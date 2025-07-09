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
    --status-user admin --status-pass secret
```

실행하면 각 매핑에 대해 "Forwarding" 메시지가 표시되며, 여러 프록시가 동시에 동작합니다.
종료하려면 `Ctrl+C` 를 누르면 됩니다.

기본적으로 상태 정보는 `status.txt` 파일에 저장됩니다. 첫 줄에는 상태 페이지가 동작하는
포트 번호가 기록되며, 이후 줄에는 각 포트 매핑이 나열됩니다. 같은 정보는 `--status-port`
옵션으로 지정한 포트에서 제공되는 웹 페이지에서도 확인할 수 있습니다.

`--status-user` 와 `--status-pass` 옵션을 지정하면 상태 포트(`http://호스트:포트/`)
로 접속 시 로그인 CGI 페이지가 표시됩니다. 올바른 사용자 이름과 비밀번호를
입력해야 `status.txt` 파일의 내용이 출력됩니다.


- 실행(예)
```
sudo python3 multi_reverse_proxy.py --map 2280:localhost:80 --map 2281:localhost:81 --status-port 81 --status-user {username} --status-pass {password}
```
✨ (Status Port 로 연결, username, password ) ✨ 

![image](https://github.com/user-attachments/assets/a0f9ecb4-4e0a-401e-8e30-d255099d2924)

✨ (결과 출력) ✨  

![image](https://github.com/user-attachments/assets/5521fb89-beb9-400e-9e4e-9d99437406dc)


### status.txt 조회 스크립트

`status_reader.py` 스크립트는 로컬에 저장된 `status.txt` 파일을
비밀번호 입력 후 확인할 수 있게 해 줍니다.

```bash
python3 status_reader.py --file status.txt --expected-pass secret
```

비밀번호가 올바르면 파일 내용을 출력하고, 틀리면 `Access denied` 메시지가
표시됩니다.

