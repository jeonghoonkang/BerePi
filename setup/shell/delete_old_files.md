# 오래된 파일 삭제 스크립트

`delete_old_files.sh` 는 지정한 경로에서 일정 기간보다 오래된 파일을 찾아 보여주거나 삭제합니다.

## 사용 예

```bash
chmod +x delete_old_files.sh
./delete_old_files.sh
./delete_old_files.sh /var/log 14 "*.log"
./delete_old_files.sh /data/images 7 "*.jpg" --delete
```

기본값은 다음과 같습니다.

- 경로: 현재 디렉터리
- 보관 기간: 30일
- 파일 패턴: `*`
- 실행 방식: dry-run

먼저 dry-run 으로 확인한 뒤 `--delete` 를 붙여 실제 삭제하는 방식을 권장합니다.
