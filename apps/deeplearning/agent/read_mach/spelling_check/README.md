# PDF 한글/영문 맞춤법 검사기

PDF의 텍스트 레이어를 페이지별로 읽고 한글(`ko-KR`)과 영어(`en-US`) 맞춤법 오류 후보를 출력합니다. 각 결과에는 페이지, 오류 문자열, 첫 번째 수정 제안, 설명과 문맥이 포함됩니다.

검사 중에는 `맞춤법 검사 중: 15/313 페이지` 형식으로 현재 처리 중인 페이지가 실시간 표시됩니다.

## 설치

```powershell
cd E:\devel\BerePi\apps\deeplearning\agent\read_mach\spelling_check
py -3 -m pip install -r requirements.txt
```

### Java 17 설치 (Ubuntu/WSL)

로컬 LanguageTool 실행에는 Java 17 이상이 필요합니다. Ubuntu 또는 WSL에서는 다음 명령으로 설치합니다.

```bash
sudo apt update
sudo apt install -y openjdk-17-jre-headless
```

설치된 Java 버전을 확인합니다.

```bash
java -version
```

출력에 `17` 이상의 버전이 표시되어야 합니다. 여러 Java 버전이 설치되어 있다면 다음 명령으로 Java 17을 선택합니다.

```bash
sudo update-alternatives --config java
```

WSL에서 실행할 때는 Python 의존성도 WSL 환경에 별도로 설치해야 합니다.

```bash
cd /mnt/e/devel/BerePi/apps/deeplearning/agent/read_mach/spelling_check
python3 -m pip install -r requirements.txt
```

## 실행

```powershell
py -3 spelling_check.py input.pdf
py -3 spelling_check.py input.pdf --output result.json
```

기본값은 호출 제한이 없는 로컬 LanguageTool 서버입니다. 최초 실행 시 LanguageTool을 내려받으며 Java가 필요합니다. 313페이지처럼 긴 PDF에는 기본 로컬 모드를 사용하세요.

기존 사내 LanguageTool 서버가 있다면 다음과 같이 지정합니다.

```powershell
py -3 spelling_check.py input.pdf --remote-url http://localhost:8081
```

짧은 문서에 한해서 무료 공개 API를 선택할 수도 있지만 요청 한도가 있습니다.

```powershell
py -3 spelling_check.py input.pdf --public-api
```

종료 코드는 오류 후보 없음 `0`, 오류 후보 있음 `1`, 실행 실패 `2`입니다. 스캔 이미지로만 구성된 PDF는 텍스트를 추출할 수 없으며 해당 페이지를 OCR 필요 페이지로 경고합니다.
