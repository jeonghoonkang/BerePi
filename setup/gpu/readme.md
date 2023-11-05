## GPU (NVIDIA)
- 그래픽카드 및 설치 가능한 드라이버 확인
  - ubuntu-drivers devices
- 현재 사용중인 그래픽카드 확인 (gpu 확인)
  - lshw -numeric -C display
  - lspci | grep -i nvidia

## 드라이버 설치
- sudo ubuntu-drivers autoinstall
- (수동) sudo apt install nvidia-driver-450
### PPA 저장소 사용 설치
- sudo add-apt-repository ppa:graphics-drivers/ppa

## 설치 후 확인
- 그래픽카드 및 설치 가능한 드라이버 확인
  - ubuntu-drivers devices
- 현재 사용중인 그래픽카드 확인
  - lshw -numeric -C display
  - lspci | grep -i nvidia
- 설치
  - sudo add-apt-repository ppa:graphics-drivers/ppa
  - sudo apt update
  - sudo apt install nvidia-driver-xxx
- 확인
  - nvidia-smi
  - 상시 모니터링 : watch -d -n 0.5 nvidia-smi

## NVIDIA 삭제 후 드라이버 재설치 
- dpkg -l | grep -i nvidia
- sudo apt remove --purge nvidia-*
- sudo apt autoremove

  - 다른 방법 
    - sudo apt-get remove --purge nvidia-*
    - sudo apt-get autoremove
    - sudo apt-get update

