# CGI 를 이용한 디바이스 정보 확인 웹페이지
## 웹접근 방법
- `http://IP/gw` 에 접속하면 apache 서버는 index.html 을 전송
- 웹브라우저는 전송된 index.html 을 표시
- 대부분 /var/www/html 에 있는 index.html 이 대상 파일임
## CGI for Python
- /usr/lib/cgi-bin 디렉토리에 있는 *.py 실행 코드들이 위치함
- `http://IP/gw/index.html` 페이지를 활용하여, `http://IP/cgi-bin/실행할파일.py` 로 링크, 연계하여 실행하도록 구현
