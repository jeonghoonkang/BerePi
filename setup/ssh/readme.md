
#### 키 관리 방법, 자동 로그인,ssh key

1. ssh-keygen (ssh client)
1. cat ~/.ssh/id_rsa.pub | ssh -p {포트번호} {USERNAME@IP-ADDRESS}    'cat >> /home/USER/.ssh/authorized_keys' (엔터옆 
   키)

<pre>
tinyos:NUC:~$ssh-keygen
Generating public/private rsa key pair.
Enter file in which to save the key (/home/tinyos/.ssh/id_rsa):
Enter passphrase (empty for no passphrase):
Enter same passphrase again:
Your identification has been saved in /home/tinyos/.ssh/id_rsa.
Your public key has been saved in /home/tinyos/.ssh/id_rsa.pub.
The key fingerprint is:
SHA256:~~H2h/~~~~~~~~~~~~ tinyos@NUC
The key's randomart image is:
+---[RSA 2048]----+|
      o+.oo oo..  ||
      o .E..+oo . ||
     o + . o.o o  ||
      * . = . +   ||
       ~~~~~~~~.  ||
      . * O + o . ||
         o = . o .||
            ... = ||
              o*B..|
+----[SHA256]-----+
</pre>


### 키 변경되었을 경우 (ssh -R) ssh key 변경 (Mac OSX), ssh문제 
- ssh-keygen -f "/home/tinyos/.ssh/known_hosts" -R "10.0.0.117"
- ssh-keygen -f "/home/tinyos/.ssh/known_hosts" -R "[keties.iptime.org]:60000"
- ssh key remove
- '-f' 옵션 output 파일 '-R' 옵션은 삭제할 문자, "따옴표" 사용 필요 

### 초기설치 후 에러
- connection reset by 10.10.10.10 port 22 라고 나오는 경우
- sudo ssh-keygen -A

### 서버 실행 
- systemctl enable ssh.service

### ssh 키 복사 방법
- ssh-copy-id -i ~/.ssh/id_rsa.pub lesstif@192.168.10.1
- ssh-copy-id -n -i ~/.ssh/id_rsa.pub -p7022 <id>@<host>
- ssh-keygen -t rsa
  - ~/.ssh 경로에 id_rsa 와 id_rsa.pub 파일 생성
  - ssh-copy-id -i ~/.ssh/id_rsa.pub [원격서버 주소]      
      
### Auth 방법 결정 
- PubkeyAuthentication yes
- PasswordAuthentication no
- sudo vim /etc/ssh/sshd_config
      
### WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!  
- ssh-keygen -f "/home/tinyos/.ssh/known_hosts" -R "10.0.0.22" 
      
### key 를 이용하여 자동 로그인이 안되는 경우
- 디렉토리 등의 권한 설정이 잘 안되어 있는 경우임 
  - /home/아이디 는 chmod 755
  - .ssh 는 700
  - authorized_keys 는 600
      

### Using an additional local port for SSH
- Local port `1001` can be mapped to the default SSH port `22`.
- Run `redirect_1001_to_22.sh` as root to add the port forwarding rule:
  ```bash
  sudo ./redirect_1001_to_22.sh
  ```
- After executing, connections to port `1001` will be served by the same SSH daemon running on port `22`.
