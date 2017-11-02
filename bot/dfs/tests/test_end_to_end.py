# -*- coding: utf-8 -*-
from gevent import monkey

monkey.patch_all()

import uuid

from simplejson import dumps
from gevent.queue import Queue
from bottle import response, request

from base import BaseServersTest, config
from bot.dfs.bridge.constants import tender_status, AWARD_STATUS
from bot.dfs.bridge.sleep_change_value import APIRateController
from bot.dfs.bridge.process_tracker import ProcessTracker
from bot.dfs.bridge.bridge import EdrDataBridge
from utils import generate_request_id

CODES = ('14360570', '0013823', '23494714')
award_ids = [uuid.uuid4().hex for _ in range(5)]
request_ids = [generate_request_id() for _ in range(2)]
bid_ids = [uuid.uuid4().hex for _ in range(5)]

s = 0


def setup_routing(app, func, path='/api/2.3/spore', method='GET'):
    global s
    s = 0
    app.route(path, method, func)


def response_spore():
    response.set_cookie("SERVER_ID", ("a7afc9b1fc79e640f2487ba48243ca071c07a823d27"
                                      "8cf9b7adf0fae467a524747e3c6c6973262130fac2b"
                                      "96a11693fa8bd38623e4daee121f60b4301aef012c"))
    return response


def doc_response():
    return response


def awards(counter_id, counter_bid_id, status, sup_id):
    return {'id': award_ids[counter_id], 'bid_id': bid_ids[counter_bid_id], 'status': status,
            'suppliers': [{'identifier': {'scheme': 'UA-EDR', 'id': sup_id, "legalName": "company_name"}}]}


def bids(counter_id, edr_id):
    return {'id': bid_ids[counter_id], 'tenderers': [{'identifier': {'scheme': 'UA-EDR', 'id': edr_id}}]}


def proxy_response():
    if request.headers.get("sandbox-mode") != "True":  # Imitation of health comparison
        response.status = 400
    return response


def get_tenders_response():
    response.content_type = 'application/json'
    response.headers.update({'X-Request-ID': request_ids[0]})
    global s
    if s == 0:
        s -= 1
        return get_tenders_response_sux()
    else:
        return get_empty_response()


def get_tenders_response_sux():
    return dumps({'prev_page': {'offset': '123'}, 'next_page': {'offset': '1234'},
                  'data': [{'status': tender_status, "id": '123', 'procurementMethodType': 'aboveThresholdEU'}]})


def get_empty_response():
    return dumps({'prev_page': {'offset': '1234'}, 'next_page': {'offset': '12345'}, 'data': []})


def get_tender_response():
    response.status = 200
    response.content_type = 'application/json'
    response.headers.update({'X-Request-ID': request_ids[0]})
    return dumps({'prev_page': {'offset': '123'}, 'next_page': {'offset': '1234'},
                  'data': {'status': tender_status, 'id': '123', 'procurementMethodType': 'aboveThresholdEU',
                           'awards': [awards(2, 2, AWARD_STATUS, CODES[2])]}})


class EndToEndTest(BaseServersTest):
    def setUp(self):
        super(EndToEndTest, self).setUp()
        self.filtered_tender_ids_queue = Queue(10)
        self.edrpou_codes_queue = Queue(10)
        self.process_tracker = ProcessTracker()
        self.tender_id = uuid.uuid4().hex
        self.sleep_change_value = APIRateController()
        self.worker = EdrDataBridge(config)

    def tearDown(self):
        super(EndToEndTest, self).tearDown()
        self.redis.flushall()

        # @patch('gevent.sleep')
        # def test_scanner_and_filter(self, gevent_sleep):
        #     gevent_sleep.side_effect = custom_sleep
        #     self.worker = EdrDataBridge(config)
        #     setup_routing(self.api_server_bottle, get_tenders_response, path='/api/2.3/tenders')
        #     setup_routing(self.api_server_bottle, get_tender_response, path='/api/2.3/tenders/123')
        #     self.worker.scanner()
        #     self.worker.filter_tender()
        #     data = Data('123', award_ids[2], CODES[2], "company_name", {"meta": {"sourceRequests": [request_ids[0]]}})
        #     # sleep(5)
        #     sleep_until_done(self.worker, is_working_filter)
        #     self.assertEqual(self.worker.edrpou_codes_queue.get(), data)
        #     self.assertEqual(self.worker.edrpou_codes_queue.qsize(), 0)
        #     self.assertEqual(self.worker.filtered_tender_ids_queue.qsize(), 0)
