# Saga Pattern 보상 트랜잭션 테스트 시나리오

## 🎯 테스트 목적
정산서비스 장애 시 결제서비스의 보상 트랜잭션(Compensation Transaction)이 올바르게 작동하는지 검증

---

## 👥 테스트 계정 준비

### 1. 손님 계정 (Customer)
- **User ID**: `customer01`
- **Password**: `customer01`
- **초기 잔액**: 10,000원 (회원가입 시 자동 부여)

### 2. 가게 주인 계정 (Merchant)
- **Merchant ID**: `merchant_coffee`
- **설명**: 커피숍 가맹점

---

## 📋 테스트 절차

### Step 0: 환경 준비

```bash
# 1. Docker 컨테이너 실행 확인
cd C:\Users\wngus\quickpay-temp
docker-compose ps

# 2. Settlement 서비스 강제 중지 (장애 시뮬레이션)
docker stop settlement
```

---

### Step 1: 손님 계정 생성

#### 브라우저 방식
```
1. http://localhost:8080/static/index.html 접속
2. User ID: customer01
3. Password: customer01
4. "회원가입" 버튼 클릭
5. "잔액 조회" → 10,000원 확인
```

#### curl 방식
```bash
# 회원가입
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"customer01","password":"customer01"}'

# 잔액 조회
curl "http://localhost:8080/account/balance?user_id=customer01"
# Expected: {"balance": 10000}
```

---

### Step 2: 정상 결제 테스트 (Settlement 서비스 정상 작동 시)

#### Settlement 서비스 재시작
```bash
docker start settlement
sleep 5  # 서비스 초기화 대기
```

#### 결제 요청
```bash
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 3000
  }'
```

#### 예상 결과
```json
{}
```
**HTTP Status**: 200 OK

#### 잔액 확인
```bash
curl "http://localhost:8080/account/balance?user_id=customer01"
# Expected: {"balance": 7000}  (10,000 - 3,000)
```

---

### Step 3: **보상 트랜잭션 테스트** (Settlement 서비스 장애 시)

#### 3-1. Settlement 서비스 강제 중지
```bash
docker stop settlement
```

#### 3-2. 결제 시도 (실패 예상)
```bash
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "customer01",
    "merchant_id": "merchant_coffee",
    "amount": 2000
  }'
```

#### 3-3. 예상 응답
```json
{
  "error": "TRANSACTION_STORE_FAIL",
  "message": "결제는 실패했으나, 잔액은 복구되었습니다. 잠시 후 다시 시도해주세요."
}
```
**HTTP Status**: 500 Internal Server Error

#### 3-4. **중요: 잔액이 복구되었는지 확인**
```bash
curl "http://localhost:8080/account/balance?user_id=customer01"
# Expected: {"balance": 7000}  ← 변화 없음! (보상 트랜잭션 성공)
```

---

## 🔍 Saga Pattern 트래픽 흐름 (Settlement 장애 시)

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: 결제 요청                                                │
└─────────────────────────────────────────────────────────────────┘

[Browser/curl]
    ↓ POST /payments
    ↓ {"user_id":"customer01", "merchant_id":"merchant_coffee", "amount":2000}

[API Gateway:8080]
    ↓ 라우팅 → http://payment:5000/payments

[Payment Service:5000]
    ↓ app.py:108 거래 ID 생성: uuid.uuid4()
    ↓ transaction_id = "abc-123-def-456"
    ↓
    ↓ ===== Step 1: 계좌 출금 =====
    ↓ app.py:114 POST http://account:5000/account/withdraw
    ↓ {"user_id":"customer01", "amount":2000}

[Account Service:5000]
    ↓ app.py:240 withdraw() 함수
    ↓ 잔액 확인: 7,000원 ✅
    ↓ 출금 처리: 7,000 - 2,000 = 5,000원
    ↓ SQLite UPDATE 성공
    ↓ return {}, 200 ✅

[Payment Service:5000]
    ↓ app.py:121 출금 성공 확인
    ↓ 잔액: 7,000 → 5,000원 (2,000원 출금됨)
    ↓
    ↓ ===== Step 2: 정산 기록 저장 =====
    ↓ app.py:138 POST http://settlement:5000/settlement/transaction
    ↓ {"transaction_id":"abc-123", "merchant_id":"merchant_coffee", ...}
    ↓
    ↓ ⚠️ Settlement 서비스 중지됨!
    ↓ requests.exceptions.ConnectionError 발생
    ↓
    ↓ app.py:158 예외 처리
    ↓ print("[Step 2 실패] 정산서비스 연결 오류")
    ↓
    ↓ ===== 보상 트랜잭션 시작 =====
    ↓ app.py:164 compensate_withdraw() 호출
    ↓ user_id="customer01", amount=2000

[Payment Service:5000 - compensate_withdraw 함수]
    ↓ app.py:39 for attempt in range(1, 6):  # 최대 5번 재시도
    ↓
    ↓ [시도 1/5]
    ↓ app.py:43 POST http://account:5000/account/deposit
    ↓ {"user_id":"customer01", "amount":2000}

[Account Service:5000]
    ↓ app.py:196 deposit() 함수
    ↓ 입금 처리: 5,000 + 2,000 = 7,000원
    ↓ SQLite UPDATE 성공
    ↓ return {}, 200 ✅

[Payment Service:5000 - compensate_withdraw 함수]
    ↓ app.py:49 if response.status_code == 200:
    ↓ app.py:50 print("[보상 성공]")
    ↓ app.py:51 return True ✅
    ↓
    ↓ app.py:166 if compensation_success:
    ↓ app.py:168 print("[결제 실패] 보상 트랜잭션 완료, 사용자 잔액 복구됨")
    ↓
    ↓ return {"error":"TRANSACTION_STORE_FAIL", ...}, 500

[API Gateway:8080]
    ↓ 응답 전달

[Browser/curl]
    ✅ 500 에러 수신 (결제 실패)
    ✅ 잔액 7,000원 복구됨 (보상 트랜잭션 성공)
```

---

## 📊 데이터베이스 변화

### Account Service DB (account.db)

```sql
-- 초기 상태 (회원가입 직후)
SELECT user_id, balance FROM accounts WHERE user_id='customer01';
┌────────────┬─────────┐
│ user_id    │ balance │
├────────────┼─────────┤
│ customer01 │ 10,000  │
└────────────┴─────────┘

-- 정상 결제 후 (3,000원 결제)
┌────────────┬─────────┐
│ user_id    │ balance │
├────────────┼─────────┤
│ customer01 │  7,000  │  ← 10,000 - 3,000
└────────────┴─────────┘

-- Settlement 장애 시 결제 시도 (2,000원)
--
-- ① 출금 실행: 7,000 → 5,000 (일시적)
-- ② Settlement 연결 실패
-- ③ 보상 트랜잭션: 5,000 → 7,000 (복구!)

┌────────────┬─────────┐
│ user_id    │ balance │
├────────────┼─────────┤
│ customer01 │  7,000  │  ← 복구됨! (원자성 보장)
└────────────┴─────────┘
```

---

## 🧪 로그 확인

### Payment Service 로그
```bash
docker logs payment | tail -30
```

#### 예상 로그 출력
```
[2025-01-18 12:00:00] [결제 시작] transaction_id=abc-123, user_id=customer01, amount=2000
[2025-01-18 12:00:00] [Step 1] 계좌 출금 요청 중...
[2025-01-18 12:00:00] [Step 1 성공] 출금 완료
[2025-01-18 12:00:00] [Step 2] 정산 기록 저장 요청 중...
[2025-01-18 12:00:01] [Step 2 실패] 정산서비스 연결 오류: Connection refused
[2025-01-18 12:00:01] [보상 트랜잭션 필요] Step 2 실패로 인한 출금 취소 시작
[2025-01-18 12:00:01] [보상 트랜잭션 시작] transaction_id=abc-123, user_id=customer01, amount=2000
[2025-01-18 12:00:01] [보상 시도 1/5] 입금 요청 중...
[2025-01-18 12:00:01] [보상 성공] transaction_id=abc-123
[2025-01-18 12:00:01] [결제 실패] 보상 트랜잭션 완료, 사용자 잔액 복구됨
```

### Account Service 로그
```bash
docker logs account | tail -20
```

#### 예상 로그 출력
```
[2025-01-18 12:00:00] 출금 성공: customer01 -2000원
[2025-01-18 12:00:01] 입금 성공: customer01 +2000원  ← 보상 트랜잭션
```

---

## ⚠️ 보상 트랜잭션 실패 시나리오 (극단적 케이스)

만약 **Account 서비스마저 중지된 상태**라면?

### 테스트
```bash
# Settlement과 Account 모두 중지
docker stop settlement account

# 결제 시도
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{"user_id":"customer01","merchant_id":"merchant_coffee","amount":2000}'
```

### 예상 응답
```json
{
  "error": "SERVICE_UNAVAILABLE",
  "message": "계좌관리서비스에 연결할 수 없습니다."
}
```
**HTTP Status**: 503 Service Unavailable

→ **Step 1 출금 자체가 실패**하므로, 보상 트랜잭션이 불필요 (안전)

---

### Account 서비스가 재시도 중 복구된다면?

```bash
# Settlement만 중지 (Account는 정상)
docker stop settlement
docker start account  # Account 재시작

# 결제 시도
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{"user_id":"customer01","merchant_id":"merchant_coffee","amount":2000}'
```

#### 로그 예시
```
[보상 시도 1/5] 입금 요청 중...
[보상 실패] 연결 오류: Connection refused
2초 후 재시도...
[보상 시도 2/5] 입금 요청 중...
[보상 실패] 연결 오류: Connection refused
2초 후 재시도...
[보상 시도 3/5] 입금 요청 중...
[보상 성공] transaction_id=abc-123  ← Account 서비스 복구 후 성공!
```

→ **재시도 로직으로 최종 보상 성공** (원자성 보장!)

---

## 🎯 테스트 체크리스트

- [ ] 손님 계정 생성 (customer01)
- [ ] 초기 잔액 10,000원 확인
- [ ] Settlement 정상 시 결제 성공 (3,000원)
- [ ] 잔액 7,000원 확인
- [ ] Settlement 중지
- [ ] 결제 시도 (2,000원)
- [ ] 500 에러 수신 (TRANSACTION_STORE_FAIL)
- [ ] **잔액 여전히 7,000원 (보상 완료)** ✅
- [ ] Payment 로그에서 보상 트랜잭션 확인
- [ ] Account 로그에서 입금 기록 확인

---

## 🔧 환경 변수로 재시도 설정 변경

`docker-compose.yml`에서 설정 가능:

```yaml
payment:
  environment:
    - MAX_COMPENSATION_RETRIES=10     # 재시도 횟수 증가
    - COMPENSATION_RETRY_DELAY=1      # 재시도 간격 단축 (1초)
```

---

## 📌 핵심 포인트

1. **원자성(Atomicity)**: 정산 실패 시 출금도 취소됨
2. **재시도 로직**: 최대 5번, 2초 간격으로 보상 시도
3. **멱등성(Idempotency)**: 입금 API는 여러 번 호출해도 안전
4. **로깅**: 모든 단계가 상세히 로그로 기록됨
5. **에러 처리**: 명확한 에러 메시지와 HTTP 상태 코드

---

## 🚀 브라우저에서 테스트

```
1. http://localhost:8080/static/index.html 접속
2. User ID: customer01, Password: customer01 입력 후 회원가입
3. 잔액 조회 → 10,000원 확인
4. 터미널에서: docker stop settlement
5. 브라우저에서 결제하기:
   - Merchant ID: merchant_coffee
   - 금액: 2,000
6. "결제하기" 버튼 클릭
7. 에러 메시지 확인: "결제는 실패했으나, 잔액은 복구되었습니다"
8. 잔액 조회 → 여전히 10,000원! ✅
```

---

## 📊 성공 기준

✅ Settlement 장애 시에도 사용자 잔액이 복구됨
✅ 보상 트랜잭션 재시도 로직 작동
✅ 명확한 에러 메시지 반환
✅ 로그에서 전체 트랜잭션 흐름 추적 가능
