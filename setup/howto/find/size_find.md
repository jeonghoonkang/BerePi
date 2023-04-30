
### Find file by size


- sudo find /var -size +200M -exec ls -sh {} +

<pre>

 6.0G /var/log/auth.log
 3.7G /var/log/daemon.log
 1.6G /var/log/kern.log
 1.8G /var/log/messages
 5.6G /var/log/syslog
 1.6G /var/log/ufw.log

</pre>

### and reduce size of log files, issue of Rasbian OS

- sudo vim /etc/cron.daily/logrotate

- sudo /usr/sbin/logrotate /etc/logrotate.conf

- sudo vim /etc/logrotate.conf

<pre>
# see "man logrotate" for details
# rotate log files weekly
weekly
maxsize 1G
</pre>
