#!/bin/bash

# 파이션 코드 실행스크립트
# version 1.1
# 버전 주요 변경 사항 : 아규먼트 18개로 추가

# read 할 csv 정보 및 opentsdb 정보

# [1] opentsdb ip
#ip=db
ip=None

# [2] opentsdb port
port=None

# [3] target field name
field=None
#field=$FIELDNAME

# [4] time field name
ts=None
#ts=$TIMEFIELD

# [5] ID fieldname
id=None

# [6] opentsdb metric
metric=None
#metric=$METRIC


echo ">>===================================================="
echo "실행 관련 주요 정보(this_run.sh)"
echo "opentsdb ip : "$ip
echo "opentsdb port    : " $port
echo "target field name  : "$field
echo "time field name   : "$ts
echo "metric    : "$metric
echo "====================================================<<"
echo


# time 은 스크립트 SW 실행 시간을 확인하기 위해 사용
# 인자값 7개
#                   [1] [2]       [3]           [4]         [5]       [6]
#python FILE2TSDB.py $ip $port "\""$field"\"" "\""$ts"\"" "\""$id"\"" $metric 
python FILE2TSDB.py $ip $port $field $ts $id $metric 


echo " *** end script run for PYTHON *** "