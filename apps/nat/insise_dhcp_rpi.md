https://gist.github.com/cellularmitosis/8294f0800e6d4b4022772fe8869d8a6f

Configure Raspbian

Boot the Pi
Login as pi, password raspberry
sudo raspi-config
Localisation Options -> Change Locale (to en_US.UTF-8)
Localisation Options -> Change Timezone (to America / Chicago)
Localisation Options -> Keyboard Layout (to Generic 104, Other -> English US)
Interfacing Options -> SSH (enable)
Make note of the IP address (ifconfig eth0)
Logout
Login via ssh as pi, then sudo -i
Change root's password (run passwd)
Append your ~/.ssh/id_rsa.pub to /root/.ssh/authorized_keys
Logout
Login via ssh as root
deluser pi && rm -rf /home/pi





