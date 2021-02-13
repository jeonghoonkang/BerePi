
#도커 컴포즈, 동작 확인을 위해

## 기본 사용방법
docker-compose_simple.yml 파일 실행 
sudo docker-compose -f docker-compose_simple.yml up (-d)

sudo docker-compose ps 로 실행 컨테이너 확인
docker ps 로도 확인 가능

종료시에는 docker-compose down


## 로컬 시스템 포트 확인
sudo lsof -i -P -n | grep LISTEN
 
 
 
