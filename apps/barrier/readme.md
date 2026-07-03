## Install for Mac OSX
- brew install barrier
- https://github.com/debauchee/barrier/releases

- This SW for keyboard and mouse sharing beyond OS barrier

## Deskflow

Deskflow는 Barrier/Synergy 계열의 키보드/마우스 공유 프로그램입니다.
여러 PC가 같은 네트워크에 있을 때 한 컴퓨터의 키보드와 마우스로 다른 컴퓨터를 제어합니다.

### Install for Mac OSX

```bash
brew tap deskflow/tap
brew install deskflow
```

개발 빌드를 사용하려면:

```bash
brew install deskflow-dev
```

직접 다운로드한 앱이 macOS에서 열리지 않으면 Applications로 복사한 뒤 아래 명령을 실행합니다.

```bash
xattr -c /Applications/Deskflow.app
```

### macOS permission

macOS에서는 아래 권한을 허용해야 정상 동작합니다.

- System Settings > Privacy & Security > Accessibility
  - Deskflow
  - deskflow 또는 deskflow-core
- System Settings > Privacy & Security > Local Network
  - Deskflow

권한을 이미 줬는데도 동작하지 않으면 기존 항목을 삭제한 뒤 Deskflow를 다시 실행해서 권한을 다시 허용합니다.

### GUI usage

#### Server

키보드와 마우스를 실제로 연결한 컴퓨터에서 실행합니다.

1. Deskflow 실행
2. Server 모드 선택
3. Configure Server에서 client 컴퓨터 이름을 화면 배치대로 추가
4. Apply
5. Start

#### Client

키보드와 마우스를 공유받을 컴퓨터에서 실행합니다.

1. Deskflow 실행
2. Client 모드 선택
3. Server IP 입력
4. Start

컴퓨터 이름이 맞지 않으면 연결이 실패할 수 있습니다. client 쪽 Deskflow 화면에 표시되는 이름을 server 설정의 computer 이름과 맞춥니다.

### Command line usage

macOS 앱 내부 실행 파일 위치:

```bash
cd /Applications/Deskflow.app/Contents/MacOS/
```

Client로 접속:

```bash
./deskflow-core client <server-ip>
```

예:

```bash
./deskflow-core client 192.168.0.10
```

Linux에서 패키지로 설치된 경우:

```bash
deskflow-core client <server-ip>
```

구버전/배포판 패키지에 따라 아래 명령이 제공될 수도 있습니다.

```bash
deskflow-client <server-ip>
```

### Firewall / network check

연결이 안 되면 먼저 같은 네트워크에서 server IP가 보이는지 확인합니다.

```bash
ping <server-ip>
```

macOS 방화벽을 사용하는 경우 Deskflow의 들어오는 연결을 허용합니다.

## Issue

<pre>

(error) ssl certificate doesn't exist: /Users/tinyos/Library/Application Support/barrier/SSL/Barrier.pem

I had the exact same issue on macOS Monterey (12.0.1) today.
Solved it by running the openssl command described in @4F2E4A2E post.

cd into /Users/<user>/Library/Application Support/barrier/SSL ** not this dir /Users/Library/Application Support
run in the cmd 
openssl req -x509 -nodes -days 365 -subj /CN=Barrier -newkey rsa:4096 -keyout Barrier.pem -out Barrier.pem
restart barrier

(other direction)
openssl req -x509 -nodes -days 365 -subj /CN=barrier -newkey rsa:4096 -keyout barrier.pem -out barrier.pem
openssl x509 -fingerprint -sha1 -noout -in barrier.pem > Fingerprints/Local.txt
sed -e "s/.*=//" -i Fingerprints/Local.txt

</pre>
