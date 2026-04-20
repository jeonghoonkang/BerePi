- 사용자 ID 확인: 경로 중간의 user는 실제 Nextcloud에서 생성한 계정 이름이어야 합니다. 예를 들어 로그인 아이디가 myname이라면 경로를 /var/www/html/data/myname/files/Photos로 수정하세요.

- 권한 설정: 외부로 뺀 photos 디렉토리는 컨테이너 내부의 www-data (UID: 33) 사용자가 읽고 쓸 수 있는 권한이 있어야 합니다. 매핑 후 사진이 보이지 않거나 업로드가 안 된다면 호스트에서 sudo chown -R 33:33 ./volumes/nextcloud/photos 명령어를 실행해 주세요.

- 파일 동기화: 만약 이 설정을 하기 전에 이미 Photos 폴더에 사진이 있었다면, 설정 변경 후 호스트의 ./volumes/nextcloud/photos로 해당 파일들을 미리 옮겨두어야 합니다. 그렇지 않으면 빈 폴더가 마운트되어 기존 파일이 보이지 않을 수 있습니다.

- OCC 명령어: 파일들을 수동으로 옮긴 후 Nextcloud가 이를 인식하지 못한다면, 아래 명령어로 파일 인덱스를 갱신해야 합니다.

  - docker exec -u www-data nextcloud_rpi php occ files:scan --all
