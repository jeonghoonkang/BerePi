
export DNPATH='http://125.7.128.54:8070/wordpress/pub/devel/setup_linux'

export bashrc_file=$DNPATH/.bashrc
wget -N $bashrc_file

export vimrc_file=$DNPATH/.vimrc
wget -N $vimrc_file

export net_file=$DNPATH/interfaces
wget -N $net_file
chmod 776 interfaces

export dns_file=$DNPATH/resolv.conf
wget -N $dns_file

export rc_file=$DNPATH/rc.local
wget -N $rc_file
chmod 775 rc.local

export rctest_file=$DNPATH/rc.local.test
wget -N $rctest_file

export vimjelly_file=$DNPATH/vim_conf/jellybeans.vim
wget -N $vimjelly_file

unset DNPATH
unset bashrc_file
unset vimrc_file
unset net_file
unset dns_file
unset rc_file
unset rctest_file
unset vimjelly_file

