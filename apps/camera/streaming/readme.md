# RaspberryPi cammera streaming
## setup & configure camera
- sudo apt-get install python3-picamera

## network setup for streaming
## run streaming code
- run python file [run_streaming.py](run_streaming.py) which is from https://randomnerdtutorials.com/video-streaming-with-raspberry-pi-camera/

## Network Detouring
### 문제점
- 가정내 설치한 카메라의 영상을 스트리밍 하여 스마트폰으로 전송하기 위해서는, 인터넷 공유기에서 카메라에 대한 Server Port 를 직접 연결할 수 있도록 설정해 주어야 한다
  - 설정할 수 있는 사용자는 큰 문제가 없음
  - 설정을 못하는 사용자들은 공유기 설정없이 카메라 스트링밍 영상을 핸드폰으로 수신할 수 있도록 해야한다
- 카메라 스트리밍을 어디에서든 쉽게 연결하기 위한 조건들
  - 서버 포트는 기본동작 해야함
  - 서버 포트 연결을 못하는 경우는, 카메라가 클라이언트, 사용자 핸드폰이 서버로 동작하면 됨
    - 카메라가 사용자 서버 (핸드폰, PC 등)의 IP 주소를 알아낼 수 있어야 함
      - 앱의 경우는 서버 S/W 기능을 구현하여 내장할 수 있음
      - PC 윈도우나, MAC OSX 같은 경우는 웹브라우저로 동작할 수 있어야 함
      
    

