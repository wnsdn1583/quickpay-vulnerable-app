from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import os
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# --- 설정 (환경 변수) ---
# ACCOUNT_SERVICE_URL은 계좌 서비스의 내부 주소입니다.
ACCOUNT_SERVICE_URL = os.getenv('ACCOUNT_SERVICE_URL', 'http://account:8001')
# ADJUSTMENT_SERVICE_URL은 정산 서비스의 내부 주소입니다.
# 참고: 이 변수는 파일 구조상 settlement 서비스를 가리키는 것으로 보입니다.
ADJUSTMENT_SERVICE_URL = os.getenv('ADJUSTMENT_SERVICE_URL', 'http://adjustment:8003')
MAX_COMPENSATION_RETRIES = int(os.getenv('MAX_COMPENSATION_RETRIES', '5'))
COMPENSATION_RETRY_DELAY = int(os.getenv('COMPENSATION_RETRY_DELAY', '2'))
# -----------------------------


# --- 보상 트랜잭션 함수 ---
def compensate_withdraw(user_id, amount, transaction_id):
    """
    [보상 트랜잭션] (Compensation Transaction)
    출금을 취소하기 위해 입금 처리

    Args:
        user_id: 사용자 ID
        amount: 환불할 금액 (원래 출금한 금액)
        transaction_id: 거래 ID (로깅용)

    Returns:
        bool: 보상 성공 여부
    """
    print(f"[{datetime.now()}] [보상 트랜잭션 시작] transaction_id={transaction_id}, user_id={user_id}, amount={amount}")

    for attempt in range(1, MAX_COMPENSATION_RETRIES + 1):
        try:
            print(f"[{datetime.now()}] [보상 시도 {attempt}/{MAX_COMPENSATION_RETRIES}] 입금 요청 중...")

            response = requests.post(
                f"{ACCOUNT_SERVICE_URL}/account/deposit",
                json={"user_id": user_id, "amount": amount},
                timeout=5
            )

            if response.status_code == 200:
                print(f"[{datetime.now()}] [보상 성공] transaction_id={transaction_id}")
                return True
            else:
                print(f"[{datetime.now()}] [보상 실패] 응답 코드: {response.status_code}, 응답: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"[{datetime.now()}] [보상 실패] 연결 오류: {e}")

        # 마지막 시도가 아니면 대기 후 재시도
        if attempt < MAX_COMPENSATION_RETRIES:
            print(f"[{datetime.now()}] {COMPENSATION_RETRY_DELAY}초 후 재시도...")
            time.sleep(COMPENSATION_RETRY_DELAY)

    # 모든 재시도 실패
    print(f"[{datetime.now()}] [보상 실패] transaction_id={transaction_id}, user_id={user_id}, amount={amount}")
    return False


# --- API 엔드포인트 ---

@app.route('/health', methods=['GET'])
def health():
    """헬스체크"""
    return jsonify({"status": "Payment Service OK"}), 200


@app.route('/payments', methods=['POST'])
def process_payment():
    """
    [결제 처리 API] (Saga Pattern Orchestration)

    Request: {"user_id": "user1234", "merchant_id": "M1234", "amount": 1000}
    Response: {} (빈 객체, 200 OK)

    에러 응답:
    - 403: {"error": "INSUFFICIENT_FUNDS", "message": "..."}
    - 500: {"error": "TRANSACTION_STORE_FAIL", "message": "..."}
    - 503: {"error": "SERVICE_UNAVAILABLE", "message": "..."}
    """
    data = request.get_json()
    user_id = data.get('user_id')
    merchant_id = data.get('merchant_id')
    amount = data.get('amount')

    # 입력값 검증
    if not user_id or not merchant_id or amount is None:
        return jsonify({
            "error": "MISSING_FIELDS",
            "message": "user_id, merchant_id, amount가 필요합니다."
        }), 400

    if amount <= 0:
        return jsonify({
            "error": "INVALID_AMOUNT",
            "message": "결제 금액은 양수여야 합니다."
        }), 400

    # 거래 ID 생성
    transaction_id = str(uuid.uuid4())
    print(f"[{datetime.now()}] [결제 시작] transaction_id={transaction_id}, user_id={user_id}, merchant_id={merchant_id}, amount={amount}")

    # ===== Step 1: 계좌 출금 =====
    try:
        print(f"[{datetime.now()}] [Step 1] 계좌 출금 요청 중...")
        withdraw_response = requests.post(
            f"{ACCOUNT_SERVICE_URL}/account/withdraw",
            json={"user_id": user_id, "amount": amount},
            timeout=5
        )

        # 출금 실패 (잔액 부족 또는 서버 오류)
        if withdraw_response.status_code != 200:
            error_data = withdraw_response.json()
            print(f"[{datetime.now()}] [Step 1 실패] {error_data}")
            return jsonify(error_data), withdraw_response.status_code

        print(f"[{datetime.now()}] [Step 1 성공] 출금 완료")

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] [Step 1 실패] 계좌관리서비스 연결 오류: {e}")
        return jsonify({
            "error": "SERVICE_UNAVAILABLE",
            "message": "계좌관리서비스에 연결할 수 없습니다."
        }), 503

    # ===== Step 2: 정산 기록 저장 =====
    try:
        print(f"[{datetime.now()}] [Step 2] 정산 기록 저장 요청 중...")
        adjustment_response = requests.post(
            f"{ADJUSTMENT_SERVICE_URL}/settlement/transaction",
            json={
                "transaction_id": transaction_id,
                "merchant_id": merchant_id,
                "amount": amount,
                "user_id": user_id
            },
            timeout=5
        )

        # 정산 기록 저장 성공
        if adjustment_response.status_code == 200:
            print(f"[{datetime.now()}] [Step 2 성공] 정산 기록 저장 완료")
            print(f"[{datetime.now()}] [결제 성공] transaction_id={transaction_id}")
            return jsonify({}), 200

        # 정산 기록 저장 실패 → 보상 트랜잭션 시작
        print(f"[{datetime.now()}] [Step 2 실패] 정산서비스 오류: {adjustment_response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] [Step 2 실패] 정산서비스 연결 오류: {e}")

    # ===== 보상 트랜잭션: 출금 취소 (입금) =====
    # Step 2(정산 기록 저장)가 실패했으므로, Step 1(출금)을 취소해야 합니다.
    print(f"[{datetime.now()}] [보상 트랜잭션 필요] Step 2 실패로 인한 출금 취소 시작")
    compensation_success = compensate_withdraw(user_id, amount, transaction_id)

    if compensation_success:
        # 보상 성공 → 결제 실패 응답
        print(f"[{datetime.now()}] [결제 실패] 보상 트랜잭션 완료, 사용자 잔액 복구됨")
        return jsonify({
            "error": "TRANSACTION_STORE_FAIL",
            "message": "결제는 실패했으나, 잔액은 복구되었습니다. 잠시 후 다시 시도해주세요."
        }), 500
    else:
        # 보상 실패 (심각한 상황, 수동 개입 필요)
        print(f"[{datetime.now()}] [결제 실패] 보상 트랜잭션 실패 (심각한 오류)")
        return jsonify({
            "error": "CRITICAL_COMPENSATION_FAIL",
            "message": "치명적인 서버 오류가 발생했습니다. 고객센터에 문의해주세요."
        }), 500


if __name__ == '__main__':
    # Flask 개발 서버 실행 (Payment 서비스는 8002번 포트 사용을 가정)
    app.run(host='0.0.0.0', port=8002, debug=True)
