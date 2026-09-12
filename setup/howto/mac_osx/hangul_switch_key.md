# macOS 한/영 전환을 Shift + Space로 설정하기

설정 창에서 Shift + Space가 입력되지 않을 때 터미널의 `defaults` 명령으로 단축키를 지정한다. 대상 파일은 사용자별 설정인 `~/Library/Preferences/com.apple.symbolichotkeys.plist`이다. `sudo`는 사용하지 않는다.

## 현재 설정 확인 결과

2026-09-12에 이 Mac에서 읽은 결과이다. 문서를 작성하면서 시스템 설정을 변경하지 않았다.

| 항목 | 확인 결과 |
|---|---|
| macOS | Sequoia 15.7.7, 빌드 24G720 |
| 입력 언어 | ABC(영어), 한국어 두벌식 |
| 이전 입력 소스 선택 (`60`) | 비활성화, Control + Space (`32, 49, 262144`) |
| 입력 메뉴에서 다음 소스 선택 (`61`) | 활성화, Shift + Space (`32, 49, 131072`) |
| Shift + Space 중복 | 저장된 `AppleSymbolicHotKeys`에서 `61`번만 등록됨 |

**현재 저장된 값은 이미 원하는 설정이다.** 변경 명령을 다시 실행할 필요는 없다. 실제 키 입력에 반영되었는지는 텍스트 편집기에서 확인해야 한다. 이 확인 결과는 macOS 단축키 설정 범위이며, 개별 앱이나 키 매핑 프로그램의 단축키까지 검사한 결과는 아니다.

## 1. 현재 값을 직접 확인하기

macOS 버전과 등록된 입력 소스:

```sh
sw_vers
defaults read com.apple.HIToolbox AppleEnabledInputSources
```

입력 소스 목록의 `ABC`와 `com.apple.inputmethod.Korean.2SetKorean`이 각각 영어와 한국어 두벌식이다. 문자 팔레트나 PressAndHold 등의 보조 항목은 별도의 입력 언어로 세지 않는다.

아래 한 줄은 현재 설정을 임시 파일로 내보낸 뒤 `60`, `61`번만 출력한다. 설정은 변경하지 않는다.

```sh
zsh -c 'plist_file=$(mktemp); trap '\''rm -f "$plist_file"'\'' EXIT; defaults export com.apple.symbolichotkeys "$plist_file" || exit 1; for key_id in 60 61; do case "$key_id" in 60) echo "이전 입력 소스 선택 (60)";; 61) echo "입력 메뉴에서 다음 소스 선택 (61)";; esac; /usr/libexec/PlistBuddy -c "Print :AppleSymbolicHotKeys:$key_id" "$plist_file"; done'
```

`enabled = true`이면 활성화, `false`이면 비활성화이다. `Does Not Exist`가 나오면 해당 항목이 명시적으로 저장되지 않은 상태이다.

전체 단축키를 확인하려면 다음을 실행한다. Space 키 코드가 `49`이고 보조 키 값이 정확히 `131072`인 항목이 여러 개 활성화되어 있는지 살펴본다.

```sh
defaults read com.apple.symbolichotkeys AppleSymbolicHotKeys
```

## 2. 설정 파일 구조와 키 값

```text
AppleSymbolicHotKeys
└── 61
    ├── enabled = true
    └── value
        ├── type = standard
        └── parameters
            ├── Item 0 = 32
            ├── Item 1 = 49
            └── Item 2 = 131072
```

| 값 | 의미 |
|---|---|
| `60` | 이전 입력 소스 선택 |
| `61` | 입력 메뉴에서 다음 소스 선택 |
| `parameters[0] = 32` | Space 문자 코드 |
| `parameters[1] = 49` | Space 키 코드 |
| `parameters[2] = 131072` | Shift |
| `parameters[2] = 262144` | Control |

plist 파일은 바이너리 형식일 수 있다. 텍스트 편집기로 직접 덮어쓰기보다 아래 `defaults` 명령으로 저장한다.

## 3. 백업 후 Shift + Space 지정하기

시스템 설정 앱을 완전히 종료한다. 다음 명령은 한/영 전환을 사용하는 본인 계정의 터미널에서 실행한다.

먼저 바탕화면에 날짜와 시간이 포함된 백업을 만든다. 백업 명령이 실패하면 변경하기 전에 오류를 해결한다.

```sh
defaults export com.apple.symbolichotkeys "$HOME/Desktop/symbolichotkeys-backup-$(date +%Y%m%d-%H%M%S).plist"
```

`60`번을 비활성화하고 `61`번에 Shift + Space를 지정한다.

```sh
defaults write com.apple.symbolichotkeys AppleSymbolicHotKeys -dict-add 60 '<dict><key>enabled</key><false/><key>value</key><dict><key>parameters</key><array><integer>32</integer><integer>49</integer><integer>262144</integer></array><key>type</key><string>standard</string></dict></dict>'
defaults write com.apple.symbolichotkeys AppleSymbolicHotKeys -dict-add 61 '<dict><key>enabled</key><true/><key>value</key><dict><key>parameters</key><array><integer>32</integer><integer>49</integer><integer>131072</integer></array><key>type</key><string>standard</string></dict></dict>'
```

`-dict-add`는 `AppleSymbolicHotKeys`의 지정된 항목을 교체하며 다른 번호의 단축키는 유지한다. 같은 명령을 재실행해도 `61`번이 추가로 생기지 않는다.

## 4. 적용 및 동작 확인

1. 1절의 확인 명령으로 `60`번은 `enabled = false`, `61`번은 `enabled = true`이고 배열 값이 `32, 49, 131072`인지 확인한다.
2. 작업 중인 문서를 저장하고 로그아웃한 뒤 다시 로그인한다.
3. 시스템 설정 → 키보드 → 키보드 단축키 → 입력 소스에서 ‘이전 입력 소스 선택’이 꺼져 있고, ‘입력 메뉴에서 다음 소스 선택’이 `⇧스페이스`로 켜져 있는지 확인한다.
4. 텍스트 편집기에서 Shift + Space를 짧게 누르고 두 키를 모두 뗀다. 반복할 때마다 메뉴 막대의 입력 소스와 실제 입력 문자가 영어 ↔ 한글로 바뀌는지 확인한다.

‘다음 소스 선택’은 등록된 입력 언어를 순서대로 이동한다. 매번 한/영을 번갈아 선택하려면 시스템 설정 → 키보드 → 텍스트 입력 → 편집에서 ABC(또는 미국) 하나와 한국어 두벌식만 유지한다. 현재 Mac은 이미 이 조건을 충족한다.

앱이나 문서를 옮길 때 입력 언어가 자동으로 바뀌는 것을 원하지 않으면 입력 소스 설정의 ‘문서의 입력 소스로 자동으로 전환’을 끈다.

저장된 값이 맞는데 특정 앱에서만 전환되지 않으면 해당 앱의 Shift + Space 단축키와 설치된 키 매핑 프로그램의 규칙을 확인한다. 로그아웃 후 실제 키 입력 동작 확인은 사용자가 수행해야 한다.

## 5. 복원하기

백업 시점의 전체 단축키 설정으로 복원하려면 시스템 설정을 종료하고, 아래 파일명을 실제 백업 파일명으로 바꿔 실행한다. 이 명령은 백업 이후 변경한 다른 시스템 단축키도 백업 시점으로 되돌린다.

```sh
defaults import com.apple.symbolichotkeys "$HOME/Desktop/symbolichotkeys-backup-YYYYMMDD-HHMMSS.plist"
```

백업 시점부터 이미 Shift + Space였다면 복원해도 Shift + Space가 유지된다. 백업과 무관하게 이 Mac의 변경 전 구성인 Control + Space로 돌리려면 다음을 실행한다.

```sh
defaults write com.apple.symbolichotkeys AppleSymbolicHotKeys -dict-add 60 '<dict><key>enabled</key><true/><key>value</key><dict><key>parameters</key><array><integer>32</integer><integer>49</integer><integer>262144</integer></array><key>type</key><string>standard</string></dict></dict>'
defaults write com.apple.symbolichotkeys AppleSymbolicHotKeys -dict-add 61 '<dict><key>enabled</key><false/><key>value</key><dict><key>parameters</key><array><integer>32</integer><integer>49</integer><integer>262144</integer></array><key>type</key><string>standard</string></dict></dict>'
```

복원 후에도 로그아웃하고 다시 로그인한다.

## 참고

- [Apple: 한국어 입력기 사용 설명서](https://support.apple.com/ko-kr/guide/korean-input-method/welcome/mac)
- [Apple: 입력 소스 설정 변경하기](https://support.apple.com/ko-kr/guide/mac-help/mchl84525d76/mac)
- [Shift + Space 설정 스크립트 및 키 값 참고](https://gist.github.com/dongminkim/5856427)
