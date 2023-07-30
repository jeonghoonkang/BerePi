# */45 * * * * sh /home/pi/devel/BerePi/apps/tinyosGW/this_run_public_ip.sh > /home/pi/logs/crontab_debug.log 2>&1
*/45 * * * * sh /home/tinyos/devel_opment/BerePi/apps/tinyosGW/this_run_public_ip.sh > /home/tinyos/logs/crontab_debug.log 2>&1

*/45 * * * * sh /home/tinyos/devel_opment/BerePi/apps/tinyosGW/this_run_public_ip.sh {IP} {PORT} {ID} {PASS} > /home/tinyos/logs/crontab_debug.log 2>&1

