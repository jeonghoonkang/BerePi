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

https://corona-world.tistory.com/26
