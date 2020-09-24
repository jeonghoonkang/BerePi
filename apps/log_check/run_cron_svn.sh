#!/bin/bash
svn up /home/pi/devel/BerePi
svn  ci -m'auto_update' /home/pi/devel/BerePi/apps/log_check/output > /home/pi/devel/BerePi/apps/log_check/error.log 2>& 1 --username id --password 'PASS'
