
export tmppath=/home/pi/devel/BerePi/apps/lcd_berepi
cd $tmppath
pwd
echo "[BerePi] starting watch app"
screen -dmS lcddisp sudo python watch.py -ip x.x.x.53:4242
unset tmppath
cd
