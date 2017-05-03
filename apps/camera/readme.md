
#### 카메라 동작  
  - 기본 동작 완료    
  - 움직임(모션)이 발생한 경우만 촬영하도록 기능 추가 진행   
  - 웹  기반으로 동작하도록  진행  
  - 웹으로 촬영 하거나, 자동 촬영되어 있는 파일을 브라우징 할 수 있는 갤러리

#### timelaps, motion detection, low light
  - https://github.com/pageauc/pi-timolo

#### Raspi NoIR Camera (with LED)
  - https://www.raspberrypi.org/learning/infrared-bird-box/worksheet/

#### Machine Vision info.
  - ImageNet You Tube
    - It gives outline understanding of Vision Intelligence
    - https://youtu.be/40riCqvRoMs


### camera module 설정
- ''/boot/config.txt'' 에서 ''start_x=1''로 수정하고 재부팅

- pi-cam_with_visionAPI.py 설명
- 소스 코드 내에 pic 변수에 저장될 위치와 파일명으로 저장한다.
- 실행
- ''$ python pi-cam_with_visionAPI.py /directory/of/image.jpg'' 처럼 위치와 파일명을 명세하면 해당 파라미터로 저장되며 파라미터 없이 실행하면 소소코드 내에 저장된 default위치와 파일명으로 저장된다.
