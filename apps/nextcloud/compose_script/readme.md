# 설치 및 동작 이슈  

## 설치 후 문제 발생할 경우 (https 문제)
- 문제 : 로그인 아이디를 입력해도 계속 기다리기만 하고, 로그인하여 초기 페이지로 이동하지 않음
  - 해결방법 : config.php 에 추가...  'overwriteprotocol' => 'https',
  - 파일위치 : ~~ {volume-nextcloud} ...config/config.php
  - 'forcessl' => true,
  - 'overwriteprotocol' => 'https',
