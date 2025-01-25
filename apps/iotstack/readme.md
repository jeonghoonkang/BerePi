## IoTStack

- IoT 서비스에 필요한 다양한 컨테이너 실행을 관리할 수 있음
- 메인 리포 : https://github.com/SensorsIot/IOTstack
- https://sensorsiot.github.io/IOTstack/Basic_setup/Default-Configs/

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

- `Build Stack` 엔터

<img title="" src="https://user-images.githubusercontent.com/4587330/211264293-50299f86-7bd9-48c1-a7f7-c36c471b35fa.png" alt="" width="254">

- `wireguard` 스페이스
- [Enter] 하면 설치 시작
- 설치 진행

<img title="" src="https://user-images.githubusercontent.com/4587330/211264295-7b7cfe6f-ea8d-417c-828a-f90c4f95f2e2.png" alt="" width="411">



## 설정

```bash
cd ~/IOTstack/
vim docker-compose.yml
```

```yaml
# Timezone 설정
TZ=Asia/Seoul

# Domain 설정 (DDNS 사용할 경우, DDNS 도메인 사용)
SERVERURL=***.duckdns.org

# cient 장치 설정 (숫자 "PEERS=n" 도 가능하나, 취약점 때문에 비추)
PEERS=laptop,PC,iphone,android

# DNS 설정, 
#   - auto 는 라즈베리파이 DNS 설정 사용
#   - DNS 서버도 설정할 수 있음 ex) 8.8.8.8
PEERDNS=auto
```

## 클라이언트 접속

> wireguard 는 전용 클라이언트를 사용한다.

[Installation - WireGuard](https://www.wireguard.com/install/)를 설치한다.
