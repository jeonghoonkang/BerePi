
### Find file based on size

<pre>
sudo find /var -size +200M -exec ls -sh {} +

 6.0G /var/log/auth.log
 3.7G /var/log/daemon.log
 1.6G /var/log/kern.log
 1.8G /var/log/messages
 5.6G /var/log/syslog
 1.6G /var/log/ufw.log

</pre>
