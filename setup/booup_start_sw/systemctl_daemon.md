### System Daemon
- sudo vi /etc/systemd/system/wol.service
- file text
<pre>
[Unit]
Description=Configure Wake-up on LAN

[Service]
Type=oneshot
ExecStart=/sbin/ethtool -s 인터페이스명(eth0) wol g

[Install]
WantedBy=basic.target
</pre>

### Setup and Run
- sudo systemctl enable /etc/systemd/system/wol.service

