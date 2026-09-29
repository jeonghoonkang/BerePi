#!/bin/bash
set -e

echo "=== Pironman 5 드라이버 설치 시작 ==="

# 1. 패키지 목록 업데이트 및 필수 의존성 설치
echo "[1/4] 필수 패키지 설치 중..."
sudo apt update
sudo apt install -y git python3-pip python3-setuptools python3-smbus

# 2. 작업 디렉토리 이동 및 저장소 클론
echo "[2/4] Pironman 5 소스코드 다운로드 중..."
cd "$HOME"
if [ -d "pironman5" ]; then
    echo "기존 pironman5 디렉토리를 제거합니다."
    rm -rf pironman5
fi
git clone https://github.com/sunfounder/pironman5.git

# 3. 드라이버 설치 진행 (install.sh 직접 실행)
echo "[3/4] 드라이버 설치 시작..."
sudo bash "$HOME/pironman5/install.sh"

echo "=== [4/4] 설치 완료 ==="
echo "시스템을 재부팅해야 설정이 완전히 적용됩니다."
read -r -p "지금 재부팅하시겠습니까? (y/n): " choice
case "$choice" in
    y|Y ) sudo reboot;;
    n|N ) echo "나중에 'sudo reboot'로 직접 재부팅해 주세요.";;
    * ) echo "잘못된 입력입니다. 재부팅을 취소합니다.";;
esac
