# Docker compose installation
## official installation step

### Docker V1, V2 compatibility
  - Window, Mac 버전의 Docker 에 내장 (추가 설치 필요없음)
  - 실행 명령어 내장 (`docker-compose` → `docker compose`)
  - 일부 명령어 삭제 (참조: https://docs.docker.com/compose/cli-command-compatibility/)
  - 삭제 명령어
    ```
    compose ps --filter KEY-VALUE
    compose rm --all
    compose scale
    ```

### Install docker compose V1
  - https://docs.docker.com/compose/install/
    ```bash
    sudo curl -L "https://github.com/docker/compose/releases/download/1.25.4/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
    $ docker-compose --version
    ```
### Install docker compose V2
  - https://docs.docker.com/compose/install/linux/
    ```bash
    sudo apt-get update
    sudo apt-get install docker-compose-plugin
    ```

<pre>
(EXAMPLE)

$ docker run -it --rm \
    --name db \
    -e POSTGRES_DB=djangosample \
    -e POSTGRES_USER=sampleuser \
    -e POSTGRES_PASSWORD=samplesecret \
    postgres:9.6.1

$ docker run -it --rm \
    -p 8000:8000 \
    --link db \
    -e DJANGO_DB_HOST=db \
    -e DJANGO_DEBUG=True \
    django-sample \
    ./manage.py runserver 0:8000

</pre>
    
