from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import time
import requests

# ----------------------------------------
# DB 설정
# ----------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "settlement.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------------------------------
# 모델 정의
# ----------------------------------------
class Settlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)

class MerchantBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.String(50), unique=True, nullable=False)
    balance = db.Column(db.Integer, default=0)

# ----------------------------------------
# 계좌관리 서비스 주소
# ----------------------------------------
ACCOUNT_SERVICE_URL = "http://localhost:5002/account/deposit"


# ----------------------------------------
# API 1: 거래 저장
# ----------------------------------------
@app.route("/settlement/transaction", methods=["POST"])
def save_transaction():
    try:
        data = request.get_json()
        merchant_id = data.get("merchant_id")
        amount = data.get("amount")

        if not merchant_id or amount is None:
            return jsonify({"error": "INVALID_REQUEST",
                            "message": "merchant_id와 amount는 필수입니다."}), 400

        # 거래 내역 저장
        transaction = Settlement(merchant_id=merchant_id, amount=amount)
        db.session.add(transaction)

        # 잔액 업데이트
        merchant = MerchantBalance.query.filter_by(merchant_id=merchant_id).first()
        if not merchant:
            merchant = MerchantBalance(merchant_id=merchant_id, balance=0)
            db.session.add(merchant)

        merchant.balance += amount
        db.session.commit()

        return jsonify({"status": "success",
                        "message": "거래 내역이 정상적으로 저장되었습니다."}), 200

    except Exception:
        db.session.rollback()
        return jsonify({"error": "TRANSACTION_STORE_FAIL",
                        "message": "서버 문제 발생. 다시 시도해주세요."}), 500


# ----------------------------------------
# API 2: 주기적 정산
# ----------------------------------------
@app.route("/settlement/execute", methods=["POST"])
def execute_settlement():
    merchants = MerchantBalance.query.all()
    settled = []

    for merchant in merchants:
        amount = merchant.balance
        if amount <= 0:
            continue

        # 원자성 보장: 성공할 때까지 입금 재시도
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

        # 정산 후 초기화
        merchant.balance = 0
        db.session.commit()

        settled.append({
            "merchant_id": merchant.merchant_id,
            "settled_amount": amount
        })

    return jsonify({"status": "success", "settled": settled}), 200


# ----------------------------------------
# 서버 시작
# ----------------------------------------
if __name__ == "__main__":
    # db 폴더 없으면 생성
    os.makedirs(os.path.join(BASE_DIR, "db"), exist_ok=True)

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5001, debug=True)
