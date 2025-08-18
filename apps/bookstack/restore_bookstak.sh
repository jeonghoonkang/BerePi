#!/bin/bash
# 백업 디렉터리를 첫 번째 인자로 받습니다.
BACKUP_DIR="$1"

if [ -z "$BACKUP_DIR" ]; then
  echo "사용법: $0 <backup_dir>"
  exit 1
fi

# 1) 데이터베이스 복구 (컨테이너 이름: bookstack_db)
docker exec -i bookstack_db \
  mysql -u bookstack -p'비밀번호' bookstack \
  < "$BACKUP_DIR/bookstack.sql"

# 2) 업로드 파일 복구 (컨테이너 이름: bookstack_app)
docker run --rm \
  --volumes-from bookstack_app \
  -v "$BACKUP_DIR":/backup \
  alpine tar xzvf /backup/uploads.tgz -C /

echo "복구 완료"
