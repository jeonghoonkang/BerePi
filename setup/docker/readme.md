
### 설치
  - www.docker.com
  - 도커 이미지는 hub.docker.com 에서 pull 명령을 실행하여 다운로드 함
  
### 실행
  - docker run -it --name {내가 정하는 실행이름} {실행할 이미지 이름} /bin/bash
  - docker images : 이미지 리스트 보여줌
  - docker ps -a : 컨테이너 리스트 보여줌
  - docker start {내가 정한 실행할 컨테이너 이름 }
  - docker attach {내가 정한 실행할 컨테이너 이름 }
  - docker exec -it {내가 정한 컨테이너 실행 이름} bash
  - To detach from the container1 container and leave it running, use the keyboard sequence CTRL-p CTRL-q

### 컨테이너 저장 및 백업, 배포
  - 컨테이너 : 도커 이미지가 실행되어 관리 중인 (실행중인) 이미지
  - 컨테이터 커밋
    - docker commit dtinyos python_tos:001
                    {실행중인 컨테이너} {생성할 이미지이름 : 태그}
  - 백업
    - docker save oracle_backup > /backup/oracle_xx.tar
                  {이미지이름}
  - 복원
    - docker load < /backup/oracle_xx.tar 

### Docker 네트워크
  - docker network ls
  - docker network inspect
  - docker run -it -p 6622:22 --name {내가 정하는 실행이름} {실행할 이미지 이름} /bin/bash
    - 6622 컨테이너 포트, 22 localhost 포트
    - (예) ssh root@localhost -p 22 로 접근하면 컨테이너로 연결

### Docker 관련 명령어 (참고)
  - docker run 컨테이너 생성
  - docker stop 컨테이너 정지
  - docker start 컨테이너 다시 실행
  - docker restart 컨테이너 재가동
  - docker rm 컨테이너 삭제
  - docker rmi 이미지 삭제
  - docker kill 컨테이너에게 SIGKILL을 보낸다. 이에 관련된 이슈가 있음
  - docker attach 실행중인 컨테이너에 접속
  - docker wait 컨테이너가 멈출 때까지 블럭

#### 도커 장단점 내용
  - 도커로 서버를 운영하면 현재 서비스중인 환경을, 신속하게 복사해서 업그레이드 하고,
    업그레이드가 끝났을때 바로 새로운 서비스 환경(컨테이너)로 전환이 가능함
    - https://subicura.com/2016/06/07/zero-downtime-docker-deployment.html


#### Sample
  - Creates a static mapping between port 8082 of the container host and port 80 of the container.
  - C:\> docker run -it -p 8082:80 windowsservercore cmd

##### Docker 세부 설정 내용
  - BASH 사용 준비
    - apt-get update

  - SSH 서버
    - apt-get install openssh-server
      - vi /etc/ssh/sshd_config
        - PermitRootLogin  without-password 부분을
        - PermitRootLogin  yes 로 변경

  - 한글사용 (Locale)
    - apt-get install locales
      - export LANGUAGE=ko_KR.UTF-8
      - export LANG=ko_KR.UTF-8
      - locale-gen ko_KR ko_KR.UTF-8
      - update-locale LANG=ko_KR.UTF-8
      - dpkg-reconfigure locales
        - 선택. 286 ko_KR.UTF-8
  - Xmanager 설정
    - xfce4-terminal
    - gnome-terminal --geometry=80x48
      - child 창 생성실패로 matplotlib 사용에 적합하지 않음
    
