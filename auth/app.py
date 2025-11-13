import sqlite3
import uuid
import jwt 
import datetime
import time
from flask import Flask, request, jsonify

# ====================================================================
# [보안 설정]
# 실제 환경에서는 환경 변수를 사용해야 하며, 비밀 키는 매우 길고 복잡해야 합니다.
SECRET_KEY = "secure-quickpay-master-key-0123456789abcdef"
ALGORITHM = "HS256"
TOKEN_EXPIRY_MINUTES = 30 # 토큰 만료 시간: 30분
# ====================================================================

app = Flask(__name__)
SERVICE_PORT = 5000 
DB_PATH = 'db/auth.db'

def get_db_connection():
    """데이터베이스 연결 객체를 반환합니다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """데이터베이스와 필요한 테이블을 초기화합니다. (비밀번호는 단순 문자열로 저장합니다. 실제 환경에서는 해싱 필수)"""
    conn = get_db_connection()
    c = conn.cursor()
    # users 테이블: 사용자 정보 저장
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL 
        )
    ''')
    # revoked_tokens 테이블: 로그아웃된 토큰을 저장하는 블랙리스트
    c.execute('''
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token_id TEXT PRIMARY KEY,
            expires_at INTEGER NOT NULL
        )
    ''')

    # 테스트 사용자 추가 (admin/password)
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if c.fetchone() is None:
        # 안전한 버전: 비밀번호를 평문으로 저장합니다. (실제 환경에서는 bcrypt 등으로 해싱해야 함)
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', 'password'))
    
    # 추가 테스트 사용자
    c.execute("SELECT * FROM users WHERE username = 'user1234'")
    if c.fetchone() is None:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('user1234', 'password'))
    
    conn.commit()
    conn.close()

with app.app_context():
    init_db()

# 토큰을 헤더에서 추출하는 유틸리티 함수
def extract_token_from_header():
    """Authorization 헤더에서 Bearer 토큰을 추출합니다."""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None, "Authorization header missing"
    
    try:
        auth_type, token = auth_header.split(' ', 1)
    except ValueError:
        return None, "Invalid Authorization header format"
    
    if auth_type.lower() != 'bearer' or not token:
        return None, "Token must be a Bearer token"
    
    return token, None

# 토큰이 블랙리스트에 있는지 확인하는 함수
def is_token_revoked(jti):
    """JWT ID (jti)가 블랙리스트에 등록되어 있는지 확인합니다."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # 만료된 토큰은 블랙리스트에서 정리합니다.
    cursor.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (time.time(),))
    conn.commit()
    
    # [SQLi 방지]: 매개변수화된 쿼리 사용
    cursor.execute("SELECT token_id FROM revoked_tokens WHERE token_id = ?", (jti,))
    is_revoked = cursor.fetchone() is not None
    conn.close()
    return is_revoked

# ====================================================================
# API 엔드포인트
# ====================================================================

@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "auth"}), 200

@app.route('/auth/register', methods=['POST'])
def register():
    """사용자 등록 API"""
    data = request.json
    username = data.get('username')
    password = data.get('password') 

    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400

    conn = get_db_connection()
    try:
        # [SQLi 방지]: 매개변수화된 쿼리 사용
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return jsonify({"message": f"User {username} registered successfully"}, username), 201
    except sqlite3.IntegrityError:
        return jsonify({"message": "Username already exists"}), 409
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({"message": "Internal error"}), 500
    finally:
        conn.close()


@app.route('/auth/login', methods=['POST'])
def login():
    """
    [안전함] 토큰 생성 API
    - 요구사항: user_id와 password 검증 필요
    """
    data = request.json
    username = data.get('user_id') 
    password = data.get('password') # 비밀번호 필드 추가

    if not username or not password:
        return jsonify({"message": "User ID and password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 사용자 조회 및 인증 (비밀번호 검증 추가)
    # [SQLi 방지]: 매개변수화된 쿼리 사용
    query = "SELECT user_id, username, password FROM users WHERE username = ? AND password = ?"
    
    try:
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if user:
            # 2. 인증 성공 -> JWT 생성
            now = datetime.datetime.now(datetime.timezone.utc)
            expiry = now + datetime.timedelta(minutes=TOKEN_EXPIRY_MINUTES)
            token_id = str(uuid.uuid4()) # 토큰 블랙리스트에 사용될 고유 ID (jti)
            
            payload = {
                "user_id": user['user_id'],
                "username": user['username'],
                "exp": expiry.timestamp(), 
                "iat": now.timestamp(),      
                "jti": token_id 
            }
            
            jwt_token = jwt.encode(
                payload, 
                SECRET_KEY, 
                algorithm=ALGORITHM
            )
            
            return jsonify({
                "message": "Login successful. JWT token issued.",
                "JWT": jwt_token 
            }), 200
        else:
            # 사용자 ID 또는 비밀번호가 일치하지 않는 경우
            return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"message": "Internal error during token generation"}), 500
    finally:
        conn.close()


@app.route('/auth/validate', methods=['GET'])
def validate():
    """
    [안전함] 토큰 인증 API - 블랙리스트 검사 포함
    """
    token, error_message = extract_token_from_header()
    if error_message:
        return jsonify({"user_id": None, "message": error_message}), 401

    try:
        # 1. JWT 기본 디코딩 및 만료 시간 검사
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        jti = payload.get('jti')
        if not jti:
            return jsonify({"user_id": None, "message": "JWT missing jti claim"}), 401

        # 2. 블랙리스트 검사
        if is_token_revoked(jti):
            return jsonify({"user_id": None, "message": "Token has been revoked/logged out"}), 401

        # 3. 유효성 검증 성공
        user_id = payload.get('username') 
        return jsonify({"user_id": user_id}), 200

    except jwt.ExpiredSignatureError:
        return jsonify({"user_id": None, "message": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"user_id": None, "message": "Invalid JWT token"}), 401
    except Exception as e:
        print(f"Validation error: {e}")
        return jsonify({"user_id": None, "message": "Internal error during validation"}), 500


@app.route('/auth/logout', methods=['GET'])
def logout():
    """
    [안전함] 로그아웃 API - 사용하지 않는 토큰을 블랙리스트에 추가
    """
    token, error_message = extract_token_from_header()
    if error_message:
        return jsonify({"message": error_message}), 401
    
    conn = get_db_connection()
    try:
        # 1. 토큰 디코딩을 시도하여 유효성 및 jti, 만료 시간 확보
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get('jti')
        expires_at = payload.get('exp')

        if not jti or not expires_at:
            return jsonify({"message": "Token missing required jti or exp claim"}), 401
        
        # 2. 토큰을 블랙리스트에 추가
        # [SQLi 방지]: 매개변수화된 쿼리 사용
        conn.execute(
            "INSERT OR IGNORE INTO revoked_tokens (token_id, expires_at) VALUES (?, ?)", 
            (jti, expires_at)
        )
        conn.commit()
        
        return jsonify({"message": "Logout successful: Token revoked"}), 200

    except jwt.ExpiredSignatureError:
        # 이미 만료된 토큰이므로, 블랙리스트에 추가할 필요 없이 성공 처리
        return jsonify({"message": "Logout successful: Token already expired"}), 200
    except jwt.InvalidTokenError:
        # 유효하지 않은 토큰이므로, 로그아웃 처리할 수 없음
        return jsonify({"message": "Invalid token provided"}), 401
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({"message": "Internal error during logout"}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=SERVICE_PORT)
