#!/bin/bash
#author : https://github.com/jeonghoonkang

hstoppath='.'

if [ expr $1 == 'stop' ]
then
    echo $hstoppath
    $hstoppath
    exit " finish Hbase STOP"
fi

echo "working"

