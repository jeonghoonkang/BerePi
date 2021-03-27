# Windows10 Docker on WSL2
## 주요 설정
- https://www.44bits.io/ko/post/wsl2-install-and-basic-usage
## 세부내용
### 순서
- Windows Terminal 관리자 권한 실행
- dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
- dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
- ubuntu 터미널 설치
- wsl -l
- wsl -l -v
- 
