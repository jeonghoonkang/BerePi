## Filebrowser
- from : https://github.com/filebrowser/filebrowser
- great software for file maintanace and sharing on simple and strait interface

## install
- by just run shell command
  - curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash
## run
  - filebrowser -r /path/to/your/files
## configure
  - filebrowser config set -a {0.0.0.0}
  - filebrowser config set -p {포트번호}

<pre>
filebrowser config set -a 0.0.0.0
filebrowser config set -p 5320
filebrowser -r ./
</pre>
