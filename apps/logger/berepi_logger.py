# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import logging
#import logging.config
from logging.handlers import RotatingFileHandler

#logging.config.fileConfig('logging.conf')
LOG_FILENAME = "./log/berelogger.log"

logger = logging.getLogger('BereLogger')
logger.setLevel(logging.DEBUG)

handler = logging.handlers.TimedRotatingFileHandler(filename=LOG_FILENAME, when="midnight", interval=1, encoding="utf-8")
#handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, mode='a', maxBytes=10, backupCount=10)
handler.formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

logger.addHandler(handler)

def berelog(msg_name, value):
    logger.info(msg_name + ' ==> ' + value)

if __name__ == "__main__":

    berelog('sesnor type co2', '25')
    
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
