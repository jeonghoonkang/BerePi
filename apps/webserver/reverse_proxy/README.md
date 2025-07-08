# Multi Reverse Proxy

이 스크립트는 간단한 파이썬 기반 리버스 프록시 서버입니다. 여러 개의 내부 웹 서비스를
각각 다른 외부 포트로 포워딩할 수 있습니다.

## 사용법

```
python3 multi_reverse_proxy.py --map OUT_PORT:HOST:PORT [--map OUT_PORT:HOST:PORT ...]
```

예를 들어 내부의 `localhost:5000` 서비스를 외부 8080 포트로,
`localhost:5001` 서비스를 8081 포트로 노출하려면 다음과 같이 실행합니다.

```
python3 multi_reverse_proxy.py \
    --map 8080:localhost:5000 \
    --map 8081:localhost:5001
    --status-port 9000

```

실행하면 각 매핑에 대해 "Forwarding" 메시지가 표시되며, 여러 프록시가 동시에 동작합니다.
종료하려면 `Ctrl+C` 를 누르면 됩니다.

기본적으로 상태 정보는 `status.txt` 파일에 저장되며, `--status-port` 옵션으로 지정한 포트에서
동작하는 웹 페이지를 통해 현재 매핑 상태를 확인할 수 있습니다.

