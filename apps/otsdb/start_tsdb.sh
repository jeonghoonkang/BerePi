#### 동작하는 스크립트 실행 (예)
#
#JAVA_HOME=/usr/lib/jvm/jdk-7-oracle-arm-vfp-hflt/jre /usr/local/hadoop/hbase-1.0.1.1/bin/start-hbase.sh
#
#JAVA_HOME=/usr/lib/jvm/jdk-7-oracle-arm-vfp-hflt/jre /usr/local/opentsdb/build/tsdb tsd --port=4242 --staticroot=/usr/local/opentsdb/build/staticroot --cachedir=/usr/local/opentsdb/tmp --auto-metric

#(/etc/rc.local 파일에 아래 내용 추가 필요)
# sudo /home/tinyos/devel/_start_up_sw.sh

# 참고
#export hadoopdir=/usr/local/hadoop
#export javadir=/usr/lib/jvm/java-8-oracle/jre
#export javadir=/usr/lib/jvm/jdk-7-oracle-arm-vfp-hflt/jre/bin/java


################################################################################

#/bin/bash
echo " "
echo "----------------------------------------------------"
echo "[BerePi] starting openTSDB by BerePi start-up script"
echo "----------------------------------------------------"

#No.1 JAVA 경로를 맞추어야 함 오라클 JDK 로 설정
export javadir='/usr/lib/jvm/jdk-7-oracle-arm-vfp-hflt/jre'
export JAVA_HOME=$javadir

#user should input correct PATH of hbase, opentsdb
export hpath=/usr/local/hadoop/hbase-1.0.1.1
export tsdbpath=/usr/local/opentsdb

echo $hpath
cd $hpath
#export hrunpath='JAVA_HOME='$JAVA_HOME' '$hpath'/bin/start-hbase.sh'
hrunpath='sudo '$hpath'/bin/start-hbase.sh'
hstoppath='sudo '$hpath'/bin/stop-hbase.sh'
echo '>> check point -  print hbase run path'
echo $JAVA_HOME

if [ expr $1 == 'stop' ]
then
    echo $hstoppath
    $hstoppath
    exit " finish Hbase STOP"
fi

pushd $tsdbpath
tsdbrunpath=$tsdbpath'/build/tsdb'
srpath=$tsdbpath'/build/staticroot'
cachepath=$tsdbpath'/tmp'
cmd='sudo '$tsdbrunpath' tsd --port=4242 --staticroot='$srpath' --cachedir='$cachepath' --auto-metric'

echo $hrunpath 
$hrunpath 
sleep 30 
echo $cmd
$cmd

popd

echo "[BerePi] last step of run openTSDB, tcollector by BerePi start-up script"
echo "------------------------------------------------------------------------"
echo " "

# 변경사항. 2018-07-14
#     cd tcollector
#     sudo python tcollector.py -H <TSDB Host IP> -p <TSDB port> -D
#     cd /usr/local/tcollector
#     sudo ./startstop start
