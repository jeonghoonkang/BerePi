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
- Like htop : nvtop
  - sudo add-apt-repository ppa:flexiondotorg/nvtop
  - sudo apt install nvtop 

## NVIDIA 삭제 후 드라이버 재설치 
- dpkg -l | grep -i nvidia
- sudo apt remove --purge nvidia-*
- sudo apt autoremove

  - 다른 방법 
    - sudo apt-get remove --purge nvidia-*
    - sudo apt-get autoremove
    - sudo apt-get update

## WSL 설치
- 설치방법
  - https://velog.io/@jaehyeong/WSL2-%EC%B4%88%EA%B0%84%EB%8B%A8-%EC%84%A4%EC%B9%98-%EB%B0%8F-CUDAGPU-%EC%84%A4%EC%A0%95-%EB%B0%A9%EB%B2%95
- 주의
  - sudo cp apt_pkg.cpython-36m-aarch64-linux-gnu.so apt_pkg.so    
