# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import logging
#import logging.config
from logging.handlers import RotatingFileHandler

#logging.config.fileConfig('logging.conf')
LOG_FILENAME = "/home/tinyos/devel/BerePi/logs/berelogger.log"

logger = logging.getLogger('BereLogger')
logger.setLevel(logging.DEBUG)

# Choose TimeRoatatingFileHandler or RotatingFileHandler 
#handler = logging.handlers.TimedRotatingFileHandler(filename=LOG_FILENAME, when="midnight", interval=1, encoding="utf-8")
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, mode='a', maxBytes=2000, backupCount=1)
handler.formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

logger.addHandler(handler)

def berelog(msg_name, value=None):
    print (LOG_FILENAME, 'log file name')
    if (value == None):
        logger.info(msg_name )
    elif (value != None):
        logger.info(msg_name + ' ==> ' + value)

def args_proc():
 
    msg = "usage : python %s {} {} {} {}" %__file__
    msg += " => user should input arguments {} "
    print (msg, '\n')
  
    if len(sys.argv) < 2:
       exit("[bye] you need to input args, ip / port / id")
 
    arg1 = sys.argv[1]
    arg2 = sys.argv[2]
    arg3 = sys.argv[3]
    arg4 = sys.argv[4]
 
    ip   = arg1
    port = arg2
    id   = arg3
    passwd = arg4
 
    print ("... start running, inputs are ", ip, port, id, passwd)
 
    return ip, port, id, passwd


if __name__ == "__main__":

    berelog('temperature', '25')
    berelog('temperature')
    
    # 'application' code
    #logger.debug('debug message')
    #logger.info('info message')
    #logger.warn('warn message')
    #logger.error('error message')
    #logger.critical('critical message')
    """
      if you want to use, this berepi_logger
      import logging, and use berelog('*****')
    """


'''
To do:
    LOG_FILENAME has to have sensor name on the file name
'''


