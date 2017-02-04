

#!/bin/bash
# Author: jeonghoon.kang@gmail.com

echo "Help: source init.sh co <-- checkout" 
echo "      source init.sh up <-- update" 


export gitdnpath='https://raw.githubusercontent.com/jeonghoonkang/BerePi/master/setup'

if [ $1 = 'co' ]; 
then
    echo ".... checking out"
    wget -N $gitdnpath/setup_shell.sh
    wget -N $gitdnpath/setup_apt.sh
    wget -N $gitdnpath/setup_code.sh
    source ./setup_apt.sh
    source ./setup_shell.sh
    source ./setup_code.sh co
elif [ $1 = 'up' ]; 
then
    echo ".... update"
    ./setup_code.sh up
else
    echo ".... no action... please add argument "
fi

unset gitdnpath
echo ".... ending init.sh"
