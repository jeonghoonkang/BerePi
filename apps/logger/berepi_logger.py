# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import logging
#import logging.config
from logging.handlers import RotatingFileHandler
import sys

#logging.config.fileConfig('logging.conf')
LOG_FILENAME = "/home/tinyos/devel_opment/BerePi/logs/berelogger.log"
#LOG_FILENAME = "/Users/tinyos/devel/BerePi/logs/berelogger.log"

logger = logging.getLogger('BereLogger')
logger.setLevel(logging.DEBUG)

# Choose TimeRoatatingFileHandler or RotatingFileHandler 
#handler = logging.handlers.TimedRotatingFileHandler(filename=LOG_FILENAME, when="midnight", interval=1, encoding="utf-8")
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, mode='a', maxBytes=200000, backupCount=9)
handler.formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

logger.addHandler(handler)

# API for outside 
def berelog(msg_name, value=None):
    print ("logging to", LOG_FILENAME, 'log file name')
    if (value == None):
        logger.info(msg_name )
    elif (value != None):
        logger.info(msg_name + ' ==> ' + value)

def args_proc():
 
    num_of_args = len(sys.argv)
    if num_of_args < 2:
       print('current number of args -->  ', num_of_args )
       exit("[bye] you have to write input args ")

    arg=[0 for i in range(num_of_args)]
    for loop_num in range(num_of_args): 
        #print ('##loop_num :', loop_num)
        #print (arg[loop_num])
        arg[loop_num] = sys.argv[loop_num]
    return arg


if __name__ == "__main__":

    args = args_proc()
    berelog('logging cpu temp', args[1])
    
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


