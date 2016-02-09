#/bin/bash

cd /usr/local/hadoop/hbase-1.1.3/bin/
sudo ./stop-hbase.sh
sudo ./start-hbase.sh

cd /usr/local/opentsdb
export JAVA_HOME=/usr 
export COMPRESSION="NONE" 
export HBASE_HOME="/usr/local/hadoop/hbase-1.1.3"
sudo ./src/create_table.sh
export tsdtmp=${TMPDIR-'/usr/local/opentsdb/tmp'}/tsd 
sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir="/usr/local/opentsdb/tmp" --auto-metric --zkquorum=iot.iptime.org:2181

cd /usr/local/tcollector
sudo ./startstop start

