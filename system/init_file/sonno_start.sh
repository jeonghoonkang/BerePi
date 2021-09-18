# should have $SONNO_HOME 
# this file location $SONNO_HOME/BerePi/system/init_file
echo "(sonn_check) Please check environment variable SONNO_HOME, it is abolutely to be required " 
echo "SONNO_HOME = "$SONNO_HOME
python3 $SONNO_HOME/BerePi/apps/logger/berepi_logger.py 'sonno_example'
