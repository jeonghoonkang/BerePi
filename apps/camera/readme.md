
## 개발 목표

- 라즈베리파이 카메라로 촬영한 사진을 AI 영상 인식 기능 S/W에 입력하여 지능적인 판단 결과를 리턴 받는다
- Google Vision API에 입력하고, 해당 지능처리 결과를 JSON 으로 회신 받아, 원하는 데이터 필드를 TSDB에 입력한다
- 데모용 사진 : https://github.com/jeonghoonkang/BerePi/tree/master/apps/camera/dataset

참고 내용

- 라즈베리파이 카메라 원격 제어, 웹캠  <http://jamiej7.wixsite.com/anpr-on-raspberry-pi
- 구글 API 사용 NODE JS http://bcho.tistory.com/1075
- 구글 API 사용 Python http://www.hardcopyworld.com/ngine/aduino/index.php/archives/2736


## 시각지능 분야 IoT 시스템 기술 통합 방법
  - 스마트미터 적용하여 문자를 인식함
  - 시각 지능 성능을 높이기위해 여러대의 카메라를  동기화하여 데이터를 수집함
  - 특정상황을 연출하고 그에 해당하는 다각도 영상을 수집, 저장처리함
  - 왜 딥러닝을 위한 데이터 수집을 직접 수행해야 하는가?
    - 대부분의 경우 딥러닝을 위한 충분한 데이터가 없다
      - 구글같은 대기업은 서비스 시스템 내에 많은 데이터가 있으나
      - 아직 안정적인 데이터가 확보되지 않은 대부분의 중소기업은 인공지능 서비스를 시작하기 위해서는 자체적으로 데이터를 확보해야 함
      - 그러면, 데이터 보유기관이 없는 중소기업은 자신들이 데이터를 수집해서 확보해야 한다. 이를 기반으로 신규서비스 구현 가능성을 증명해야 함

## 카메라 동작  

- 카메라 촬영, 스트리밍, 수신 영상 웹기반 표출의 기본기능 제공
- 움직임(모션)이 발생한 경우 촬영 기능 
- 웹으로 촬영 하거나, 자동 촬영되어 있는 파일을 브라우징 할 수 있는 갤러리

## timelaps, motion detection, low light
  - https://github.com/pageauc/pi-timolo

## Raspi NoIR Camera (with LED)
  - https://www.raspberrypi.org/learning/infrared-bird-box/worksheet/

## Machine Vision info.
  - ImageNet You Tube
    - It gives outline understanding of Vision Intelligence
    - https://youtu.be/40riCqvRoMs


### camera module 설정
- ''/boot/config.txt'' 에서 ''start_x=1''로 수정하고 재부팅

- pi-cam_with_visionAPI.py 설명
- 소스 코드 내에 pic 변수에 저장될 위치와 파일명으로 저장한다.
- 실행
- ''$ python pi-cam_with_visionAPI.py /directory/of/image.jpg'' 처럼 위치와 파일명을 명세하면 해당 파라미터로 저장되며 파라미터 없이 실행하면 소소코드 내에 저장된 default위치와 파일명으로 저장된다.


### USB Camera 설치 방법
- 로지텍 카메라 설치 for 라즈베리파이
  - https://webnautes.tistory.com/909
  

## Too many files, 인수가 너무 길어지는 경우
- <code> find /home/pi/cam_data/ -name "*.jpg" -print0 | xargs -0 ls </code>
