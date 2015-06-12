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

# http://125.7.128.54:8070/wordpress/pub/devel/HEMS.apk

