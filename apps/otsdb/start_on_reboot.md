# /etc/rc.local 설정
- sudo /usr/local/hbase-1.2.6/bin/start-hbase.sh
- sleep 5 
- sudo /usr/local/opentsdb/build/tsdb tsd --port=54242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/data --auto-metric
- 권한확인 
