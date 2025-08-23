## 개인 운영 클라우드 다큐먼트 시스템

- Bookstack service
- .env file should have
  - APP_URL= http://192.168.0.100:6875
 
- admin@admin.com password

### Backup

`backup_bookstack.sh` 스크립트는 `nocommit.ini` 파일에 저장된 데이터베이스 정보를 사용합니다. 예시는 다음과 같습니다.

```
db=bookstack
id=bookstack
password=your_password
```

`nocommit.ini` 파일은 버전에 포함되지 않으므로 필요에 따라 직접 생성해야 합니다.
