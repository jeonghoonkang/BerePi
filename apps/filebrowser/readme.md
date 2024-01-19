## Filebrowser
- from : https://github.com/filebrowser/filebrowser
- great software for file maintanace and sharing on simple and strait interface
  - I have forked it on https://github.com/jeonghoonkang/filebrowser    

## install
- just run shell command
  - curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash
  
## run (실행)
  - bash 또는 shell 에서 아래 명령으로 실행
    - filebrowser -r /path/to/your/files
## configure
  - filebrowser config set -a {0.0.0.0}
  - filebrowser config set -p {포트번호}

<pre>
filebrowser config set -a 0.0.0.0  ## 외부접근 IP 허용
filebrowser config set -p 5522  ## 포트설정
filebrowser -r ./ ## 실행
</pre>
