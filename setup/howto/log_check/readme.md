# How to check log of ubuntu /var/log system
<pre>
journalctl --since "2 days ago"  
journalctl --since "today"
journalctl --since "yesterday --until "today" 
journalctl --since "2019-03-10" --until "2019-03-11 03:00"
journalctl -b # since last boot 
journalctl --boot=-1 # since previous boot 
journalctl -k # kernel messages
journalctl -p err # by priority like (emerg|alert|crit|err|warning|info|debug)
journalctl -u sshd # for a particular unit 
journalctl _UID=1000 # for a particular user id
</pre>
