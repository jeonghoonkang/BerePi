# Tesla Direct Streaming

Apache 웹 서버가 이미 제공하는 디렉토리 인덱스를 활용해서 차량 브라우저에서 음악 폴더를 탐색하고, 여러 곡을 선택한 뒤 순차 재생할 수 있는 정적 웹 앱입니다.

## 구성 파일
- `index.html`: Tesla 차량 브라우저용 메인 화면
- `style.css`: 터치 중심 레이아웃과 대형 UI 스타일
- `app.js`: Apache 디렉토리 목록 파싱, 선택, 큐 재생 로직

## 동작 방식
1. 사용자가 `Root URL`에 Apache가 노출 중인 음악 루트 URL을 입력합니다.
2. 웹 앱이 해당 디렉토리의 Apache index HTML을 가져와 폴더와 오디오 파일을 파싱합니다.
3. 사용자는 폴더를 이동하거나 파일을 여러 개 선택할 수 있습니다.
4. 선택한 곡을 재생 큐에 넣고 순서대로 재생합니다.

## 지원 포맷
- `mp3`
- `m4a`
- `aac`
- `wav`
- `ogg`
- `flac`

브라우저 자체 코덱 지원 여부는 차량 브라우저 환경에 따라 달라질 수 있습니다.

## 배포 예시
Apache document root 아래에 이 디렉토리를 배치한 뒤 다음과 같이 접근할 수 있습니다.

```text
https://your-server/direct_streaming/
```

초기 루트 URL을 바로 넘기고 싶으면 쿼리 파라미터를 사용할 수 있습니다.

```text
https://your-server/direct_streaming/?root=https://your-server/music/
```

## Apache 조건
- 디렉토리 인덱스가 켜져 있어야 합니다.
- 웹 앱이 접근하는 음악 디렉토리가 브라우저에서 `fetch()` 가능한 URL이어야 합니다.
- 가장 단순한 구성은 웹 앱과 음악 디렉토리를 같은 Apache 출처에 두는 방식입니다.

## 참고
- Apache 기본 인덱스 페이지 구조를 기준으로 동작합니다.
- 디렉토리 표시 형식이 크게 커스텀된 경우에는 `app.js`의 파서 로직 조정이 필요할 수 있습니다.
