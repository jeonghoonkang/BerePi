---
name: minimal-blue-bilingual-portfolio
description: 한서우 홈페이지에서 추출한 미니멀 블루 포트폴리오 디자인을 재사용한다. 한·영 전환, 라이트·다크 테마, 프로필 히어로, 카드 그리드, 경력 타임라인을 갖춘 정적 개인 홈페이지를 만들거나 수정할 때 사용한다.
---

# Minimal Blue Bilingual Portfolio

원본: https://swhan0329.github.io/ · 다운로드 시각과 파일별 출처는 [source-manifest.json](references/source-manifest.json)에 기록한다.

## 바로 실행

`assets/site/index.html`을 브라우저로 열면 빌드 없이 확인할 수 있다. CSS, JavaScript, 이미지와 Inter 폰트가 로컬에 포함되어 있다. 외부 링크를 클릭하면 인터넷이 필요하다.

새 작업 디렉터리를 만들려면 이 스킬 디렉터리에서 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reuse.ps1 -Destination E:\devel\my-portfolio
```

`Destination`은 아직 존재하지 않는 경로를 사용한다. 생성된 `index.html`을 열어 수정 결과를 확인한다.

Ubuntu 또는 WSL Bash에서는 동일한 디렉터리에서 실행한다.

```bash
bash scripts/reuse.sh "$HOME/my-portfolio"
```

두 환경의 실행·미리보기·재다운로드 방법은 [readme.md](readme.md)를 참고한다.

## 재사용 순서

1. `assets/site`를 새 프로젝트로 복사한다. `references/original`은 원본 비교용이므로 수정하지 않는다.
2. [design-system.md](references/design-system.md)의 섹션과 토큰을 참고한다. 색상·폭·간격은 `css/custom.css`에서 변경한다. 구조를 바꿀 때만 `css/style.css`를 수정한다.
3. `index.html`에서 원하는 섹션을 선택하고 인물·이미지·링크·메타데이터를 교체한다. 텍스트에 `data-i18n` 또는 `data-i18n-html`이 있으면 `js/i18n.js`의 한국어·영어 값도 함께 수정한다. HTML만 바꾸면 언어 초기화 시 원본 문구가 다시 나타난다.
4. `js/main.js`가 사용하는 `header`, `nav`, `themeToggle`, `langToggle`, `menuToggle` ID를 유지한다. 필요 없는 기능을 제거할 때 연결된 초기화도 확인한다.
5. 데스크톱과 390px 모바일 화면에서 메뉴, 테마, 언어 전환, 앵커 이동과 가로 넘침을 확인한다. 연결된 브라우저가 없으면 시각 검증을 완료했다고 기록하지 않는다.

## 파일 구성과 경계

- `assets/site/`: 수정해서 사용할 정적 사이트. 원본 홈페이지의 전체 섹션을 포함한다.
- `references/original/`: 다운로드한 응답 본문을 그대로 보관한 비교 자료. 외부 통계 호출 등이 남아 있으므로 실행용은 `assets/site`를 사용한다.
- `references/source-manifest.json`: URL, 다운로드 시각, 크기, 원본·로컬 SHA-256, 변경 사항.
- `scripts/download.mjs`: Node.js 20 이상에서 `node scripts/download.mjs <새 저장 경로>`로 다시 다운로드한다. 기존 사이트는 덮어쓰지 않는다. 중단된 다운로드는 다른 새 경로에서 재시도한다.
- `scripts/reuse.ps1`: 원본 자료 없이 실행용 사이트만 새 디렉터리로 복사한다.
- `scripts/reuse.sh`: Ubuntu/WSL Bash에서 실행용 사이트를 새 디렉터리로 복사한다. 공백이 있는 경로도 인용해서 전달할 수 있다.

홈페이지의 하위 페이지와 외부 서비스는 복제하지 않았다. 전자책 상세 등의 링크는 원본 URL로 연결한다. 다운로드 카운터는 로컬에서 0을 표시하며 원본 통계를 읽거나 증가시키지 않는다. 판매 기간 처리 등 나머지 원본 동작은 유지된다.

다운로드한 인물 소개, 사진, 책 표지와 브랜드는 원본 저작자의 자료다. 공개 재배포 라이선스는 확인하지 않았다. 다른 인물의 홈페이지로 재사용할 때 자신의 콘텐츠로 바꾸고, 실제 공개 전에 canonical·Open Graph·JSON-LD·사이트 인증값·연락처·저작권 문구를 함께 교체한다. 로컬본의 `noindex`는 공개 준비가 끝난 뒤 필요에 따라 변경한다.
