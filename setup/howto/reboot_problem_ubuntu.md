<pre>

# 1. daily-timer 확인.
systemctl list-timers | grep apt-daily
Sat 2022-05-14 17:52:23 KST 6h left        Sat 2022-05-14 03:10:49 KST 7h ago       apt-daily.timer              apt-daily.service
Sun 2022-05-15 06:06:08 KST 19h left       Sat 2022-05-14 06:29:39 KST 4h 30min ago apt-daily-upgrade.timer      apt-daily-upgrade.service

# 2. 마지막 재부팅 시간 확인.
last reboot
reboot   system boot  5.13.0-41-generi Sat May 14 07:10   still running

# 3. 타이머 비활성화.
#    stop은 타이머 중지, disable은 script 비활성화 하는 동작.
systemctl stop apt-daily.timer
systemctl disable apt-daily.timer
systemctl disable apt-daily-upgrade.service
systemctl stop apt-daily-upgrade.timer
systemctl disable apt-daily-upgrade.timer
systemctl disable apt-daily-upgrade.service

# 4. 타이머 확인.
systemctl list-timers | grep apt-daily

</pre>
