# Author : jeonghoon.kang@gmail.com

export DNPATH='https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup'

export bashrc_file=$DNPATH/.bashrc
wget -N $bashrc_file
sudo scp .bashrc /root

export vimrc_file=$DNPATH/.vimrc
wget -N $vimrc_file
sudo scp .vimrc /root

export net_file=$DNPATH/interfaces
wget -N $net_file
sudo mv interfaces /etc/network
sudo chmod 776 /etc/network/interfaces

export dns_file=$DNPATH/resolv.conf
wget -N $dns_file
sudo mv resolv.conf /etc

export rc_file=$DNPATH/rc.local
wget -N $rc_file
sudo mv rc.local /etc
sudo chmod 775 /etc/rc.local

export rctest_file=$DNPATH/rc.local.test
wget -N $rctest_file

export vimjelly_file=$DNPATH/vim_conf/jellybeans.vim
wget -N $vimjelly_file
sudo mv jellybeans.vim /usr/share/vim/vim73/colors

unset DNPATH
unset bashrc_file
unset vimrc_file
unset net_file
unset dns_file
unset rc_file
unset rctest_file
unset vimjelly_file

