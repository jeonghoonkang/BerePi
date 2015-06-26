#!/bin/bash
#Author: jeonghoonkang http://github.com/jeonghoonkang

if [ $1 = 'up' ]; then
then
    echo "... updating"
    cd
    cd devel/BerePi/
    svn up --force
    cd /home/pi/devel/stalk/
    svn up --force
    cd
    
elif [ $1 = 'co' ]; then
    echo "... installing"
    cd
    mkdir devel
    cd devel
    svn co http://github.com/jeonghoonkang/BerePi/trunk BerePi  
    git clone git://git.drogon.net/wiringPi wiringPi
    svn co svn://125.7.128.53/danalytics --username=tinyos

    svn co https://github.com/321core/EnergyManagementSystem/trunk stalk
    cd /home/pi/devel/stalk/code/client
    cp start.sh /home/pi
    cd
else
   echo "... do notihing for code install / update"
fi

# http://125.7.128.54:8070/wordpress/pub/devel/HEMS.apk

