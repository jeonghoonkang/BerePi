
cd /usr/local/hadoop/hbase-1.1.3/bin/
sudo ./stop-hbase.sh
sudo ./start-hbase.sh

cd /usr/local/opentsdb
JAVA_HOME=/usr COMPRESSION="NONE" HBASE_HOME="/usr/local/hadoop/hbase-1.1.3"
sudo ./src/create_table.sh
tsdtmp=${TMPDIR-'/usr/local/hadoop'}/tsd 
sudo screen -dmS tsdb ./build/tsdb tsd --port=4242 --staticroot=build/staticroot --cachedir=/usr/local/data --auto-metric &

cd /usr/local/tcollector
sudo ./startstop start

