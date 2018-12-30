#!/bin/bash
#installation for windows, please visit https://github.com/source-foundry/Hack-windows-installer/releases/latest

wget https://github.com/source-foundry/Hack/releases/download/v3.003/Hack-v3.003-ttf.zip

unzip *.zip

sudo cp ttf /usr/share/fonts/truetype -R

fc-cache -f -v

fc-list | grep Hack

