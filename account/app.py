from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import bcrypt
import random
import os
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- 설정 ---
DB_PATH = os.getenv('DB_PATH', 'database.db')
SETTLEMENT_SERVICE_URL = os.getenv('SETTLEMENT_SERVICE_URL', 'http://adjustment:8003')
# -------------

# --- 데이터베이스 연결 ---
def get_db():
    """SQLite 데이터베이스 연결"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- 데이터베이스 초기화 ---
def init_db():
    """데이터베이스 초기화 및 테스트 계정 추가"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 계좌 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'USER',
            balance INTEGER DEFAULT 0,
            account_number TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 테스트 계정 추가 (admin, user1)
    test_users = [
        ('admin', 'password', 'ADMIN', 1000000, '0000000001'),
        ('user1', 'password', 'USER', 50000, '1234567890'),
    ]

    for user_id, password, role, balance, account_number in test_users:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            cursor.execute('''
                INSERT INTO accounts (user_id, password_hash, role, balance, account_number)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, password_hash, role, balance, account_number))
        except sqlite3.IntegrityError:
            pass  # 이미 존재하는 경우 무시

    conn.commit()
    conn.close()
    print(f"[{datetime.now()}] 데이터베이스 초기화 완료")


# --- API 엔드포인트 ---

@app.route('/health', methods=['GET'])
def health():
    """헬스체크"""
    return jsonify({"status": "Account Service OK"}), 200


@app.route('/account/register', methods=['POST'])
def register():
    """
    [회원가입 API] (계좌 생성)
    Request: {"user_id": "user1234", "password": "pass_word"}
    Response: {} (빈 객체, 200 OK)
    """
    data = request.get_json()
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({"error": "MISSING_FIELDS", "message": "user_id와 password가 필요합니다."}), 400

    # bcrypt로 안전하게 해시
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # 계좌번호 생성 (10자리 랜덤)
    account_number = ''.join([str(random.randint(0, 9)) for _ in range(10)])

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO accounts (user_id, password_hash, balance, account_number)
            VALUES (?, ?, ?, ?)
        ''', (user_id, password_hash, 0, account_number))

        conn.commit()
        conn.close()

        print(f"[{datetime.now()}] 회원가입 성공: {user_id}")
        return jsonify({}), 200

    except sqlite3.IntegrityError:
        return jsonify({"error": "ID_DUPLICATED", "message": "이미 존재하는 아이디입니다."}), 409
    except Exception as e:
        print(f"[{datetime.now()}] 회원가입 오류: {e}")
        return jsonify({"error": "REGISTER_FAIL", "message": "서버에 문제가 발생했습니다."}), 500


@app.route('/account/login', methods=['POST'])
def login():
    """
    [로그인 API] (계좌 인증)
    Request: {"user_id": "user1234", "password": "pass_word"}
    Response: {"user_id": "user1234"}
    """
    data = request.get_json()
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({"error": "MISSING_FIELDS", "message": "user_id와 password가 필요합니다."}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Parameterized query 사용
        cursor.execute("SELECT password_hash FROM accounts WHERE user_id = ?", (user_id,))
        account = cursor.fetchone()
        conn.close()

        if account and bcrypt.checkpw(password.encode(), account['password_hash'].encode()):
            print(f"[{datetime.now()}] 로그인 성공: {user_id}")
            return jsonify({"user_id": user_id}), 200
        else:
            return jsonify({"error": "AUTHENTICATION_FAILED", "message": "인증되지 않았습니다."}), 401

    except Exception as e:
        print(f"[{datetime.now()}] 로그인 오류: {e}")
        return jsonify({"error": "AUTHENTICATION_FAILED", "message": "인증되지 않았습니다."}), 401


@app.route('/account/balance', methods=['GET'])
def get_balance():
    """
    [잔액 조회 API]
    Request: GET /account/balance?user_id=user1234
    Response: {"balance": 50000}
    """
    user_id = request.args.get('user_id')

    if not user_id:
        return jsonify({"error": "MISSING_FIELDS", "message": "user_id가 필요합니다."}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT balance FROM accounts WHERE user_id = ?", (user_id,))
        account = cursor.fetchone()
        conn.close()

        if account:
            return jsonify({"balance": account['balance']}), 200
        else:
            return jsonify({"error": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}), 404

    except Exception as e:
        print(f"[{datetime.now()}] 잔액 조회 오류: {e}")
        return jsonify({"error": "BALANCE_CHECK_FAIL", "message": "서버에 문제가 발생했습니다."}), 500


@app.route('/account/deposit', methods=['POST'])
def deposit():
    """
    [입금 API]
    Request: {"user_id": "user1234", "amount": 10000}
    Response: {} (빈 객체, 200 OK)

    [CTF 취약점 - PDF Page 14]
    서버 사이드 검증 부재: 음수 금액 입금 가능
    """
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')

    if not user_id or amount is None:
        return jsonify({"error": "MISSING_FIELDS", "message": "user_id와 amount가 필요합니다."}), 400

    # CTF 취약점: 음수 체크 안 함 (클라이언트 사이드만 검증)
    # 공격자가 개발자 도구로 JS 수정 시 음수 입금 가능

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 사용자 존재 확인
        cursor.execute("SELECT balance FROM accounts WHERE user_id = ?", (user_id,))
        account = cursor.fetchone()

        if not account:
            conn.close()
            return jsonify({"error": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}), 404

        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()

        print(f"[{datetime.now()}] 입금 성공: {user_id} +{amount}원")
        return jsonify({}), 200

    except Exception as e:
        print(f"[{datetime.now()}] 입금 오류: {e}")
        return jsonify({"error": "DEPOSIT_FAIL", "message": "서버에 문제가 발생했습니다. 잠시후 다시 시도해주세요."}), 500


@app.route('/account/withdraw', methods=['POST'])
def withdraw():
    """
    [출금 API]
    Request: {"user_id": "user1234", "amount": 5000}
    Response: {} (빈 객체, 200 OK)
    """
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')

    if not user_id or amount is None:
        return jsonify({"error": "MISSING_FIELDS", "message": "user_id와 amount가 필요합니다."}), 400

    if amount <= 0:
        return jsonify({"error": "INVALID_AMOUNT", "message": "출금 금액은 양수여야 합니다."}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT balance FROM accounts WHERE user_id = ?", (user_id,))
        account = cursor.fetchone()

        if not account:
            conn.close()
            return jsonify({"error": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}), 404

        current_balance = account['balance']

        if current_balance < amount:
            conn.close()
            return jsonify({"error": "INSUFFICIENT_FUNDS", "message": "출금 금액이 현재 잔액을 초과합니다."}), 403

        # 출금 처리
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()

        print(f"[{datetime.now()}] 출금 성공: {user_id} -{amount}원")
        return jsonify({}), 200

    except Exception as e:
        print(f"[{datetime.now()}] 출금 오류: {e}")
        return jsonify({"error": "WITHDRAW_FAIL", "message": "서버에 문제가 발생했습니다. 잠시후 다시 시도해주세요."}), 500


@app.route('/account/internal/debug', methods=['GET'])
def debug_log_viewer():
    """
    [CTF 취약점 API - PDF Page 22]
    개발자가 실수로 남긴 디버그용 API

    SSRF (Server-Side Request Forgery):
    정산서비스의 내부 API를 프록시처럼 사용 가능

    공격 시나리오:
    1. SSH로 계좌관리서비스 침투
    2. 소스코드 분석 중 이 API 발견
    3. GET /account/internal/debug?filename=flag.txt 호출
    4. 정산서비스의 flag.txt 읽기 성공

    Request: GET /account/internal/debug?filename=flag.txt
    Response: flag 내용
    """
    filename = request.args.get('filename', 'access.log')

    print(f"[{datetime.now()}] [디버그 API 호출] filename={filename}")

    try:
        response = requests.get(
            f"{SETTLEMENT_SERVICE_URL}/settlement/internal/log_viewer",
            params={'filename': filename},
            timeout=5
        )

        print(f"[{datetime.now()}] [디버그 API 응답] status={response.status_code}")
        return response.text, response.status_code

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] [디버그 API 오류] {e}")
        return jsonify({"error": "CONNECTION_FAILED", "message": "정산서비스에 연결할 수 없습니다."}), 503


if __name__ == '__main__':
    # 데이터베이스 초기화
    init_db()

    # Flask 개발 서버 실행
    app.run(host='0.0.0.0', port=8001, debug=True)
