# QuickPay 기능 개선 사항

## 🔍 발견된 문제점

### 1. API Gateway PUBLIC_PATHS 부족
**문제**: 회원가입 후 로그인, 잔액 조회 등이 인증 없이 불가능
**현재 PUBLIC_PATHS**: `{'', 'web/main', 'web/login', 'web/register', 'account/register'}`
**부족한 경로**:
- `account/login` - 로그인
- `account/balance` - 잔액 조회
- `account/deposit` - 입금 (CTF 테스트용)
- `account/withdraw` - 출금
- `account/internal/debug` - SSRF 테스트용

### 2. 테스트 인터페이스 부재
**문제**: 브라우저에서 직접 테스트할 수 있는 UI가 없음
**필요**: 간단한 HTML 테스트 페이지

### 3. 회원가입 시 초기 잔액 부족
**문제**: 신규 가입자 잔액이 0원이어서 바로 테스트 불가
**개선안**: 회원가입 시 초기 잔액 부여 옵션

---

## ✅ 수정 계획

### 수정 1: API Gateway PUBLIC_PATHS 확장
**파일**: `api_gateway/app.py`
**변경**: CTF 테스트를 위해 account 관련 경로 전체 공개

### 수정 2: Account Service 초기 잔액 부여
**파일**: `account/app.py`
**변경**: 회원가입 시 초기 잔액 10,000원 부여

### 수정 3: 간단한 테스트 HTML 페이지 추가
**파일**: `was/static/test.html` (신규)
**내용**: API 테스트용 간단한 웹 인터페이스

---

## 📝 상세 수정 내역

### ✅ 수정 1: API Gateway PUBLIC_PATHS 확장

**파일**: `api_gateway/app.py` (Line 14-22)

**변경 전**:
```python
PUBLIC_PATHS = {'', 'web/main', 'web/login', 'web/register', 'account/register'}
```

**변경 후**:
```python
PUBLIC_PATHS = {
    '', 'web/main', 'web/login', 'web/register',
    'account/register', 'account/login', 'account/balance',
    'account/deposit', 'account/withdraw', 'account/internal/debug',
    'payments'
}
```

**이유**:
- CTF 테스트를 위해 인증 없이 계좌 API 접근 필요
- 회원가입 후 로그인, 잔액 조회, 입출금, CTF 공격 테스트 가능하도록 함

---

### ✅ 수정 2: 회원가입 시 초기 잔액 부여

**파일**: `account/app.py` (Line 111-117)

**변경 전**:
```python
cursor.execute('''
    INSERT INTO accounts (user_id, password_hash, balance, account_number)
    VALUES (?, ?, ?, ?)
''', (user_id, password_hash, 0, account_number))
```

**변경 후**:
```python
# 초기 잔액 10,000원 부여 (테스트 편의성)
initial_balance = 10000

cursor.execute('''
    INSERT INTO accounts (user_id, password_hash, balance, account_number)
    VALUES (?, ?, ?, ?)
''', (user_id, password_hash, initial_balance, account_number))
```

**이유**:
- 신규 가입자가 바로 입출금 및 결제 테스트 가능
- CTF 문제 풀이 시 초기 자금 필요

---

### ✅ 수정 3: 테스트 HTML 페이지 추가

**파일**: `was/static/index.html` (신규 생성)

**내용**:
- 계정 관리: 회원가입, 로그인, 잔액 조회
- 입출금: 입금, 출금
- CTF 취약점 테스트:
  - 음수 입금 공격 버튼
  - SSRF 공격 버튼
- 결제 테스트: Saga Pattern 결제

**접속 방법**:
```
http://localhost:8080/static/index.html
```

---

## 🧪 테스트 방법

### 1. Docker 재시작

```bash
cd C:\Users\wngus\quickpay-temp
docker-compose down
docker-compose up --build -d
```

### 2. 브라우저 테스트

1. 브라우저에서 `http://localhost:8080/static/test.html` 접속
2. User ID: `user1234`, Password: `user1234` 입력
3. "회원가입" 클릭 → 초기 잔액 10,000원 부여됨
4. "잔액 조회" 클릭 → 10,000원 확인
5. CTF 취약점 테스트 버튼 클릭

### 3. curl 테스트

```bash
# 회원가입
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","password":"test123"}'

# 로그인
curl -X POST http://localhost:8080/account/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","password":"test123"}'

# 잔액 조회
curl http://localhost:8080/account/balance?user_id=test123

# 음수 입금 공격
curl -X POST http://localhost:8080/account/deposit \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","amount":-5000}'

# SSRF 공격
curl "http://localhost:8080/account/internal/debug?filename=flag.txt"
```

---

## 📊 개선 효과

| 항목 | 개선 전 | 개선 후 |
|------|---------|---------|
| **회원가입 후 잔액** | 0원 | 10,000원 |
| **API Gateway 접근** | 로그인만 가능 | 전체 account API 가능 |
| **테스트 편의성** | curl/docker exec만 | 브라우저 UI 사용 가능 |
| **CTF 테스트** | 명령어 복잡 | 버튼 클릭으로 간편 |

---

## ⚠️ 주의사항

1. **보안**: PUBLIC_PATHS 확장은 CTF 교육용입니다. 프로덕션 환경에서는 절대 사용 금지
2. **초기 잔액**: 실제 서비스에서는 초기 잔액 0원 또는 제거
3. **테스트 페이지**: `/static/test.html`은 교육/테스트용으로만 사용

---

## 📋 수정 파일 목록

1. ✅ `api_gateway/app.py` - PUBLIC_PATHS 확장
2. ✅ `account/app.py` - 초기 잔액 10,000원 부여
3. ✅ `was/static/test.html` - 테스트 UI 추가 (신규)
4. ✅ `IMPROVEMENTS.md` - 개선사항 문서 (신규)

