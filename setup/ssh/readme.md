
#### 키 관리 방법, 자동 로그인

- ssh-keygen -t rsa -C eben@pi
- cat ~/.ssh/id_rsa.pub | ssh <USERNAME>@<IP-ADDRESS> 'cat >> .ssh/authorized_keys'
- cd ~
  - install -d -m 700 ~/.ssh

