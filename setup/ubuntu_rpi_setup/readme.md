## ubuntu version update (if you have old version of Ubuntu which has error on apt-get update, apt update)

### backup your sources file
- sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak 

### replace the links with the archive address
- sudo sed -i -re 's/([a-z]{2}.)?archive.ubuntu.com|security.ubuntu.com/old-releases.ubuntu.com/g' /etc/apt/sources.list

### run update again
- sudo apt-get update && sudo apt-get dist-upgrade
- check URL : https://old-releases.ubuntu.com/ubuntu/dists/hirsute-updates/


### Please check , old repo 
- https://old-releases.ubuntu.com/ubuntu/dists/
<pre>deb http://old-releases.ubuntu.com/ubuntu/ hirsute-updates universe
 </pre>
- /etc/apt/sources.list 파일에 위 deb ~~~~ universe 와 동일하게 입력. dist 같은 중간 dir 없는 경우 있음 


<pre>
http://kr.archive.ubuntu.com/ubuntu/dists/focal/restricted/

deb http://kr.archive.ubuntu.com/ubuntu/ focal main restricted
</pre>
