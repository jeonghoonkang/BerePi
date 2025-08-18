#!/bin/bash
# 현재 날짜/시간으로 백업 디렉터리 생성
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$PWD/bookstack_backup_$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

# 1) 데이터베이스 백업 (컨테이너 이름: bookstack_db)
docker exec bookstack_db \
  mysqldump -u bookstack -p'비밀번호' bookstack \
  > "$BACKUP_DIR/bookstack.sql"

# 2) 업로드 파일 백업 (컨테이너 이름: bookstack_app)
docker run --rm \
  --volumes-from bookstack_app \
  -v "$BACKUP_DIR":/backup \
  alpine tar czvf /backup/uploads.tgz /var/www/bookstack/storage/uploads

echo "백업 완료: $BACKUP_DIR"
