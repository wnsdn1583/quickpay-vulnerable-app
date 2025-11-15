FROM python:3.11-slim

#작업 디렉토리를 /usr/src/app으로 설정합니다.
WORKDIR /usr/src/app

#requirements.txt를 복사하고 종속성을 설치합니다.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

#db 디렉토리 생성 및 db 파일 복사 (db 파일은 app.py가 실행될 때 필요)
COPY 명령 실행 전에 폴더를 미리 만들어 둡니다.

RUN mkdir -p db
COPY db/auth.db db/

#메인 애플리케이션 파일을 복사합니다.
COPY app.py .

#Flask 애플리케이션이 5000번 포트를 사용하도록 선언합니다.
EXPOSE 5000

#Gunicorn을 사용하여 애플리케이션을 실행합니다. (프로덕션 환경용)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
