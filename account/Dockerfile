FROM python:3.11-slim

WORKDIR /app

# SSH 및 기타 종속성 설치
RUN apt-get update && apt-get install -y openssh-server
RUN mkdir -p /var/run/sshd

# 루트 비밀번호 설정
RUN echo 'root:mypassword1234' | chpasswd

# SSH 설정 수정
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl 
    
# 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY app.py .

# 시작 스크립트 생성 및 실행 권한 부여
RUN echo '#!/bin/bash' > /start.sh && \
    echo 'service ssh start' >> /start.sh && \
    echo 'gunicorn -b 0.0.0.0:5000 -w 4 --access-logfile - --error-logfile - app:app' >> /start.sh
RUN chmod +x /start.sh

# 포트 노출
EXPOSE 5000 22

# 시작 스크립트로 실행
CMD ["/start.sh"]
