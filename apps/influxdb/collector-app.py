#!/usr/bin/python
# -*- coding: utf-8 -*-
# app.py

import threading
import time

from twisted.internet import reactor
from twisted.web import server

import logger
import web
from collector import TextCollectorProtocolFactory


class Application(object):
    def __init__(self):
        super(Application, self).__init__()
        reactor.listenTCP(19100, server.Site(web.RootResource()))
        reactor.listenTCP(19101, TextCollectorProtocolFactory(), backlog=4096)
        self.__thread = None

    def start(self):
        assert not self.__thread
        self.__thread = threading.Thread(target=reactor.run, args=(False,))
        self.__thread.start()

    def stop(self):
        if self.__thread:
            reactor.callFromThread(reactor.stop)
            self.__thread.join()
            self.__thread = None

    def run(self):
        try:
            self.start()
            logger.info(__name__, "server start...")
            while True:
                time.sleep(60.0 * 5)

        finally:
            self.stop()
            logger.info(__name__, "server shutdown...")


if __name__ == '__main__':
    app = Application()
    app.run()
