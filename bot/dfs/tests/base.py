# -*- coding: utf-8 -*-
import subprocess
import unittest
from time import sleep

import os

from bot.dfs.bridge.caching import Db
from bottle import Bottle, request, response
from gevent.pywsgi import WSGIServer
from redis import StrictRedis

config = {
    'main':
        {
            'tenders_api_server': 'http://127.0.0.1:20604',
            'tenders_api_version': '2.3',
            'public_tenders_api_server': 'http://127.0.0.1:20605',
            'buffers_size': 450,
            'full_stack_sync_delay': 15,
            'empty_stack_sync_delay': 101,
            'on_error_sleep_delay': 5,
            'api_token': "api_token",
            'cache_db_name': 1,
            'cache_host': '127.0.0.1',
            'cache_port': '16379',
            'time_to_live': 1800,
            'delay': 1,
            'time_to_live_negative': 120
        }
}


class BaseServersTest(unittest.TestCase):
    """Api server to test openprocurement.integrations.edr.databridge.bridge """

    relative_to = os.path.dirname(__file__)  # crafty line

    @classmethod
    def setUpClass(cls):
        cls.api_server_bottle = Bottle()
        cls.api_server = WSGIServer(('127.0.0.1', 20604), cls.api_server_bottle, log=None)
        setup_routing(cls.api_server_bottle, response_spore)
        cls.public_api_server = WSGIServer(('127.0.0.1', 20605), cls.api_server_bottle, log=None)
        cls.redis_process = subprocess.Popen(['redis-server', '--port',
                                              str(config['main']['cache_port']), '--logfile /dev/null'])
        sleep(0.1)
        cls.redis = StrictRedis(port=str(config['main']['cache_port']), db=1)
        cls.db = Db(config)

        # start servers
        cls.api_server.start()
        cls.public_api_server.start()

    @classmethod
    def tearDownClass(cls):
        cls.api_server.close()
        cls.public_api_server.close()
        cls.redis_process.terminate()
        cls.redis_process.wait()

    def tearDown(self):
        del self.worker


def setup_routing(app, func, path='/api/{}/spore'.format(config['main']['tenders_api_version']), method='GET'):
    app.route(path, method, func)


def response_spore():
    response.set_cookie("SERVER_ID", ("a7afc9b1fc79e640f2487ba48243ca071c07a823d27"
                                      "8cf9b7adf0fae467a524747e3c6c6973262130fac2b"
                                      "96a11693fa8bd38623e4daee121f60b4301aef012c"))
    return response


def doc_response():
    return response


def proxy_response():
    if request.headers.get("sandbox-mode") != "True":  # Imitation of health comparison
        response.status = 400
    return response
