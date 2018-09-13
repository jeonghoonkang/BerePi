## 한글 로케일 설정
- sudo apt-get install language-pack-ko
- sudo locale-gen ko_KR.UTF-8
- sudo dpkg-reconfigure locales
- sudo update-locale LANG=ko_KR.UTF-8 LC_MESSAGES=POSIX

## 한글 x 윈도우 폰트 추가
- (우분투) sudo apt-get install ibus ibus-hangul ttf-unfonts-core
- (라즈베리파이) sudo apt-get install ibus ibus-hangul fonts-unfonts-core
  - ttf-unfonts-core 대신 fonts-unfonts-core
  
## 한글 입력기
 - sudo apt-get install fcitx-hangul
 - 위의 ibus 같은 다른 입력기들은 PIXEL 윈도우 상에서 사용에 문제가 좀 있었음 
 
  
## to-do
- 한글 입력기 설정
