FROM python:3.11-slim

WORKDIR /app

# 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY app.py .

# 포트 노출
EXPOSE 8001

# Gunicorn으로 실행
CMD ["gunicorn", "-b", "0.0.0.0:8001", "-w", "4", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
