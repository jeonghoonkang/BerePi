#!/bin/bash
git pull /Users/tinyos/devel/BerePi
git add /Users/tinyos/devel/BerePi/apps/log_check/output/*
git commit -m'auto_update' /Users/tinyos/devel/BerePi/apps/log_check/output > /Users/tinyos/devel/BerePi/apps/log_check/error.log 2>&1 
git push origin master > /Users/tinyos/devel/BerePi/apps/log_check/error.log 2>&1 
