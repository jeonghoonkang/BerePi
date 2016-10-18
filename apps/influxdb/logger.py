# -*- coding: utf-8 -*-
# logger.py

import logging
import sys

__loggers = {}


def instance(name):
    assert isinstance(name, str)

    if name in __loggers:
        return __loggers[name]

    else:
        logger = logging.getLogger(name)
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        #handler = logging.StreamHandler(stream=sys.stdout)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        __loggers[name] = logger
        return logger


def info(name, message, *args, **keyw):
    return instance(name).info(message, *args, **keyw)


def debug(name, message, *args, **keyw):
    return instance(name).debug(message, *args, **keyw)


def warning(name, message, *args, **keyw):
    return instance(name).warning(message, *args, **keyw)


def error(name, message, *args, **keyw):
    return instance(name).error(message, *args, **keyw)


def exception(name, message, *args, **keyw):
    return instance(name).exception(message, *args, **keyw)
