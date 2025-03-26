
monterey keyboard 설정 - 한영키 스페이스 전환 

http://dobiho.com/691/


### shift space 한영전환 키보드 한/영 전환 쉬프트 스페이스
- Finder에서 Go > Go to Folder(Command + Shift + G)를 선택하여 
  - ~/Library/Preferences/com.apple.symbolichotkeys.plist를 선택
- Xcode 로 해당 파일의 내용 중에서.
  - <key>60</key>을 찾아서 item2 <integer>131072</integer>로 변경하고 파일을 저장. (기존 깂 262144)
  - <img width="808" alt="image" src="https://github.com/user-attachments/assets/d1f36419-3ede-44f8-beeb-6d3496f98c04" />

- 저장 후에 맥을 재시동하거나 사용자 계정에 다시 로그인하면 변경사항이 적용됩니다.
- Mac 에서 windows 로 원격 데스크탑 연결을 사용할때, 설정해 놓으면 편합니다
  - 편집도구 다운로드 : https://www.fatcatsoftware.com/plisteditpro/PlistEditPro.zip
  - Xcode 는 시간이 오래 걸림 


#### 스크린샷
- <img width="658" alt="image" src="https://github.com/jeonghoonkang/BerePi/assets/4180063/f0371c74-ec33-47c4-ac0b-034a0b75c5cf">

