sudo nano /etc/xrdp/startwm.sh

<pre>

. /etc/X11/Xsession를 삭제 또는 주석 처리(맨앞에 #추가)하고 아래와 같이 수정한다.

#!/bin/sh

if [ -r /etc/default/locale ]; then
  . /etc/default/locale
  export LANG LANGUAGE
fi

#. /etc/X11/Xsession
. /usr/bin/startxfce4
</pre>

<pre>
test -x /usr/bin/startxfce4 && exec /usr/bin/startxfce4
exec /bin/sh /usr/bin/startxfce4
</pre>





Ubuntu 20.10 - xrdp/remote access

Remote login, after 'apt install xrdp', gives a static grey screen. The following appears to be one way to solve the problem ...
Code: Select all

sudo apt install xrdp
sudo systemctl status xrdp
# Remote grey screen problem and solution 

- Ubuntu 20 버전으로 넘어오면서 회색화면 이슈는 해결된것으로 보임 (2021.6 기준)

sudo adduser xrdp ssl-cert // not use
sudo systemctl restart xrdp
sudo apt-get install xfce4
echo xfce4-session > .xsession

</pre>

https://corona-world.tistory.com/26
