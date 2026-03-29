# QuickPay 버그 수정 보고서

**날짜**: 2025-01-17
**작성자**: 김재현 (Account & Payment Service 담당)
**수정 범위**: account, payment, settlement 서비스

---

## 🔍 문제 발견

전체 프로젝트를 스캔한 결과, **서비스 간 연동 실패**로 인해 모든 기능이 작동하지 않는 문제를 발견했습니다.

### 근본 원인

1. **잘못된 서비스 이름**: `adjustment` (존재하지 않음) → `settlement` (실제 서비스)
2. **잘못된 포트 번호**: docker-compose.yml에서 모든 서비스가 `5000`번 포트로 실행되지만, 코드에서는 `8001`, `8003` 등 다른 포트 사용
3. **Docker 환경 미고려**: `localhost` 사용 (Docker 컨테이너 간 통신 불가)
4. **누락된 엔드포인트**: CTF 취약점(SSRF)에 필요한 `/settlement/internal/log_viewer` 엔드포인트 없음

---

## 🔧 수정 내역

### 1. account/app.py (계좌관리 서비스)

**파일**: `account/app.py`
**라인**: 15

**변경 전**:
```python
SETTLEMENT_SERVICE_URL = os.getenv('SETTLEMENT_SERVICE_URL', 'http://adjustment:5000')
```

**변경 후**:
```python
SETTLEMENT_SERVICE_URL = os.getenv('SETTLEMENT_SERVICE_URL', 'http://settlement:5000')
```

**수정 이유**:
- `adjustment` 서비스는 존재하지 않음 (docker-compose.yml 확인 결과)
- 실제 서비스 이름은 `settlement`
- SSRF 취약점(PDF Page 22)이 제대로 작동하려면 올바른 서비스 이름 필요

---

### 2. payment/app.py (결제 서비스)

**파일**: `payment/app.py`
**라인**: 14, 17

#### 수정 #1: Account Service URL

**변경 전**:
```python
ACCOUNT_SERVICE_URL = os.getenv('ACCOUNT_SERVICE_URL', 'http://account:8001')
```

**변경 후**:
```python
ACCOUNT_SERVICE_URL = os.getenv('ACCOUNT_SERVICE_URL', 'http://account:5000')
```

**수정 이유**:
- docker-compose.yml의 `account` 서비스는 `0.0.0.0:5000`으로 실행됨 (Line 61)
- `8001` 포트는 열려있지 않음
- 결제 시 출금 API 호출이 실패하는 원인

#### 수정 #2: Settlement Service URL

**변경 전**:
```python
ADJUSTMENT_SERVICE_URL = os.getenv('ADJUSTMENT_SERVICE_URL', 'http://adjustment:8003')
```

**변경 후**:
```python
ADJUSTMENT_SERVICE_URL = os.getenv('ADJUSTMENT_SERVICE_URL', 'http://settlement:5000')
```

**수정 이유**:
- 서비스 이름 오류: `adjustment` → `settlement`
- 포트 오류: `8003` → `5000`
- 결제 후 정산 기록 저장이 실패하는 원인

---

### 3. settlement/app.py (정산 서비스)

**파일**: `settlement/app.py`

#### 수정 #1: Account Service URL (Line 35)

**변경 전**:
```python
ACCOUNT_SERVICE_URL = "http://localhost:5002/account/deposit"
```

**변경 후**:
```python
ACCOUNT_SERVICE_URL = "http://account:5000/account/deposit"
```

**수정 이유**:
- Docker 환경에서 `localhost`는 자기 자신을 가리킴 (다른 컨테이너 접근 불가)
- 서비스 이름 `account` 사용해야 함
- 포트: `5002` → `5000`
- 정산 실행 시 계좌 입금이 실패하는 원인

#### 수정 #2: SSRF 취약점 엔드포인트 추가 (Line 119-143)

**추가된 코드**:
```python
@app.route("/settlement/internal/log_viewer", methods=["GET"])
def log_viewer():
    """
    [CTF 취약점 API - PDF Page 22]
    SSRF 공격 대상 엔드포인트
    """
    filename = request.args.get('filename', 'access.log')

    # CTF 취약점: 파일명 검증 없음
    if 'flag' in filename.lower():
        return "FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}", 200

    return f"[정산서비스 로그] {filename} 파일 내용\n...", 200
```

**추가 이유**:
- PDF Page 22의 SSRF 취약점 시나리오 구현 필요
- `account/internal/debug` → `settlement/internal/log_viewer` 프록시 흐름 완성
- CTF 플래그 획득 가능하도록 구현

---

## 📊 수정 요약

| 파일 | 수정 항목 | 변경 전 | 변경 후 |
|------|-----------|---------|---------|
| account/app.py | SETTLEMENT_SERVICE_URL | `http://adjustment:5000` | `http://settlement:5000` |
| payment/app.py | ACCOUNT_SERVICE_URL | `http://account:8001` | `http://account:5000` |
| payment/app.py | ADJUSTMENT_SERVICE_URL | `http://adjustment:8003` | `http://settlement:5000` |
| settlement/app.py | ACCOUNT_SERVICE_URL | `http://localhost:5002/...` | `http://account:5000/...` |
| settlement/app.py | 신규 엔드포인트 | 없음 | `/settlement/internal/log_viewer` |

---

## ✅ 예상 효과

### 정상 작동 가능한 기능

1. **계좌 관리 서비스**:
   - ✅ 회원가입
   - ✅ 로그인
   - ✅ 잔액 조회
   - ✅ 입금 (음수 입금 취약점 포함)
   - ✅ 출금
   - ✅ SSRF 디버그 API

2. **결제 서비스**:
   - ✅ 결제 처리 (Saga Pattern)
   - ✅ 계좌 출금 연동
   - ✅ 정산 기록 저장 연동
   - ✅ 보상 트랜잭션 (실패 시 rollback)

3. **정산 서비스**:
   - ✅ 거래 내역 저장
   - ✅ 주기적 정산
   - ✅ 계좌 입금 연동
   - ✅ SSRF 취약점 엔드포인트

### CTF 취약점 (PDF 기준)

1. **✅ PDF Page 14 - 음수 입금 허용**:
   - `POST /account/deposit` with `{"amount": -50000}`
   - 서버 사이드 검증 부재로 출금 가능

2. **✅ PDF Page 22 - SSRF via debug endpoint**:
   - `GET /account/internal/debug?filename=flag.txt`
   - 정산서비스 내부 파일 읽기 가능
   - FLAG 획득: `FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}`

---

## 🧪 테스트 계획

### 1. Docker Compose 전체 실행
```bash
cd quickpay-temp
docker-compose down -v
docker-compose up --build
```

### 2. 기본 기능 테스트
```bash
# 회원가입
curl -X POST http://localhost:8080/account/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","password":"test123"}'

# 로그인
curl -X POST http://localhost:8080/account/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user1","password":"password"}' \
  -c cookies.txt

# 잔액 조회
curl http://localhost:8080/account/balance?user_id=user1

# 결제 (Saga Pattern)
curl -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user1","merchant_id":"M001","amount":1000}'
```

### 3. CTF 취약점 테스트

#### 취약점 #1: 음수 입금
```bash
# 초기 잔액 확인
curl http://localhost:8080/account/balance?user_id=user1
# 예상 결과: {"balance": 50000}

# 음수 입금 공격
curl -X POST http://localhost:8080/account/deposit \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user1","amount":-50000}'

# 최종 잔액 확인
curl http://localhost:8080/account/balance?user_id=user1
# 예상 결과: {"balance": 0}  → 50,000원 출금됨!
```

#### 취약점 #2: SSRF
```bash
# FLAG 획득
curl "http://localhost:8080/account/internal/debug?filename=flag.txt"
# 예상 결과: FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}

# Path Traversal 시도
curl "http://localhost:8080/account/internal/debug?filename=../../etc/passwd"
```

---

## 🚨 주의사항

1. **환경 변수 우선순위**: `.env` 파일이나 docker-compose.yml의 `environment` 섹션에서 URL을 override하면 기본값이 무시됩니다.
2. **포트 일관성**: 모든 내부 서비스는 `5000`번 포트 사용 (docker-compose.yml의 `command` 참조)
3. **서비스 이름**: Docker Compose 네트워크에서 서비스 이름이 호스트명이 됩니다 (`account`, `payment`, `settlement`)

---

## 📝 다음 단계

1. ✅ 로컬 테스트 완료 후
2. ✅ GitHub에 커밋 (`[FIX] 서비스 간 연동 오류 수정 및 SSRF 엔드포인트 추가`)
3. ✅ 팀원들에게 수정사항 공유
4. ✅ 통합 테스트 진행
