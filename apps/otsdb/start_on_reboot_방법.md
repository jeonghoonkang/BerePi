
# /etc/rc.local 설정 방법

- 부팅시 자동 실행을 위해 /etc/rc.local 에 아래 내용을 적용 (권한 및 경로 확인해야 함) 
- sudo /usr/local/hbase-1.2.6/bin/start-hbase.sh
- sleep 5 
- sudo /usr/local/opentsdb/build/tsdb tsd --port=54242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/data --auto-metric


# 라즈베리파이 구현 예제
- /etc/rc.local
<pre>  sudo bash /home/pi/devel/BerePi/this_startup_sw.sh </pre>

- /home/pi/devel/BerePi/this_startup_sw.sh
<pre> sudo screen -dmS startup sudo bash /home/pi/devel/BerePi/apps/otsdb/start_tsdb.sh </pre>

