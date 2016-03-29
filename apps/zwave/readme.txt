#### 실행방법
 
  - cd /home/pi/install/openzwave-control-panel/
  - ./ozwcp -p 55555
  - Z-Wave 하드웨어를 USB 에 Plug 시킴
  
  - Web Browser 로 http://IP:55555 로 접근하면 웹페이지 보임
  - 좌측 Controller 박스에
    - /dev/ttyACM0 입력함
    - Initialzie 버튼 누름
    - 이렇게 되면. 아랫쪽 Devices 에. 1. LBR Static Controller id=0000 보여야 함
  
  - 페어링 방법
    - 웹페이지에서 중간 박스(Controler)에 Add Device 를 선택하고, Go 버튼을 누름
    - 즉시, 스마트플러그의 측면 버튼을 5초간 눌러주면. 버튼이 깜빡거리기 시작함
    - 10초 쯤 후에.. 웹페이지에 Devices에 플러그가 보임, 페이링 완료
    
  - 마우스로, 제어할 플러그를 선택하면 아래에 Current Values 들이 보여짐
    - Switch 항목을 off / on 을 토글하면 플러그가 원격 제어됨
    
  - https://github.com/jeonghoonkang/BerePi/blob/master/apps/zwave/zwave-control-panel-run.png
      
#### 개발관련
  - /home/pi/install/openzwave-control-panel/ 안에 html 코드와 Ajax 코드들이 있음


#### 설치참고

https://www.domotiga.nl/projects/domotiga/wiki/Z-Wave_OpenZWave#Configuration

1.     open-zwave-read-only 를 사용하여 server 연동 
2.     Library : libopenzwave.so
3.     예제 Source 는 아래 경로에 들어있습니다.
경로 : open-zwave-read-only/cpp/examples

참고 : linux -> MinOZW
       Windows -> windows

https://www.domotiga.nl/projects/domotiga/wiki/DomotiGa_Installation
static controller

open-zwave-control-panel compile
-Wno-deprecated-declarations
