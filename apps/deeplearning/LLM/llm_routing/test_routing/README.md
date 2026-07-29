# LLM Routing 동작 검사

`check_routing.py`는 다음 항목을 순서대로 확인합니다.

1. `GET /api/status` 응답과 서비스 `ready` 상태
2. 등록된 LLM target이 1개 이상인지 확인
3. `POST /api/generate`에 간단한 프롬프트 전송
4. HTTP 성공 여부, 응답 본문, 기대 문자열 확인

외부 Python 패키지는 필요하지 않습니다.

## 실행

PowerShell에서 비밀번호를 환경변수로 전달하는 방법을 권장합니다.

```powershell
cd E:\devel\BerePi\apps\deeplearning\LLM\llm_routing\test_routing
$env:LLM_ROUTING_PASSWORD="<관리 비밀번호>"
py -3 .\check_routing.py
```

서버 주소를 변경할 때:

```powershell
py -3 .\check_routing.py --url http://127.0.0.1:4004
```

비밀번호 파일을 사용할 때:

```powershell
py -3 .\check_routing.py --password-file ..\admin_password.conf
```

특정 target만 검사할 때:

```powershell
py -3 .\check_routing.py --target-id TARGET_ID
```

JSON 결과가 필요한 모니터링 또는 CI:

```powershell
py -3 .\check_routing.py --json
```

검사 성공 시 종료 코드는 `0`, 실패 시 `1`입니다.

## 단위 테스트

단위 테스트는 실제 LLM을 호출하지 않고 로컬 모의 HTTP 서버를 사용합니다.

```powershell
py -3 -m unittest -v
```
