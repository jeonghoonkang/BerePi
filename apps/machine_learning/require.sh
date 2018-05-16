
# Author : Jeonghoon.Kang (http://github.com/jeonghoonkang)

# This script for Ubuntu (in the Windows10)
# python lib requred for matplot & scikit-learn  

# windows10 should have X-Server SW
# visit https://sourceforge.net/projects/vcxsrv/ and install

# For BASH : export DISPLAY=localhost:0.0
# sudo apt-get install x11-apps
# X-server run check : xeyes

#sudo apt-get -y install subversion

wget https://pypi.python.org/packages/source/d/distribute/distribute-0.7.3.zip
unzip distribute-0.7.3.zip
cd distribute-0.7.3
sudo python setup.py install
sudo easy_install pip

sudo apt-get install gcc
sudo apt-get install make

sudo pip install -U scikit-learn
sudo pip install -U scipy

sudo pip install matplotlib
sudo pip install requests --upgrade
sudo pip install twisted --upgrade
sudo pip install numpy
sudo pip install networkx
sudo pip install httplib
sudo pip install urllib3
sudo pip install utils


# (for PIP)
# python -m ensurepip --default-pip

