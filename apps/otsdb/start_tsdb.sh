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

#user should input correct PATH of hbase, opentsdb
export hpath=/usr/local/hadoop/hbase-1.0.1.1
export tsdbpath=/usr/local/opentsdb

cd $hpath
export hrunpath=$hpath'/bin/start-hbase.sh'
#sudo sh ./bin/stop-hbase.sh
sudo sh $hrunpath

sleep 90 # raspberryPi zero 에서는 90초 정도 후 Hbase 시작

cd $tsdbpath
export tsdbrunpath=$tsdbpath'/build/tsdb'
export srpath=$tsdbpath'/build/staticroot'
export cachepath=$tsdbpath'/tmp'

sudo screen -dmS tsd_start sudo sh $tsdbrunpath tsd --port=4242 --staticroot=$srpath --cachedir=$cachepath --auto-metric

sleep 2

echo "[BerePi] last step of run openTSDB, tcollector by BerePi start-up script"
echo "------------------------------------------------------------------------"
echo " "

# 변경사항. 2018-07-14
#     cd tcollector
#     sudo python tcollector.py -H <TSDB Host IP> -p <TSDB port> -D
#     cd /usr/local/tcollector
#     sudo ./startstop start
