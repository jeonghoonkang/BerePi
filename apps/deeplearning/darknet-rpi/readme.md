# RPI 3B+ install Darknet-nnpack 

## 설치 참고 링크
  [darknet-nnpack](https://github.com/digitalbrain79/darknet-nnpack)<br>
  [Raspberry pi YOLO Real-time Object Detection](http://raspberrypi4u.blogspot.com/2018/10/raspberry-pi-yolo-real-time-object.html)<br>
  [카메라 추가 테스트](https://webnautes.tistory.com/929)<br>
  
## YOLO와 Camera 연동
  ### Test 환경<br>
  &nbsp; <img width="600" src="./images/testenv.png"></img><br>
  ### run_dc.py program flow<br>
  &nbsp; <img width="600" src="./images/flow.png"></img><br>
  
## DB 구축
  ## Server 환경
  &nbsp; ssh windarin@125.140.110.217 -p 7771<br>
  &nbsp; [MySQL 설치 방법](./MySQL_Install.md)<br>
  
  
## 설치 설명 파일
  [설치&동작 설명파일 InstallRun.md](https://github.com/jeonghoonkang/BerePi/blob/master/apps/deeplearning/darknet-rpi/InstallRun.md)<br>
  [YOLO 설정파일 커스텀 custom-yolo.md](https://github.com/jeonghoonkang/BerePi/blob/master/apps/deeplearning/darknet-rpi/custom-yolo.md)<br>

## 속도 향상 방법 테스트
  [사진 크기에 따른 속도 변화](https://github.com/jeonghoonkang/BerePi/tree/master/apps/deeplearning/darknet-rpi/runtime_test/readme.md)<br>
  
## 오류 리포트
  1. -- 정면은 잘 찾음<br>
  &nbsp; <img width="600" src="./images/error_predictions2.jpg"></img><br>
  &nbsp; -- 현재 24개월 유아는 옆모습은 못찾음<br>
  &nbsp; <img width="600" src="./images/error_predictions3.jpg"></img><br>
  &nbsp; -- 1<br>
  &nbsp; <img width="600" src="./images/error/0616_1.jpg"></img><br>
  &nbsp; -- 2<br>
  &nbsp; <img width="600" src="./images/error/0616_2.jpg"></img><br>
  &nbsp; -- 3<br>
  &nbsp; <img width="600" src="./images/error/0616_3.jpg"></img><br>
  &nbsp; -- 4<br>
  &nbsp; <img width="600" src="./images/error/0616_4.jpg"></img><br>
  &nbsp; -- 5<br>
  &nbsp; <img width="600" src="./images/error/0616_5.jpg"></img><br>
  
  
## 기타 
