#!/bin/bash

sudo apt update
sudo apt install apache2

sudo a2enmod cgid
sudo a2enconf serve-cgi-bin

#sudo cp /etc/apache2/conf-available/serve-cgi-bin.conf /etc/apache2/conf-available/serve-cgi-bin.conf.bak

#FILE_NAME='/etc/apache2/conf-available/serve-cgi-bin.conf'
#ORIGINAL="</Directory>"
#CHANGE="</Directory>
#                ScriptAlias /gw/ /home/pi/Documents/BerePi/apps/tinyosGW/
#                <Directory \"/home/pi/Documents/BerePi/apps/tinyosGW/\">
#                        AllowOverride None
#                        Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
#                        Require all granted
#                </Directory>"

#FILE_NAME='\/etc\/apache2\/conf-available\/serve-cgi-bin.conf'
#ORIGINAL="\<\/Directory\>"
#CHANGE="\<\/Directory\>
#                ScriptAlias \/gw\/ \/home\/pi\/Documents\/BerePi\/apps\/tinyosGW\/
#                \<Directory \\\"\/home\/pi\/Documents\/BerePi\/apps\/tinyosGW\/\\\"\>
#                        AllowOverride None
#                        Options \+ExecCGI \-MultiViews \+SymLinksIfOwnerMatch
#                        Require all granted
#                \<\/Directory\>"

#sed --in-place "s/$ORIGINAL/$CHANGE/g" $FILE_NAME
#sed "s/$ORIGINAL/$CHANGE/g" $FILE_NAME

