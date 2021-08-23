#!/bin/bash
cd /home/tinyos/devel/BerePi
git pull ~/devel/BerePi
git commit -m'auto_update' ~/devel/BerePi/apps/log_check/output > ~/devel/BerePi/apps/log_check/error.log 2>&1 
git push origin master > ~/devel/BerePi/apps/log_check/error.log 2>&1 
