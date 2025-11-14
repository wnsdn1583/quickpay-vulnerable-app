from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import jwt
import bcrypt
import os
import uuid
import time
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# --- 설정 (Environment Variables 사용) ---
# Secret Key는 JWT 서명에 사용되며, 외부에 절대 노출되면 안 됩니다.
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'default_very_secret_key_for_dev')
DB_PATH = os.getenv('DB_PATH', 'db/auth.db')
TOKEN_EXPIRATION_HOURS = int(os.getenv('TOKEN_EXPIRATION_HOURS', '2'))
# ----------------------------------------


# --- 데이터베이스 연결 및 초기화 ---

def get_db():
    """SQLite 데이터베이스 연결"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # 결과를 딕셔너리 형태로 반환
    return conn

def init_db():
    """데이터베이스 초기화 (users 테이블, revoked_tokens 테이블 생성)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 사용자 계정 테이블 (로그인 검증용)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. 블랙리스트 토큰 테이블 (로그아웃 처리용)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            jti TEXT PRIMARY KEY NOT NULL,
            expires_at INTEGER NOT NULL
        )
    ''')

    # 테스트 계정 추가 (account.py와 동일한 'user1', 'admin' 계정)
    test_users = [
        ('admin', 'password'),
        ('user1', 'password'),
    ]

    for user_id, password in test_users:
        # bcrypt로 안전하게 해시
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            cursor.execute('''
                INSERT INTO users (user_id, password_hash)
                VALUES (?, ?)
            ''', (user_id, password_hash))
        except sqlite3.IntegrityError:
            pass  # 이미 존재하는 경우 무시

    conn.commit()
    conn.close()
    print(f"[{datetime.now()}] [DB] 데이터베이스 초기화 및 테스트 계정 추가 완료")


# --- 유틸리티 함수 ---

def create_jwt_token(user_id):
    """JWT 토큰 생성 및 서명"""
    jti = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS)
    
    payload = {
        'user_id': user_id,
        'exp': expires,              # 만료 시간 (UTC)
        'iat': datetime.utcnow(),    # 발행 시간 (UTC)
        'jti': jti                   # JWT ID (블랙리스트 추적용)
    }
    
    # HS256 알고리즘으로 서명
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
    
    return token, expires


def is_token_revoked(jti):
    """토큰이 블랙리스트에 있는지 확인"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 현재 만료되지 않은 토큰만 확인
    cursor.execute("SELECT jti FROM revoked_tokens WHERE jti = ? AND expires_at > ?", 
                   (jti, int(time.time())))
    is_revoked = cursor.fetchone() is not None
    conn.close()
    
    return is_revoked


# --- API 엔드포인트 ---

@app.route('/health', methods=['GET'])
def health():
    """헬스체크"""
    return jsonify({"status": "Auth Service OK"}), 200


@app.route('/auth/login', methods=['POST'])
def login():
    """
    [토큰 생성 API] (JWT 발급)
    Request: {"user_id": "user1234", "password": "pass_word"}
    Response: {"JWT": "..."}
    """
    data = request.get_json()
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        print(f"[{datetime.now()}] [Login 실패] 누락된 필드: user_id={user_id}")
        return jsonify({"error": "MISSING_FIELDS", "message": "user_id와 password가 필요합니다."}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Parameterized query를 사용하여 SQL Injection 방지
        cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        # 사용자 존재 및 비밀번호 검증 (bcrypt 사용)
        if user and bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            # 토큰 생성
            token, expires = create_jwt_token(user_id)
            print(f"[{datetime.now()}] [Login 성공] user_id={user_id}, 만료 시간={expires}")
            return jsonify({"JWT": token}), 200
        else:
            print(f"[{datetime.now()}] [Login 실패] 인증 실패: user_id={user_id}")
            return jsonify({"error": "AUTHENTICATION_FAILED", "message": "아이디 또는 비밀번호가 일치하지 않습니다."}), 401

    except Exception as e:
        print(f"[{datetime.now()}] [Login 오류] {e}")
        return jsonify({"error": "SERVER_ERROR", "message": "인증 서버 오류가 발생했습니다."}), 500


@app.route('/auth/validate', methods=['GET'])
def validate_token():
    """
    [토큰 인증 API] (토큰 유효성 검사 및 사용자 ID 반환)
    Header: Authorization: Bearer {JWT}
    Response: {"user_id": "..."}
    """
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        print(f"[{datetime.now()}] [Validate 실패] Authorization 헤더 누락")
        return jsonify({"error": "MISSING_TOKEN", "message": "Authorization 헤더가 누락되었거나 형식이 잘못되었습니다."}), 401

    token = auth_header.split(' ', 1)[1]
    
    try:
        # 1. 토큰 디코딩 및 검증 (서명 및 만료 시간 확인)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        jti = payload.get('jti')

        # 2. 블랙리스트 확인
        if is_token_revoked(jti):
            print(f"[{datetime.now()}] [Validate 실패] 폐기된 토큰 (블랙리스트): user_id={user_id}, jti={jti}")
            return jsonify({"error": "TOKEN_REVOKED", "message": "이 토큰은 이미 로그아웃되었습니다."}), 401
        
        print(f"[{datetime.now()}] [Validate 성공] user_id={user_id}, jti={jti}")
        return jsonify({"user_id": user_id}), 200

    except jwt.ExpiredSignatureError:
        print(f"[{datetime.now()}] [Validate 실패] 토큰 만료")
        return jsonify({"error": "TOKEN_EXPIRED", "message": "토큰이 만료되었습니다."}), 401
    except jwt.InvalidSignatureError:
        print(f"[{datetime.now()}] [Validate 실패] 서명 불일치")
        return jsonify({"error": "INVALID_TOKEN", "message": "토큰 서명이 유효하지 않습니다."}), 401
    except jwt.exceptions.DecodeError:
        print(f"[{datetime.now()}] [Validate 실패] 디코딩 오류")
        return jsonify({"error": "INVALID_TOKEN", "message": "토큰 형식이 잘못되었습니다."}), 401
    except Exception as e:
        print(f"[{datetime.now()}] [Validate 오류] {e}")
        return jsonify({"error": "SERVER_ERROR", "message": "토큰 검증 중 서버 오류가 발생했습니다."}), 500


@app.route('/auth/logout', methods=['GET'])
def logout():
    """
    [로그아웃 API] (토큰 블랙리스트 추가)
    Header: Authorization: Bearer {JWT}
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "MISSING_TOKEN", "message": "Authorization 헤더가 필요합니다."}), 401

    token = auth_header.split(' ', 1)[1]
    
    try:
        # 토큰 디코딩 (만료 여부 검사 없이 서명만 검사)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'], options={"verify_exp": False})
        jti = payload.get('jti')
        exp = payload.get('exp')
        user_id = payload.get('user_id')
        
        if not jti or not exp:
             raise jwt.exceptions.DecodeError("토큰에 jti 또는 exp 클레임이 없습니다.")

        conn = get_db()
        cursor = conn.cursor()
        
        # 블랙리스트 테이블에 JTI와 만료 시간(Unix timestamp) 저장
        # 토큰이 이미 폐기된 상태일 수 있으므로 IGNORE 사용
        cursor.execute("INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)", (jti, exp))
        conn.commit()
        conn.close()
        
        print(f"[{datetime.now()}] [Logout 성공] user_id={user_id}, jti={jti} 블랙리스트에 추가됨")
        return jsonify({"message": "로그아웃 성공, 토큰이 폐기되었습니다."}), 200

    except Exception as e:
        print(f"[{datetime.now()}] [Logout 오류] {e}")
        return jsonify({"error": "LOGOUT_FAIL", "message": "로그아웃 처리 중 오류가 발생했습니다."}), 500


if __name__ == '__main__':
    # 데이터베이스 초기화
    init_db()
    
    # Flask 개발 서버 실행 (Auth 서비스는 5000번 포트 사용)
    # account.py는 8001, payment.py는 8002 포트를 사용하므로, auth는 5000번을 사용하겠습니다.
    app.run(host='0.0.0.0', port=5000, debug=True)
