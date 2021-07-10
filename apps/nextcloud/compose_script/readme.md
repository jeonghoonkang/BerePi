# Installation 

- ./config/config.php 에 아래 내용 필요
  - 문제 : 로그인 아이디를 입력해도 계속 기다리기만 하고, 로그인하여 초기 페이지로 이동하지 않음
  - 해결방법 : config.php 에 추가...  'overwriteprotocol' => 'https',

