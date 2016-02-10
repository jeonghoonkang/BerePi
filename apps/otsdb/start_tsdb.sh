#/bin/bash

sudo cd /usr/local/hadoop/hbase-1.0.1.1/
#sudo ./bin/stop-hbase.sh
sudo ./bin/start-hbase.sh

sudo cd /usr/local/opentsdb
sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric 

sudo cd /usr/local/tcollector
sudo ./startstop start

