# SSH 공격 IP 검토 및 차단

`run_secure.sh`는 SSH 실패 기록을 집계해 공인 IPv4 공격 후보를 차단 목록에 추가하고 `/etc/hosts.deny`에 적용합니다.

## 안전 정책

- RFC1918 사설망(`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)은 기본적으로 자동 차단하지 않습니다.
- 승인되지 않은 사설 IP는 `run_secure_review_ip_list.txt`에 기록합니다.
- 실제 검토 목록에는 내부 주소가 포함되므로 Git에서 제외됩니다.
- 현재 SSH 클라이언트 IP와 서버 자체 IP는 승인 옵션이 있어도 차단하지 않습니다.
- 먼저 `--dry-run`으로 결과를 확인하는 것을 권장합니다.

## 사용법

```bash
./run_secure.sh --days 1 --dry-run
./run_secure.sh --days 1
```

기존 위치 인자도 호환됩니다.

```bash
./run_secure.sh 2 --dry-run
```

특정 사설 IP를 이번 실행에서만 차단 대상으로 승인합니다.

```bash
./run_secure.sh --days 1 --include-private-ip 192.168.10.25
```

특정 사설 CIDR을 이번 실행에서만 승인합니다. 옵션은 반복해서 사용할 수 있습니다.

```bash
./run_secure.sh --days 1 \
  --include-private-cidr 192.168.100.0/24 \
  --include-private-cidr 10.20.0.0/16
```

전체 사설망 승인은 접속 차단 위험이 커서 신중하게 사용해야 합니다. 현재 접속 IP와 서버 IP는 항상 보호됩니다.
