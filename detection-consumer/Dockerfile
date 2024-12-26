# Base 이미지 선택 
FROM python:3.11

# 필요한 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 로컬 파일 복사
COPY . /app

# 쉘 스크립트 실행 권한 부여
RUN chmod +x /app/detection-starts.sh

# 필요한 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt
