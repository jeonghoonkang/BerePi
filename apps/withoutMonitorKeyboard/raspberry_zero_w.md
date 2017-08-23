# 라즈베리파이 제로 W

## 1. 설치
  
### 1. microSD 카드에 라즈비안 이미지 설치
### 2. microSD 루트에 파일 생성
  1) 내용없이 ssh 파일 생성
  2) 다음 내용으로 wpa_supplicant.conf 파일 생성
    
```conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
  network={
  ssid="AP_name"
  psk="AP_password"
}
```

### 3. 부팅
### 4 ssh 접속

```bash
ssh pi@raspberrypi.local
```
