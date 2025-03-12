### Apple Metal에서 python pytorch 설치 방법
- M1 이상의 애플실리콘 사용 모델
#### 설치방법 
- brew install python3
- 이후 pip3 install {pkg} 는 에러 발생
  - EXTERNALLY MANAGED
- 가상환경 실행하여, pip3 사용 가능하도록 준비
  - python3 -m  env {경로, devel_opemnt/mps}
  - source myenv/bin/activate
- PyTorch 설치
  - pip3 install torch torchvision torchaudio
