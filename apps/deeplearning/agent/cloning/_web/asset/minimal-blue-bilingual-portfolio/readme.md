# Minimal Blue Bilingual Portfolio

[한서우 홈페이지](https://swhan0329.github.io/)의 정적 디자인을 보관하고 재사용하는 패키지입니다. 고정 메뉴, 원형 프로필, 파란 강조색, 카드 그리드, 경력 타임라인, 한·영 전환과 다크 모드를 포함합니다.

## 실행 환경

| 작업 | Windows | Ubuntu / WSL |
| --- | --- | --- |
| 기존 템플릿 복사 | Windows PowerShell 5.1 이상 | Bash와 GNU coreutils (`cp`, `mkdir`, `realpath`) |
| 홈페이지 열기 | 웹 브라우저 | 웹 브라우저 |
| 선택적 HTTP 미리보기 | Python 3 | Python 3 |
| 원본 재다운로드 | Node.js 20 이상 | Node.js 20 이상을 지원하는 Ubuntu 환경 |

템플릿 복사와 홈페이지 실행에는 Node.js와 npm 설치가 필요 없습니다. 명령은 이 `readme.md`가 있는 디렉터리를 기준으로 합니다. 스크립트를 절대 경로로 실행해도 되며 상대 목적지는 현재 작업 디렉터리를 기준으로 해석합니다.

## Windows PowerShell

```powershell
cd E:\devel\BerePi\apps\deeplearning\agent\cloning\_web\asset\minimal-blue-bilingual-portfolio
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\reuse.ps1 -Destination "E:\devel\my portfolio"
Start-Process "E:\devel\my portfolio\index.html"
```

`ExecutionPolicy Bypass`는 해당 PowerShell 실행에만 적용됩니다. 기존 디렉터리는 덮어쓰지 않으므로 새로운 목적지를 지정하세요.

## Ubuntu Bash / WSL

WSL에서는 Windows의 `E:\devel`을 `/mnt/e/devel`로 접근합니다. 일반 Ubuntu에서는 아래 `cd` 경로를 저장소를 내려받은 위치로 바꾸세요.

```bash
cd /mnt/e/devel/BerePi/apps/deeplearning/agent/cloning/_web/asset/minimal-blue-bilingual-portfolio
bash scripts/reuse.sh "$HOME/my portfolio"
```

생성된 `index.html`을 브라우저로 열 수 있습니다. WSL 홈 디렉터리의 파일을 Windows 브라우저에서 확인하려면 아래 HTTP 미리보기가 편리합니다.

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory "$HOME/my portfolio"
```

브라우저에서 <http://localhost:8080>을 열고 종료할 때 터미널에서 `Ctrl+C`를 누릅니다. Python 3.6 등 `--directory` 옵션을 지원하지 않는 버전에서는 다음처럼 실행합니다.

```bash
cd "$HOME/my portfolio"
python3 -m http.server 8080 --bind 127.0.0.1
```

Windows에서도 `python -m http.server 8080 --bind 127.0.0.1 --directory "E:\devel\my portfolio"`를 사용할 수 있습니다.

Ubuntu/WSL에서 복사 동작을 검증하려면 패키지 디렉터리에서 `bash scripts/test-reuse.sh`를 실행합니다. 테스트는 임시 폴더에서 수행하고 종료 시 해당 폴더를 정리합니다.

## 원본 다시 다운로드

이미 포함된 파일을 재사용할 때는 다운로드할 필요가 없습니다. 최신 원본이 필요할 때 Node.js 20 이상에서 새 저장 경로를 지정합니다. 두 OS에서 같은 JavaScript를 사용합니다.

```powershell
node .\scripts\download.mjs "E:\devel\portfolio-refresh"
```

```bash
node scripts/download.mjs "$HOME/portfolio-refresh"
```

결과는 `<저장 경로>/assets/site`, `references/original`, `references/source-manifest.json`에 생성됩니다. 이것은 캡처 결과이며 스킬 지침과 재사용 스크립트까지 새로 복사하지는 않습니다. 기존 `assets/site`가 있는 경로는 거부하며, 다운로드가 중단되면 다른 새 경로로 재시도하세요.

## 수정할 파일

- `assets/site/index.html`: 섹션 구조, 이미지, 링크, 메타데이터.
- `assets/site/js/i18n.js`: 한국어·영어 문구. `data-i18n`이 있는 본문은 HTML과 함께 수정합니다.
- `assets/site/css/custom.css`: 색상, 콘텐츠 폭, 간격과 다크 테마 재정의.
- `assets/site/js/main.js`: 메뉴, 테마, 스크롤 등 상호작용.
- [SKILL.md](SKILL.md): 다른 작업에서 이 패키지를 재사용하는 지침.
- [design-system.md](references/design-system.md): 디자인 토큰과 컴포넌트 위치.
- [validation.md](references/validation.md): 검증 범위와 제한.

실행본은 CSS·스크립트·이미지·폰트를 로컬에서 읽습니다. 하위 페이지와 외부 링크는 원본 사이트로 연결되며 인터넷이 필요합니다. 원본 다운로드 통계 호출은 실행본에서 비활성화되어 0을 표시합니다. 원본 인물 정보·사진·책 표지를 다른 사이트에 사용할 때는 본인 콘텐츠로 교체하세요. 공개 재배포 라이선스는 확인하지 않았습니다.
