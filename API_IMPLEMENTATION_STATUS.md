# QuickPay API 구현 상태 확인

## 📋 전체 API 구현 현황

### ✅ Account Service (계좌관리서비스) - 100% 완료

| API | 메서드 | 엔드포인트 | 구현 위치 | 상태 |
|-----|--------|-----------|----------|------|
| 회원가입 | POST | `/account/register` | account/app.py:86-129 | ✅ |
| 로그인 | POST | `/account/login` | account/app.py:132-163 | ✅ |
| 잔액 조회 | GET | `/account/balance` | account/app.py:166-193 | ✅ |
| 입금 | POST | `/account/deposit` | account/app.py:196-237 | ✅ |
| 출금 | POST | `/account/withdraw` | account/app.py:240-284 | ✅ |
| 디버그 API (SSRF) | GET | `/account/internal/debug` | account/app.py:287-321 | ✅ |

**특이사항**:
- 초기 잔액 10,000원 자동 부여 (account/app.py:112)
- CTF 취약점 #1: 음수 입금 허용 (account/app.py:213-214)
- CTF 취약점 #2: SSRF 취약점 (account/app.py:287-321)

---

### ✅ Auth Service (인증서비스) - 100% 완료

| API | 메서드 | 엔드포인트 | 구현 위치 | 상태 |
|-----|--------|-----------|----------|------|
| 토큰 생성 | POST | `/auth/login` | auth/app.py:123-161 | ✅ |
| 토큰 검증 | POST | `/auth/validate` | auth/app.py:163-201 | ✅ |
| 로그아웃 | POST | `/auth/logout` | auth/app.py:204-245 | ✅ |

**특이사항**:
- JWT HS256 알고리즘 사용 (auth/app.py:96)
- HttpOnly 쿠키로 토큰 전달 (auth/app.py:145-152)
- 토큰 블랙리스트 관리 (revoked_tokens 테이블)
- 토큰 만료 시간: 2시간 (환경변수 설정 가능)

---

### ✅ Payment Service (결제서비스) - 100% 완료

| API | 메서드 | 엔드포인트 | 구현 위치 | 상태 |
|-----|--------|-----------|----------|------|
| 결제 처리 (Saga Pattern) | POST | `/payments` | payment/app.py:76-180 | ✅ |
| 보상 트랜잭션 | - | `compensate_withdraw()` | payment/app.py:24-66 | ✅ |

**특이사항**:
- Saga Pattern 구현 (2단계 트랜잭션)
  - Step 1: 계좌 출금 (payment/app.py:114-121)
  - Step 2: 정산 기록 저장 (payment/app.py:138-156)
- 보상 트랜잭션 재시도 로직:
  - 최대 5번 재시도 (MAX_COMPENSATION_RETRIES=5)
  - 2초 간격 (COMPENSATION_RETRY_DELAY=2)
  - 멱등성 보장 (입금 API 여러 번 호출 가능)
- 에러 코드:
  - `TRANSACTION_STORE_FAIL`: 정산 실패, 보상 성공 (HTTP 500)
  - `CRITICAL_COMPENSATION_FAIL`: 정산 실패, 보상 실패 (HTTP 500)

---

### ✅ Settlement Service (정산서비스) - 100% 완료

| API | 메서드 | 엔드포인트 | 구현 위치 | 상태 |
|-----|--------|-----------|----------|------|
| 거래 내역 저장 | POST | `/settlement/transaction` | settlement/app.py:41-71 | ✅ |
| 정산 실행 | POST | `/settlement/execute` | settlement/app.py:77-113 | ✅ |
| 로그 뷰어 (LFI) | GET | `/settlement/internal/log_viewer` | settlement/app.py:119-143 | ✅ |

**특이사항**:
- 가맹점별 잔액 관리 (MerchantBalance 모델)
- 정산 실행 시 가맹점 잔액 0으로 초기화
- CTF 취약점 타겟: SSRF/LFI 엔드포인트 (settlement/app.py:119-143)
- FLAG 시뮬레이션: `filename=flag.txt` 요청 시 플래그 반환

---

### ✅ API Gateway (게이트웨이) - 100% 완료

| 기능 | 구현 위치 | 상태 |
|------|----------|------|
| 라우팅 | api_gateway/app.py:94-141 | ✅ |
| JWT 인증 | api_gateway/app.py:100-116 | ✅ |
| 공개 경로 관리 | api_gateway/app.py:17-22 | ✅ |
| 로그인 프록시 (2단계) | api_gateway/app.py:56-90 | ✅ |
| 정적 파일 프록시 | api_gateway/app.py:44-48 | ✅ |

**PUBLIC_PATHS (인증 불필요 경로)**:
```python
PUBLIC_PATHS = {
    '', 'web/main', 'web/login', 'web/register',
    'account/register', 'account/login', 'account/balance',
    'account/deposit', 'account/withdraw', 'account/internal/debug',
    'payments'
}
```

**라우팅 규칙**:
- `web/*` → WAS Service (http://was:5000)
- `account/*` → Account Service (http://account:5000)
- `payments` → Payment Service (http://payment:5000)
- `settlement/*` → Settlement Service (http://settlement:5000)
- `/static/*` → WAS Static Files (인증 불필요)

---

### ✅ WAS Service (웹서비스) - 100% 완료

| 기능 | 구현 위치 | 상태 |
|------|----------|------|
| 테스트 UI | was/static/index.html | ✅ |
| 정적 파일 서빙 | was/app.py | ✅ |

**index.html 기능**:
- 계정 관리: 회원가입, 로그인, 잔액 조회
- 입출금: 입금, 출금
- 결제: Saga Pattern 결제 테스트
- CTF 공격:
  - 음수 입금 공격 버튼
  - SSRF 공격 버튼 (flag.txt 읽기)

---

## 🎯 API 명세서 대비 구현 완료율

| 서비스 | 구현 API 수 | 명세 API 수 | 완료율 |
|--------|------------|------------|--------|
| Account Service | 6개 | 6개 | 100% ✅ |
| Auth Service | 3개 | 3개 | 100% ✅ |
| Payment Service | 1개 (+보상) | 1개 (+보상) | 100% ✅ |
| Settlement Service | 3개 | 3개 | 100% ✅ |
| API Gateway | 5개 기능 | 5개 기능 | 100% ✅ |
| WAS Service | 1개 | 1개 | 100% ✅ |

**전체 완료율**: **100%** ✅

---

## 📊 데이터베이스 스키마

### Account Service (account.db)

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'USER',
    balance INTEGER DEFAULT 0,
    account_number TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**초기 데이터**:
- `admin` / `password` (잔액: 1,000,000원, 계좌번호: 0000000001)
- `user1` / `password` (잔액: 50,000원, 계좌번호: 1234567890)

### Auth Service (auth.db)

```sql
-- 사용자 테이블
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 블랙리스트 토큰 테이블
CREATE TABLE revoked_tokens (
    jti TEXT PRIMARY KEY NOT NULL,
    expires_at INTEGER NOT NULL
);
```

### Settlement Service (PostgreSQL)

```python
# 거래 내역
class Settlement(db.Model):
    __tablename__ = 'settlements'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(100), unique=True)
    merchant_id = db.Column(db.String(100))
    amount = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 가맹점 잔액
class MerchantBalance(db.Model):
    __tablename__ = 'merchant_balances'
    merchant_id = db.Column(db.String(100), primary_key=True)
    balance = db.Column(db.Integer, default=0)
```

---

## 🔍 CTF 취약점 구현 상태

### 취약점 #1: 음수 입금 허용 (PDF Page 14)

**구현 위치**: account/app.py:196-237

**취약점 설명**:
- 서버 사이드 금액 검증 부재
- 클라이언트에서 음수 금액 전송 시 그대로 처리됨
- `UPDATE accounts SET balance = balance + ?` 쿼리에서 음수 값 허용

**공격 방법**:
```bash
curl -X POST http://localhost:8080/account/deposit \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user1234","amount":-50000}'
```

**결과**: 잔액 10,000원 → -40,000원 (실질적 출금)

---

### 취약점 #2: SSRF (Server-Side Request Forgery) + LFI (PDF Page 22)

**구현 위치**:
- account/app.py:287-321 (SSRF 프록시 역할)
- settlement/app.py:119-143 (SSRF 타겟)

**취약점 설명**:
- 개발자가 남긴 디버그 API (`/account/internal/debug`)
- 사용자 입력 `filename` 파라미터를 검증 없이 Settlement 서비스로 전달
- Settlement 서비스에서 파일명 검증 없이 처리
- `filename=flag.txt` 요청 시 플래그 반환

**공격 체인**:
```
[Browser]
  ↓ GET /account/internal/debug?filename=flag.txt
[API Gateway:8080]
  ↓ 라우팅 (PUBLIC_PATHS에 포함)
[Account Service:5000]
  ↓ SSRF 프록시
  ↓ GET http://settlement:5000/settlement/internal/log_viewer?filename=flag.txt
[Settlement Service:5000]
  ↓ 파일명에 'flag' 포함 확인
  ↓ return "FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}", 200
[Browser]
  ✅ FLAG 획득
```

---

## 🚀 환경 변수 설정

### Account Service
```yaml
environment:
  - DB_PATH=/app/db/account.db
  - SETTLEMENT_SERVICE_URL=http://settlement:5000
```

### Auth Service
```yaml
environment:
  - JWT_SECRET_KEY=your_secret_key_here
  - DB_PATH=/app/db/auth.db
  - TOKEN_EXPIRATION_HOURS=2
```

### Payment Service
```yaml
environment:
  - ACCOUNT_SERVICE_URL=http://account:5000
  - ADJUSTMENT_SERVICE_URL=http://settlement:5000
  - MAX_COMPENSATION_RETRIES=5
  - COMPENSATION_RETRY_DELAY=2
```

### Settlement Service
```yaml
environment:
  - DATABASE_URL=postgresql://postgres:postgres@db:5432/settlement
```

---

## 📝 구현 검증 완료

✅ **모든 API가 명세서에 따라 100% 구현되었습니다.**

- Account Service: 6개 API ✅
- Auth Service: 3개 API ✅
- Payment Service: 1개 API + 보상 로직 ✅
- Settlement Service: 3개 API ✅
- API Gateway: 라우팅 및 인증 ✅
- WAS Service: 테스트 UI ✅
- CTF 취약점: 2개 ✅

**다음 단계**: `COMPLETE_TEST_GUIDE.md` 참조하여 테스트 진행
