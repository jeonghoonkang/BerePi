- Image 설치 : 2018년 5월 버전
  - Stretch 이미지
  - 2017년 8월 이미지 파일 릴리즈
    - 2018년 4월 RaspberryPi 3 B+ 발표로 새롭게 적용
    
- Image 설치 : 2018년 4월 버전, 최근 버전 설치 
<pre> http://125.140.110.217/open/2018-05-BerePi-stretch-4G-001.img </pre>
<pre> http://125.140.110.217/open/2018-05-BerePi-stretch-4G-001.img.gz </pre>

- 설치후, sudo raspi-config 로 Hostname 을 PLUG-1001 등으로 설정해야 함
  - 1 : 1 차실증
  - 0 : 실증 가구 번호 백단위
  - 0 : 실증 가구 번호 십단위
  - 1 : 실증 가구 번호 일단위
  - 총 300개 내외의 실증을 진행할 예정임

- 플러그의 아이디
  - 1001XX : XX 플러그 아이디  

- HOSTName 변경하고 리붓하면, STALK 서버에 연결됨
  - 참고 : KEMCO stalk 
 <pre> https://github.com/321core/EnergyManagementSystem/blob/master/README.md </pre>
- sudo raspi-config 를 실행하여, 1) SD 메모리 저장 공간 확장을 실행해 줌
  - 용량 확인 `df -h` → 용량 확인  
  

  First | Second 
------------ | -------------
Content from cell 1 | Content from cell 2
Content in the first column | Content in the second column

