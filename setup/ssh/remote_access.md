- reverse proxy style , ssh forwarding
  - autossh -M 20000 -N _*_@_*_._*_._*_._*_ -R 2222:localhost:22 -vvv
  - sudo vim /lib/systemd/system/reverseProxy.service
  - sudo systemctl daemon-reload 
  - sudo systemctl restart reverseProxy.service
  - sudo systemctl status reverseProxy.service
    - reverseProxcy.service
<pre>    
[Unit]
Description=SSH reverse tunneling 
After=network-online.target
 
[Service]
User=pi
ExecStart=/usr/bin/autossh -M 20000 -N ID@IP.IP.IP.IP -R 2222:localhost:22
   
[Install]
WantedBy=network-online.target
</pre>
