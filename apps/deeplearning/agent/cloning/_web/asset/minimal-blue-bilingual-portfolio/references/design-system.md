# 디자인 시스템과 수정 위치

실제 다운로드한 `css/style.css`와 `index.html`을 기준으로 정리했다.

## 핵심 특징

| 항목 | 원본 값 / 구성 |
| --- | --- |
| 기본 배경 / 교차 배경 | `#ffffff` / `#f8f9fa` |
| 제목 / 보조 텍스트 | `#1a1a1a` / `#6b7280` |
| 강조 / hover | `#3b82f6` / `#2563eb` |
| 구분선 | `#e5e7eb` |
| 다크 배경 / 카드 | `#0f0f0f` / `#1a1a1a` |
| 다크 강조색 | `#60a5fa` |
| 본문 폰트 | Inter, 시스템 sans-serif 폴백; 한국어는 시스템 폰트 |
| 콘텐츠 최대 폭 | `1100px`, 좌우 패딩 `1.5rem` |
| 섹션 패딩 / 헤더 높이 | `4rem` / `70px` |
| 전환 | `0.3s ease` |
| 주요 반응형 분기 | `768px`, `640px`, `480px` |

고정 헤더 아래에 텍스트와 원형 프로필 사진을 배치한다. 흰색과 옅은 회색 섹션이 교차하며 카드, 배지, 타임라인과 목록을 통해 긴 이력을 정리한다. 카드별 둥근 모서리와 그리드 비율이 다르므로 일괄적인 카드 스타일로 덮어쓰지 않는다.

## 컴포넌트 찾기

| 영역 | HTML / CSS 검색어 |
| --- | --- |
| 고정 메뉴, 모바일 메뉴 | `.header`, `.nav`, `.menu-toggle` |
| 프로필 소개 | `.hero-content`, `.hero-text`, `.hero-image` |
| 대표 포트폴리오 | `.portfolio-grid`, `.portfolio-card` |
| 경력 | `id="experience"`, `.timeline` |
| 커뮤니티와 활동 | `id="ecosystem"`, `.ambassador` |
| 전자책 | `.ebook-home-card`, `.ebook-actions` |
| 프로젝트 | `id="projects"`, `.projects-grid` |
| 발표 / 미디어 | `.talks-list`, `.media-grid` |
| 논문 / 취미 | `.publications-list`, `.life-grid` |

## 수정 시 함께 볼 파일

- 본문: `index.html` + `js/i18n.js`. `data-i18n-html` 값에는 HTML이 포함될 수 있다.
- 이미지: `assets/profile.jpg`, `assets/ebooks/*`, `vendor/*`. 교체할 때 원래 비율과 대체 텍스트를 확인한다.
- 테마: `css/custom.css`의 `:root`와 `[data-theme="dark"]`를 함께 변경한다.
- 동작: `js/main.js`의 `initTheme`, `initNav`, `initI18n`, `initSmoothScroll`, `initExpandableText`.
- 로컬 폰트와 썸네일: `vendor/`의 해시 이름과 원본 URL 매핑은 `source-manifest.json`에서 확인한다.

## 보존한 동작

한·영 전환, 저장된 테마 선택, 모바일 메뉴, 앵커 스크롤, 설명 펼치기와 원본 애니메이션 코드를 유지했다. 원본의 다운로드 통계 요청만 로컬 응답으로 바꿨다. 이것은 코드 보존 범위이며 브라우저 동작 검증 결과는 `validation.md`를 확인한다.
