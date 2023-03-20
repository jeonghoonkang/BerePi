1,31 * * * * echo "" | sudo -S cp /usr/sbin/shutdown /media/ramdisk > /home//devel_opment/log/crontab.cp.shutdown.log 2>&1

2,32 * * * * echo "" | sudo -S /media/ramdisk/shutdown -r > /home//devel_opment/log/crontab.shutdown.log 2>&1 && sleep 1 &&  /usr/sbin/shutdown -c
