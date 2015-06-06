
# Author: jeonghoon.kang@gmail.com
export gitdnpath='https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup'
wget -N $gitdnpath/setup_shell.sh
wget -N $gitdnpath/setup_apt.sh
wget -N $gitdnpath/setup_code.sh
source ./setup_apt.sh
source ./setup_shell.sh
source ./setup_code.sh

