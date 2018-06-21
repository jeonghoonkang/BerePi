# /etc/rc.local 설정
- 부팅시 자동 실행을 위해 /etc/rc.local 에 아래 내용을 적용 (권한, 경로 확인해야 함) 
- sudo /usr/local/hbase-1.2.6/bin/start-hbase.sh
- sleep 5 
- sudo /usr/local/opentsdb/build/tsdb tsd --port=54242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/data --auto-metric

