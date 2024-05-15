# INSTALL

`curl -fsSL https://get.docker.com -o get-docker.sh`

`sudo sh get-docker.sh`


## pretty check : docker ps 
- docker ps --format "table {{.Image}}\t{{.Status}}\t{{.Ports}}"
- alias dockerps='sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'


## stop. sock.server
- $ docker version -f {{.Server.Version}}
- $ sudo systemctl stop docker.service
- $ sudo systemctl disable docker.service
