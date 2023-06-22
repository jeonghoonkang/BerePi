# INSTALL

## 1. INSTALL pyTorch

### 1-1) Requirements

  - Raspbian **64bit**
  - python >3.8

### 1-2) USE wheel

  - get a fresh start
  - `sudo apt-get update`
  - `sudo apt-get upgrade`

  - install the dependencies
  - `sudo apt-get install -y python3-pip libjpeg-dev libopenblas-dev libopenmpi-dev libomp-dev`

  - above 58.3.0 you get version issues
  - `sudo -H pip3 install setuptools==58.3.0`
  - `sudo -H pip3 install Cython`

  - install pyTorch 1.13.0 

    - Bullseye
    - `sudo -H pip3 install ./whl/torch-1.13.0a0+git7c98e70-cp39-cp39-linux_aarch64.whl`
  
    - Buster 
    - `sudo -H pip3 install ./whl/torch-1.13.0a0+git7c98e70-cp37-cp37m-linux_aarch64.whl`


## 2. INSATALL Whisper

### 2-1) Install ffmpeg

  - `sudo apt-get install -y ffmpeg`

