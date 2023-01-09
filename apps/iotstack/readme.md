## IoTStack
- IoT 서비스에 필요한 다양한 컨테이너 실행을 관리할 수 있음

## 준비
  - Raspberry Pi 3B or 4B
    > (Raspberry Pi Zero W2 는 RAM 용량이 적어 제한적으로 사용 가능)
  - Raspbian Bullseye
  ```bash
  sudo apt update
  sudo apt upgrade -y
  sudo apt install -y curl
  ```

## 설치

  ```bash
  curl -fsSL https://raw.githubusercontent.com/SensorsIot/IOTstack/master/install.sh | bash
  cd ~/IOTstack
  sudo ./menu.sh
  ```
