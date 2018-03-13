#/bin/bash
echo " "
echo "----------------------------------------------------"
echo "[BerePi] starting openTSDB by BerePi start-up script"
echo "----------------------------------------------------"

cd /usr/local/hadoop/hbase-1.0.1.1/
#sudo sh ./bin/stop-hbase.sh
sudo sh ./bin/start-hbase.sh && sleep 90 # raspberryPi zero 에서는 90초 정도 후 Hbase 시작

cd /usr/local/opentsdb
sudo screen -dmS tsd_start sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric

sleep 10

cd /usr/local/tcollector
sudo ./startstop start

echo "[BerePi] last step of run openTSDB, tcollector by BerePi start-up script"
echo "------------------------------------------------------------------------"
echo " "

# 변경사항. 2017-05-29
#     cd tcollector
#     sudo python tcollector.py -H <TSDB Host IP> -p <TSDB port> -D
