# -*- coding: utf-8 -*-
# author : http://github.com/jeonghoonkang

import sys
sys.path.append("~/devel/BerePi/apps/logger")

import berepi_logger


if __name__ == "__main__":

    berepi_logger.berelog('unit test bere logging', 'success')