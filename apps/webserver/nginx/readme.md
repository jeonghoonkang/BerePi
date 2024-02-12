- location 관련 
  - nginx는 클라이언트가 접근한 path를 보고, 가장 적합한 location의 블럭으로 요청을 보내서 처리하게 된다. 여러 개가 일치할 경우 우선 순위가 있는데, 다음과 같다.

1. = (exactly), 정확히 일치할 경우
ex) location = /

2. ^~ (priority prefix match), 우선 순위를 부여하고, 앞 부분이 일치할 경우. 여러 개가 충돌할 경우 긴 것이 적용(longest first)
ex) location ^~ /api

3. ~ (regex match with sensitive case), 대소문자를 구분하는 정규표현식 일치할 경우
ex) location ~ /path
4. *~ (regex math with insensitive case), 대소문자를 무시하는 정규표현식 일치할 경우
ex) location *~ /path

5. / (prefix match), 앞 부분이 일치할 경우, 여러 개가 충돌할 경우 긴 것이 적용(longest first)
ex) location /

- 위 사용법에 따라 location을 작성하여 주면, nginx.conf에 설정한대로 reverse proxy가 동작한다. 만일 아래와 같이 작성하면, /api로 시작하는 요청은 5000번 포트로, 그 외에는 8080번 포트로 보내게 된다.
<pre>
location / {
    proxy_pass http://127.0.0.1:8080;
}

location /api {
    proxy_pass http://127.0.0.1:5000;
}
</pre>

<pre>

#sudo vi /etc/nginx/sites-available/default
 
server {
    ...
 
    # sub directory setting
    location ^~ /asia {
        proxy_pass http://localhost/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
 
    ...

</pre>


