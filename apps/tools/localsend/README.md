# LocalSend 파일 전송

BerePi / Raspberry Pi / Linux / Windows / macOS에서 실행하여 Windows·macOS 등의
LocalSend 앱으로 파일과 폴더를 전송하는 GUI / CLI입니다. Python 3.9 이상만 필요하며
텍스트·파일 전송은 추가 패키지가 필요 없으며, 이미지 클립보드는 Pillow가 필요합니다.
수신 기능은 제공하지 않습니다.

## 네트워크 준비

1. 수신 PC에 [LocalSend](https://localsend.org/)를 설치하고 실행합니다.
2. 송신 기기는 유선 LAN, 수신 PC는 Wi-Fi여도 됩니다. 같은 공유기 등 서로
   통신 가능한 LAN에 연결합니다. 게스트 Wi-Fi / AP isolation은 해제해야 합니다.
3. 수신 PC 방화벽에서 LocalSend를 허용합니다. 기본 전송 포트는 TCP 53317,
   검색은 UDP 53317 / 멀티캐스트 224.0.0.167을 사용합니다.
4. 전송 요청이 오면 수신 앱에서 승인합니다. 수신 앱에 PIN을 설정했다면
   송신 명령에 `--pin`을 지정합니다.

## GUI 실행

```powershell
# Windows: 저장소 루트에서
py -3 -m pip install -r apps/tools/localsend/requirements.txt
py -3 apps/tools/localsend/localsend_gui.py
```

```sh
# Linux / Raspberry Pi / macOS
python3 -m pip install -r apps/tools/localsend/requirements.txt
python3 apps/tools/localsend/localsend_gui.py
```

Linux에서 Tkinter가 없으면 `sudo apt install python3-tk`로 설치합니다.
GUI 실행에는 그래픽 데스크톱이 필요합니다. Windows / macOS도 Tkinter가 포함된
Python 설치본을 사용하세요.

1. **대상 IP / 호스트**를 입력하거나 **주변 기기 검색** 후 검색 결과를 선택합니다.
2. 필요하면 포트, HTTPS/HTTP, PIN, 승인 대기 시간을 설정합니다.
3. **파일 / 폴더** 탭에서 파일 여러 개 또는 폴더를 추가합니다.
   **클립보드 텍스트** 탭에서는 **클립보드 가져오기**를 누르고 내용을 확인·수정합니다.
   **클립보드 이미지** 탭에서는 **이미지 가져오기**를 누르고 미리보기를 확인합니다.
4. **전송**을 누르고 수신 LocalSend 앱에서 승인합니다.

현재 선택한 탭의 내용만 전송됩니다. 클립보드는 텍스트를 UTF-8 `clipboard.txt`
파일로 전송합니다. 이미지는 `clipboard.png`로 전송하며 원본 해상도와 투명도를 유지합니다.
이미지 미리보기만 축소됩니다. 클립보드가 바뀌어도 가져온 이미지를 전송하므로 새로운
이미지를 보내려면 다시 **이미지 가져오기**를 누르세요. **이미지 지우기**로 제거할 수 있습니다.
탐색기에서 복사한 파일 목록은 **파일 선택**으로 추가하세요. 전송 결과와 오류는 창 아래에 표시됩니다.
검색과 전송은 백그라운드에서 실행되며 중복 실행은 차단합니다.

이미지 클립보드는 Windows / macOS / Linux를 지원하는
[Pillow ImageGrab](https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html)을 사용합니다.
Linux에서는 데스크톱 환경에 따라 `wl-paste` (Wayland, `wl-clipboard` 패키지) 또는
`xclip` (X11)도 필요합니다. 이미지가 아닌 클립보드나 가져오기 실패 시 기존 미리보기를
지워 이전 이미지가 잘못 전송되지 않게 합니다. Pillow가 없어도 텍스트·파일 전송은 동작합니다.

## CLI 실행

저장소 루트에서 실행합니다. Windows는 `python3` 대신 `py -3`을 사용할 수 있습니다.

```sh
# 주변 기기 검색
python3 apps/tools/localsend/localsend.py discover

# 수신 PC IP로 직접 전송 (자동 검색 없이 사용 가능)
python3 apps/tools/localsend/localsend.py send --host 192.168.0.25 report.pdf

# 여러 파일 및 폴더 전송: 하위 폴더 구조 유지
python3 apps/tools/localsend/localsend.py send --host 192.168.0.25 report.pdf ./photos

# 검색 결과의 별칭으로 전송 (공백 포함 별칭은 따옴표 사용)
python3 apps/tools/localsend/localsend.py send --device "My MacBook" ./photos

# 송신 별칭, PIN 및 승인 대기 시간 설정
python3 apps/tools/localsend/localsend.py --alias BerePi send --host 192.168.0.25 --pin 123456 --timeout 300 report.pdf

# 다중 NIC 환경에서 송신 기기의 유선 IPv4 주소 지정
python3 apps/tools/localsend/localsend.py discover --interface 192.168.0.10 --discovery-timeout 8

# 수신 앱에서 포트 또는 암호화 설정을 바꾼 경우
python3 apps/tools/localsend/localsend.py send --host 192.168.0.25 --port 53318 --protocol http report.pdf
```

기본 직접 전송은 HTTPS입니다. 검색 전송은 수신 앱이 알린 포트와 프로토콜을
사용합니다. LocalSend 자체 서명 인증서를 허용하므로 인증서의 신뢰성과 수신 기기의
신원을 검증하지 않습니다. 신뢰할 수 있는 LAN에서 수신 IP를 확인하고 사용하세요.
`--protocol http`는 수신 앱에서 암호화를 껐을 때만 사용하며 평문 전송입니다.

자동 검색은 임시 HTTP 포트에서 등록 응답을 받으므로 송신 측 Python 방화벽 허용도
필요할 수 있습니다. 자동 검색이 실패하면 수신 앱의 IP를 확인하여 `--host`로
전송하세요. IP 직접 전송도 실패하면 LAN 간 라우팅, 방화벽, 수신 앱 포트를 확인하세요.

파일은 최대 1 MiB 청크로 읽어 대용량 파일도 메모리에 통째로 올리지 않습니다.
빈 폴더와 심볼릭 링크는 전송하지 않습니다. 숨김 파일은 포함됩니다.
수신 경로가 겹치는 파일명은 전송 전에 오류로 처리합니다.
수신자가 일부 파일만 선택하면 선택한 파일만 보내고 완료 개수를 출력합니다.
오류나 Ctrl+C 발생 시 생성된 전송 세션의 취소를 시도합니다.
종료 코드는 완료 0, 오류 1, 사용자 취소 130입니다.

## 검증

```sh
python3 -m unittest discover -s apps/tools/localsend -p "test_*.py" -v
```

로컬 모의 수신 서버로 등록 검색, 준비 요청, PIN, 바이너리 전송, 부분 수락,
거절 및 업로드 실패 시 취소를 검증합니다. 실제 Windows/macOS LocalSend 앱과의
통신은 해당 기기에서 별도로 확인해야 합니다.

구현 기준: [LocalSend 공식 프로토콜 v2](https://github.com/localsend/protocol).
