#/bin/bash
echo " "
echo "----------------------------------------------------"
echo "[BerePi] starting openTSDB by BerePi start-up script"

cd /usr/local/hadoop/hbase-1.0.1.1/
#sudo sh ./bin/stop-hbase.sh
sudo sh ./bin/start-hbase.sh && sleep 90

cd /usr/local/opentsdb
sudo screen -dmS tsd_start sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric

sleep 10

cd /usr/local/tcollector
sudo ./startstop start

echo "[BerePi] last step of run openTSDB, tcollector by BerePi start-up script"
echo "------------------------------------------------------------------------"
echo " "

