#!/usr/bin/python

import time
import logging
import logging.handlers

import rpiMonitor as rpi

'''debug-level
logging.debug('')
logging.info('')
logging.warning('')
logging.error('')
logging.critical('')
'''

PROCESS = "python"

FILE_MAX_BYTE = 1024 * 4 * 1 #100MB
FILE_MAX_COUNT = 1
#FILENAME = '/home/pi/rpi_log.log'
FILENAME = '/home/pi/devel/BerePi/apps/tinyosGW/out/rpi_sys_service_log.log'
formatter = logging.Formatter('[%(levelname)s] %(asctime)s > %(message)s')

logger = logging.getLogger('rpi_logger')

#fileHandler = logging.FileHandler(FILENAME)
fileHandler = logging.handlers.RotatingFileHandler(FILENAME, \
                                    maxBytes=FILE_MAX_BYTE, \
                                    backupCount=FILE_MAX_COUNT)
streamHandler = logging.StreamHandler()
fileHandler.setFormatter(formatter)
streamHandler.setFormatter(formatter)

logger.addHandler(fileHandler)
logger.addHandler(streamHandler)
logger.setLevel(logging.DEBUG)

logger.info("##### RUN START")
logger.info("PUBLIC IP : %s" %rpi.get_pip() )
logger.info("HOSTNAME : %s" % rpi.get_hostname())
logger.info("SSH_PROXY : %s" % rpi.get_proxy())
logger.info("IP : \n%s" % rpi.get_ifconfig())
logger.info("ROUTE : \n%s" % rpi.get_route())
logger.info("HDD :\n %s " % rpi.get_df())
logger.info("FREE MEM : \n%s" % rpi.get_free())
logger.info("CPU(%s) : %s" % (PROCESS, rpi.get_proc_cpu(PROCESS)) )
logger.info("MEM(%s) : %s" % (PROCESS, rpi.get_proc_mem(PROCESS)) )
logger.info("     RUN FINISH #####")


