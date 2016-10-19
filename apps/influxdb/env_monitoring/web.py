# -*- coding: utf-8 -*-
# web.py


import json

from twisted.internet import threads
from twisted.web import server, resource
from twisted.web.resource import Resource

import logger
import tsdb


class ExporterResource(Resource):
    isLeaf = True

    def __init__(self):
        self.__client = tsdb.influx_client()

    def render(self, request):
        #
        request.responseHeaders.addRawHeader(b"content-type", b"application/json")

        # from
        try:
            from_ = int(request.args['from'][0])

        except KeyError:
            from_ = None

        except ValueError:
            return json.dumps({'code': 'failure', 'reason': 'invalid parameter: from=%s' % request.args['from'][0]})

        # to
        try:
            to_ = int(request.args['to'][0])

        except KeyError:
            to_ = None

        except ValueError:
            return json.dumps({'code': 'failure', 'reason': 'invalid parameter: to=%s' % request.args['to'][0]})

        # node_id
        try:
            node_id = int(request.args['node_id'][0])

        except KeyError:
            node_id = None

        except ValueError:
            return json.dumps(
                {'code': 'failure', 'reason': 'invalid parameter: node_id=%s' % request.args['node_id'][0]})

        # pretty
        try:
            pretty = request.args['pretty'][0]
            if pretty not in ('true', 'false'):
                return json.dumps(
                    {'code': 'failure', 'reason': 'invalid parameter: pretty=%s' % request.args['pretty'][0]})
            pretty = (pretty == 'true')

        except KeyError:
            pretty = False

        #
        threads.deferToThread(self.select_from_database, request, from_, to_, node_id, pretty)
        return server.NOT_DONE_YET

    def select_from_database(self, request, from_, to_, node_id, pretty):
        assert from_ is None or isinstance(from_, (int, long))
        assert to_ is None or isinstance(to_, (int, long))
        assert node_id is None or isinstance(node_id, (int, long))
        assert isinstance(pretty, bool)

        # plug ID
        reg = None
        if node_id is None:
            reg = '/^raw.transaction.*/'
        else:
            reg = '"raw.transaction.%d"' % node_id

        # 기간에 따라
        if from_ is not None and to_ is not None:
            rs = self.__client.query('select * from %s where time > %du and time < %du' % (reg, from_, to_),
                                     time_precision='s')
        elif from_ is not None:
            rs = self.__client.query('select * from %s where time > %du' % (reg, from_), time_precision='u')
        elif to_ is not None:
            rs = self.__client.query('select * from %s where time < %du' % (reg, to_), time_precision='u')
        else:
            rs = self.__client.query('select * from %s' % reg, time_precision='u')

        result = {
            'from': from_,
            'to': to_,
            'node_id': node_id,
            'payload': {}
        }
        for obj in rs:
            metric_name = obj['name']
            time_index = obj['columns'].index('time')
            meta_index = obj['columns'].index('meta')
            result['payload'][metric_name] = []
            for row in obj['points']:
                t = row[time_index]
                v = row[meta_index]
                result['payload'][metric_name].append((t, v))

            result['payload'][metric_name].sort()

        body = json.dumps({'code': 'success', 'result': result}, **{'sort_keys': True, 'indent': 4} if pretty else {})
        logger.info(__name__, body)

        try:
            request.write(body)
            request.finish()

        except Exception:
            pass


class RootResource(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild('crawler', ExporterResource())
