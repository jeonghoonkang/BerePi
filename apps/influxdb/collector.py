# -*- coding: utf-8 -*-
# collector.py

import json
import math
import time
import uuid

import requests
from twisted.internet import threads
from twisted.internet.protocol import Protocol, Factory, connectionDone

import logger
import tsdb
from analysis import frequency_for_average_count

SUPPORTED_ITEMS = [
    'node_id',
    'time',
    'average_count',
    'frequency',
    'columns',
    'temperature',
    'voltage',
    'rtt',
    'rms',
    'sender'
]

MANDATORY_ITEMS = [
    'node_id'
]

ITEM_TYPES = {
    'node_id': (int, long),
    'time': (int, long),
    'frequency': (int, long, float),
    'temperature': (int, long, float),
    'voltage': (int, long, float),
    'rtt': (int, long, float),
    'average_count': (int, long, float),
    'columns': (tuple, list),
    'rms': (int, long, float),
    'sender': (tuple, list)
}

VERSION = "1.0"


def save_json_object(obj):
    id_ = str(uuid.uuid4())
    url = 'http://blob.hynix-pdm.com/pdm/set/' + id_ + '/'
    mimetype = 'application/json'
    data = json.dumps(obj)
    ret = requests.post(url=url, params={'mimetype': mimetype}, data=data)
    if ret.ok:
        return id_

    # 한번만 더 시도
    ret = requests.post(url=url, params={'mimetype': mimetype}, data=data)
    if ret.ok:
        return id_

    # add recovery log
    logger.info('RECOVERY', 'blob:set_object:%s:%s:%s' % (id_, mimetype, data))
    return id_


class TextCollectorProtocol(Protocol):
    def __init__(self):
        self.__buffer = None
        self.__peer = None

    def connectionMade(self):
        p = self.transport.getPeer()
        self.__peer = '%s:%d' % (p.host, p.port)
        self.__buffer = ""
        logger.debug(__name__, 'connection made from %s:%d' % (p.host, p.port))

    def connectionLost(self, reason=connectionDone):
        p = self.transport.getPeer()
        logger.debug(__name__, 'connection made from %s:%d' % (p.host, p.port))

    def dataReceived(self, data):
        p = self.transport.getPeer()
        logger.debug(__name__, '%d bytes received from %s:%d' % (len(data), p.host, p.port))

        print "<======"
        print data #####
        print "======>"

        data = data.replace('\r\n', '\n')
        data = data.replace('\r', '\n')
        if len(self.__buffer) and self.__buffer[-1] == '\n' and len(data) and data[0] == '\n':
            data = data[1:]
        self.__buffer += data

        print data #####

        idx = self.__buffer.find('\n\n\n')
        while idx >= 0:
            chunk = self.__buffer[0:idx + 3]
            self.__buffer = self.__buffer[idx + 3:]
            threads.deferToThread(self.process_chunk, chunk)
            idx = self.__buffer.find('\n\n\n')

    @staticmethod
    def value_as_proper_type(value):
        value = value.strip()
        if ' ' in value:
            arr = value.split()
            for idx in range(len(arr)):
                arr[idx] = TextCollectorProtocol.value_as_proper_type(arr[idx])

            return arr

        else:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = long(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        pass

            return value

    def process_chunk(self, chunk):
        assert isinstance(chunk, str)

        chunk = chunk.strip()
        logger.debug(__name__, 'transaction detected:\n%s' % chunk)

        if '\n\n' in chunk:
            head, body = chunk.split('\n\n')
            head = head.strip()
            body = body.strip()

        else:
            head = chunk
            body = ''

        ctx = {}
        for l in head.split('\n'):
            k, v = l.split(':')
            k = k.strip()
            v = v.strip()
            if k in SUPPORTED_ITEMS:
                ctx[k] = self.value_as_proper_type(v)
                if not isinstance(ctx[k], ITEM_TYPES[k]):
                    logger.error(__name__, '"%s" 파라미터의 형식(type:%s)이 올바르지 않습니다.' % (k, type(ctx[k])))
                    return

            else:
                logger.warning(__name__, '"%s" 파라미터는 사용되지 않습니다 무시됩니다.' % k)

        for k in MANDATORY_ITEMS:
            if k not in ctx:
                logger.error(__name__, '"%s" 파라미터가 없습니다. 데이터 수집이 거부되었습니다.' % k)
                return

        if 'average_count' not in ctx and 'frequency' not in ctx:
            logger.error(__name__, '"average_count" 나 "frequency" 중 적어도 하나의 파라미터가 존재해야 합니다. 데이터 수집이 거부되었습니다.')
            return

        elif 'average_count' in ctx and 'frequency' not in ctx:
            ctx['frequency'] = frequency_for_average_count(ctx['average_count'])
            logger.info(__name__, '"frequency" 파라미터가 "average_count"로부터 계산됩니다.(%f)' % ctx['frequency'])

        data_points = []
        if body:
            for l in body.split('\n'):
                data_points.append(map(self.value_as_proper_type, l.split()))

            ctx['data_points_id'] = save_json_object(data_points)

        if 'time' not in ctx:
            ctx['time'] = int(time.time() * 1000000)  # to microseconds
            logger.debug(__name__, 'transaction has no "time" field, so assumed to be now(%d)' % ctx['time'])

        ctx['time'] = self.timestamp_in_microseconds(ctx['time'])
        ctx['frequency'] = float(ctx['frequency'])
        if 'temperature' in ctx:
            ctx['temperature'] = float(ctx['temperature'])

        if 'voltage' in ctx:
            ctx['voltage'] = float(ctx['voltage'])

        if 'rtt' in ctx:
            ctx['rtt'] = float(ctx['rtt'])

        if 'rms' in ctx:
            ctx['rms'] = float(ctx['rms'])

        if not ctx['time']:
            logger.error(__name__, 'transaction discarded for invalid time:%d' % ctx['time'])
            return

        dt = (1.0 / ctx['frequency']) * 1000000  # to microseconds
        ctx['start'] = ctx['time']
        ctx['end'] = int(math.ceil(ctx['time'] + (len(data_points) - 1) * dt))
        ctx['id'] = str(uuid.uuid4())
        ctx['raw_id'] = save_json_object(chunk)
        ctx['version'] = VERSION

        # record transaction
        tr = tsdb.Transaction('raw.transaction.%d' % ctx['node_id'])
        tr.write(meta=json.dumps(ctx), timestamp=ctx['time'])
        tr.flush()

        # record columns
        if 'columns' in ctx:
            for idx, c in enumerate(ctx['columns']):
                t = ctx['time']
                tr = tsdb.Transaction('raw.%s.%d' % (c, ctx['node_id']))
                for values in data_points:
                    tr.write(value=values[idx], timestamp=long(t))
                    t += dt

                tr.flush()

        # record rms, if any.
        if 'rms' in ctx:
            t = ctx['time']
            tr = tsdb.Transaction('raw.rms.%d' % ctx['node_id'])
            tr.write(value=ctx['rms'], timestamp=long(t))
            tr.flush()

        # record senders, if any
        if 'sender' in ctx:
            for gateway_id in ctx['sender']:
                tr = tsdb.Transaction('gateway.transaction.%d' % gateway_id)
                obj = {
                    'time': ctx['time'],
                    'transaction_id': ctx['id'],
                    'node_id': ctx['node_id']
                }
                tr.write(meta=json.dumps(obj), timestamp=long(t))
                tr.flush()

        # notify to web services
        try:
            url = 'http://webapp.hynix-pdm.com/pdm/event/collection_occurred/?node_id=%d' % ctx['node_id']
            if 'voltage' in ctx:
                url += '&voltage=%f' % float(ctx['voltage'])

            if 'temperature' in ctx:
                url += '&temperature=%f' % float(ctx['temperature'])

            if 'rtt' in ctx:
                url += '&rtt=%f' % float(ctx['rtt'])

            if 'sender' in ctx:
                sender_list = ','.join(ctx['sender'].split())
                url += '&sender=' + sender_list

            requests.get(url)

        except Exception:
            logger.error(__name__, 'failed to notify to webservice.')

    @staticmethod
    def timestamp_in_microseconds(timestamp):
        if len(str(timestamp)) == 10:  # seconds
            return timestamp * 1000000
        elif len(str(timestamp)) == 13:  # mili
            return timestamp * 1000
        elif len(str(timestamp)) == 16:  # micro
            return timestamp

        assert False


class TextCollectorProtocolFactory(Factory):
    protocol = TextCollectorProtocol
