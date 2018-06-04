#!/bin/bash 
# filename _start_up_sw.sh

export hadoopdir=/usr/local/hadoop
export javadir=/usr/lib/jvm/java-8-oracle/jre
export otsdbdir=/usr/local/opentsdb'
pushd $hadoopdir
JAVA_HOME=$javadir ./hbase-1.1.13/bin/start-hbase.sh
sleep 7

pushd $ostdbdir
JAVA_HOME=/usr/lib/jvm/java-8-oracle/jre ./build/tsdb tsd --port=4242 --staticroot=build/staticroot --cachedir=/usr/local/opentsdb/cache_tmp --auto-metric

popd
popd

#(/etc/rc.local 파일에 아래 내용 추가 필요)
# sudo /home/tinyos/devel/_start_up_sw.sh

################################################################################

#/bin/bash
echo " "
echo "----------------------------------------------------"
echo "[BerePi] starting openTSDB by BerePi start-up script"
echo "----------------------------------------------------"

cd /usr/local/hadoop/hbase-1.0.1.1/
#sudo sh ./bin/stop-hbase.sh
sudo sh ./bin/start-hbase.sh && sleep 90 # raspberryPi zero 에서는 90초 정도 후 Hbase 시작

cd $otsdbdir 
sudo screen -dmS tsd_start sudo sh /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric


# 변경사항. 2018-05-8
#sleep 10

#cd /usr/local/tcollector
#sudo ./startstop start

#echo "[BerePi] last step of run openTSDB, tcollector by BerePi start-up script"
#echo "------------------------------------------------------------------------"
#echo " "
#     cd tcollector
#     sudo python tcollector.py -H <TSDB Host IP> -p <TSDB port> -D

unset hadoopdir
unset javadir
unset otsdbdir
