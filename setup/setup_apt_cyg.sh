#Author : Jeonghoon.Kang (http://github.com/jeonghoonkang)

#########################################################################
#### for the Cygwin, windows
####

#apt-cyg download and run to install
#wget https://raw.githubusercontent.com/digitallamb/apt-cyg/master/apt-cyg
# cp apt-cyg /usr/bin
# chmod 777 /usr/bin/apt-cyg

#gcc installation, try
apt-cyg install gcc-core
apt-cyg install cygwin32-freetype2
apt-cyg install pkg-config
apt-cyg install libX11-devel
apt-cyg install make
apt-cyg install cmake
apt-cyg install xinit
apt-cyg install libQt5Core-devel
apt-cyg install python-devel
apt-cyg install gcc-g++ libzmq-devel libzmq5


#instead of pip install numpy
apt-cyg install python-numpy
#apt-cyg install libfreetype-devel

pip install requests --upgrade
pip install twisted --upgrade
#pip installation
# wget https://raw.githubusercontent.com/pypa/pip/master/contrib/get-pip.py
# python get-pip.py

# numpy installation takes a few minutes

#pip install numpy
pip install matplotlib
pip install scimath
pip install networkx
pip install pandas

#########################################################################
#### some commands

# tasklist
# ps -W


### FYI, Serial and pip in Cygwin
# apt-cyg install python-setuptools
#easy_install-2.7 pip
# pip install pyserial
# ( https://github.com/pyserial/pyserial/ )
