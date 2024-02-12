### 리버스 프록시, Reverse Proxy 설정
#### 서버 여러개를 도메인 구성
- 준비 : 도메인 2개, 웹서버 2개

https://img1.daumcdn.net/thumb/R1280x0/?scode=mtistory2&fname=https%3A%2F%2Fblog.kakaocdn.net%2Fdn%2FbcNr4v%2Fbtr8ayv8XGv%2Fs3tbA5zC6ehKC2toy7gE4k%2Fimg.png![image](https://github.com/jeonghoonkang/BerePi/assets/4180063/4b786e66-b984-472e-9ec0-f9ac115a8329)

<code>
  
</code>



-----

- 예전 작성
  - location 관련, nginx는 클라이언트가 접근한 path를 보고, 가장 적합한 location의 블럭으로 요청을 보내서 처리하게 된다. 여러 개가 일치할 경우 우선 순위가 있는데, 다음과 같다.

<pre>
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
</pre>

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


