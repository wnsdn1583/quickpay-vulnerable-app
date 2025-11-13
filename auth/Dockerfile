Python 3.9 Slim 이미지 사용

FROM python:3.9-slim

작업 디렉토리 설정

WORKDIR /usr/src/app

requirements.txt 복사 및 종속성 설치

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

애플리케이션 파일 복사

COPY app.py .
COPY db/auth.db db/

데이터베이스 디렉토리 생성 (실행 시 필요)

RUN mkdir -p db

Flask 애플리케이션 실행

기본 포트는 5000번입니다.

EXPOSE 5000
CMD [ "flask", "run", "--host", "0.0.0.0", "--port", "5000" ]
