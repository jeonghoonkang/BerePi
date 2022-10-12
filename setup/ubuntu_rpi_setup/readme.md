## ubuntu version update (if you have old version of Ubuntu which has error on apt-get update, apt update)

### backup your sources file
- cp /etc/apt/sources.list /etc/apt/sources.list.bak 

### replace the links with the archive address
- sudo sed -i -re 's/([a-z]{2}.)?archive.ubuntu.com|security.ubuntu.com/old-releases.ubuntu.com/g' /etc/apt/sources.list

### run update again
- sudo apt-get update && sudo apt-get dist-upgrade


### Please check , old repo 
- https://old-releases.ubuntu.com/ubuntu/dists/
- <pre>deb http://old-releases.ubuntu.com/ubuntu/ hirsute-updates universe
 </pre>
