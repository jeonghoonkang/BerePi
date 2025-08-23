#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/nocommit.ini"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Config file not found: $CONFIG_FILE"
  exit 1
fi

DB=$(awk -F '=' '/^db[ \t]*=/ {print $2}' "$CONFIG_FILE" | tr -d ' \r\n')
ID=$(awk -F '=' '/^id[ \t]*=/ {print $2}' "$CONFIG_FILE" | tr -d ' \r\n')
PASSWORD=$(awk -F '=' '/^password[ \t]*=/ {print $2}' "$CONFIG_FILE" | tr -d ' \r\n')

if [[ -z "$DB" || -z "$ID" || -z "$PASSWORD" ]]; then
  echo "db, id or password missing in $CONFIG_FILE"
  exit 1
fi

# 현재 날짜/시간으로 백업 디렉터리 생성
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$PWD/bookstack_backup_$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

# 1) 데이터베이스 백업 (컨테이너 이름: bookstack_db)
docker exec bookstack_db \
  mysqldump -u "$ID" -p"$PASSWORD" "$DB" \
  > "$BACKUP_DIR/bookstack.sql"

# 2) 업로드 파일 백업 (컨테이너 이름: bookstack_app)
docker run --rm \
  --volumes-from bookstack_app \
  -v "$BACKUP_DIR":/backup \
  alpine tar czvf /backup/uploads.tgz /var/www/bookstack/storage/uploads

echo "백업 완료: $BACKUP_DIR"
