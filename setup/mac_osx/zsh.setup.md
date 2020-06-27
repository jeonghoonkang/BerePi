

# zsh 설치

- echo $0


- sh -c "$(curl -fsSL https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"


- git clone https://github.com/bhilburn/powerlevel9k.git ~/.oh-my-zsh/themes/powerlevel9k


- vi ~/.zshrc
  - ZSH_THEME 단락을 `powerlevel9k/powerlevel9k`로 바꿔준다  
  - .zshrc 기본 ZSH_THEME는 `robbyrussell`



- (폰트설치) Powerlevel9k 테마 폰트 리포지토리를 다운로드 받고 그 폴더로 이동.
  - git clone https://github.com/powerline/fonts.git /tmp/powerlevel9k-fonts && cd $_

- install.sh를 실행해 폰트를 설치
  - sh ./install.sh

- 다운로드 받았던 리포지토리 삭제
  - cd .. && rm -rf /tmp/powerlevel9k-fonts


