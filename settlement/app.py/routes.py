from flask import Blueprint, request, jsonify
from app import db
from app.models import Settlement, MerchantBalance
import requests
import time

settlement_bp = Blueprint('settlement', __name__)

ACCOUNT_SERVICE_URL = "http://localhost:5002/account/deposit"  # 계좌관리서비스 URL

# 거래 내역 저장
@settlement_bp.route('/settlement/transaction', methods=['POST'])
def save_transaction():
    try:
        data = request.get_json()
        merchant_id = data.get('merchant_id')
        amount = data.get('amount')

        if not merchant_id or not amount:
            return jsonify({"error": "INVALID_REQUEST", "message": "merchant_id와 amount는 필수입니다."}), 400

        # 거래 저장
        transaction = Settlement(merchant_id=merchant_id, amount=amount)
        db.session.add(transaction)

        # 잔액 업데이트
        merchant = MerchantBalance.query.filter_by(merchant_id=merchant_id).first()
        if not merchant:
            merchant = MerchantBalance(merchant_id=merchant_id, balance=0)
            db.session.add(merchant)
        merchant.balance += amount

        db.session.commit()

        return jsonify({"status": "success", "message": "거래 내역이 정상적으로 저장되었습니다."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "TRANSACTION_STORE_FAIL",
            "message": "서버에 문제가 발생했습니다. 잠시후 다시 시도해주세요."
        }), 500

# 주기적 정산
@settlement_bp.route('/settlement/execute', methods=['POST'])
def execute_settlement():
    merchants = MerchantBalance.query.all()
    settled = []

    for merchant in merchants:
        amount = merchant.balance
        if amount <= 0:
            continue

        # 계좌관리서비스로 입금 (원자성 보장)
        success = False
        while not success:
            try:
                resp = requests.post(ACCOUNT_SERVICE_URL, json={
                    "user_id": merchant.merchant_id,
                    "amount": amount
                })
                if resp.status_code == 200:
                    success = True
                else:
                    time.sleep(1)
            except requests.exceptions.RequestException:
                time.sleep(1)

        # 정산 완료 후 잔액 초기화
        merchant.balance = 0
        db.session.commit()

        settled.append({
            "merchant_id": merchant.merchant_id,
            "settled_amount": amount
        })

    return jsonify({
        "status": "success",
        "settled": settled
    }), 200
