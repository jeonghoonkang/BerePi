## ubuntu version update (if you have old version Ubuntu which has error on apt-get update, apt update)

### backup your sources file
- sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak 

### replace the links with the archive address
- sudo sed -i -re 's/([a-z]{2}.)?archive.ubuntu.com|security.ubuntu.com/old-releases.ubuntu.com/g' /etc/apt/sources.list

### run update again
- sudo apt-get update && sudo apt-get dist-upgrade


### Please check , old repo 
- https://old-releases.ubuntu.com/ubuntu/dists/
- check URL : https://old-releases.ubuntu.com/ubuntu/dists/hirsute-updates/

<pre>deb http://old-releases.ubuntu.com/ubuntu/ hirsute-updates universe
 </pre>
- /etc/apt/sources.list 파일에 위 deb ~~~~ universe 와 동일하게 입력. dist 같은 중간 dir 없는 경우 있음 


<pre>
http://kr.archive.ubuntu.com/ubuntu/dists/focal/restricted/

deb http://kr.archive.ubuntu.com/ubuntu/ focal main restricted
</pre>

#### VI editor command
- <pre> :%s/ports.ubuntu.com\/ubuntu-ports/old-release.ubuntu.com\/ubuntu\/dists/gc </pre>


#### 실행 예

<img width="860" alt="image" src="https://github.com/jeonghoonkang/BerePi/assets/4180063/39b4cbf9-abf9-4b49-b2be-a61d9fe12bb4">

<img width="739" alt="image" src="https://github.com/jeonghoonkang/BerePi/assets/4180063/5c71bb25-6c83-4483-b6aa-4b06881a4243">

<img width="759" alt="image" src="https://github.com/jeonghoonkang/BerePi/assets/4180063/123d7d29-aa9b-444f-9bb5-a6d63c5fb05f">

