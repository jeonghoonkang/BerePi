
# 도커 컴포즈, 동작 확인을 위해

## 기본 사용방법
docker-compose_simple.yml 파일 실행 
sudo docker-compose -f docker-compose_simple.yml up (-d)

sudo docker-compose ps 로 실행 컨테이너 확인
docker ps 로도 확인 가능

종료시에는 docker-compose down


## 로컬 시스템 포트 확인
sudo lsof -i -P -n | grep LISTEN
 
### 참고, 컨테이너 정보 확인 방법 (docker-compose 실행 위치 정보 확인 방법)
docker inspect 로 실행 위치 검색

<pre>
$ sudo docker ps

[sudo] password for: 
CONTAINER ID   IMAGE                                    COMMAND                  CREATED        STATUS       PORTS                                                                      NAMES
521eca80ac26   teslamate/teslamate:latest               "tini -- /bin/sh /en…"   7 months ago   Up 5 weeks   0.0.0.0:4000->4000/tcp, :::4000->4000/tcp                                  teslamate_teslamate_1
0d3563b90198   postgres:12                              "docker-entrypoint.s…"   7 months ago   Up 5 weeks   5432/tcp                                                                   teslamate_database_1
eeb030fbb47e   teslamate/grafana:latest                 "/run.sh"                7 months ago   Up 5 weeks   0.0.0.0:3000->3000/tcp, :::3000->3000/tcp                                  teslamate_grafana_1
badef534b5cf   eclipse-mosquitto:1.6                    "/docker-entrypoint.…"   7 months ago   Up 5 weeks   0.0.0.0:1883->1883/tcp, :::1883->1883/tcp                                  teslamate_mosquitto_1

(중요부분 0d3563b90198 는 머신마다 다릅니다. 위 출력에서 찾으셔야 합니다. 0d3563b90198   postgres:12)

$ docker inspect 0d3563b90198 | grep com.docker.compose 

                "com.docker.compose.config-hash": "6e8097c5637a4c80e9bf7d8213a706ea489c7f9",
                "com.docker.compose.container-number": "1",
                "com.docker.compose.oneoff": "False",
                "com.docker.compose.project": "teslamate",
                "com.docker.compose.project.config_files": "docker-compose.yml",
                "com.docker.compose.project.working_dir": "/home/~~~~/teslamate",
                "com.docker.compose.service": "database",
                "com.docker.compose.version": "1.25.0"
 
</pre>
