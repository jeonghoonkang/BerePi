### 설치
  - www.docker.com
  - 도커 이미지는 hub.docker.com 에서 pull을 실행하여 다운로드 함
  
### 실행
  - docker run -it --name {내가 정하는 실행이름} {실행할 이미지 이름} /bin/bash
  - docker images : 이미지 리스트 보여줌
  - docker ps -a : 컨테이너 리스트 보여줌
  - docker start {내가 정한 실행이름 }
  - docker attach {내가 정한 실행이름 }

### 컨테이너 삭제
  - 컨테이너 : 도커 이미지가 실행되어 관리 중인 (실행중인) 이미지
  -

### Docker 네트워크
  - docker network ls
  - docker run -it --name

### Docker 관련 명령어 (참고)
  - docker run 컨테이너를 생성
  - docker stop 컨테이너를 정지
  - docker start 컨테이너를 다시 실행
  - docker restart 컨테이너를 재가동
  - docker rm 컨테이너를 삭제
  - docker kill 컨테이너에게 SIGKILL을 보낸다. 이에 관련된 이슈가 있음
  - docker attach 실행중인 컨테이너에 접속
  - docker wait 컨테이너가 멈출 때까지 블럭
