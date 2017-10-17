# -*- coding: utf-8 -*-
from gevent import monkey

monkey.patch_all()

import uuid
import unittest
import datetime

from gevent.hub import LoopExit
from gevent.queue import Queue
from mock import patch, MagicMock
from time import sleep
from munch import munchify
from restkit.errors import Unauthorized, ResourceError, RequestFailed
from gevent.pywsgi import WSGIServer
from bottle import Bottle, response
from simplejson import dumps
from gevent import event

from bot.dfs.bridge.constants import tender_status, AWARD_STATUS
from bot.dfs.bridge.workers.filter_tender import FilterTenders
from bot.dfs.bridge.utils import item_key
from bot.dfs.bridge.process_tracker import ProcessTracker
from bot.dfs.bridge.data import Data
from bot.dfs.tests.utils import custom_sleep, generate_request_id, ResponseMock
from bot.dfs.bridge.bridge import TendersClientSync
from bot.dfs.bridge.sleep_change_value import APIRateController

SERVER_RESPONSE_FLAG = 0
SPORE_COOKIES = ("a7afc9b1fc79e640f2487ba48243ca071c07a823d27"
                 "8cf9b7adf0fae467a524747e3c6c6973262130fac2b"
                 "96a11693fa8bd38623e4daee121f60b4301aef012c")
COOKIES_412 = ("b7afc9b1fc79e640f2487ba48243ca071c07a823d27"
               "8cf9b7adf0fae467a524747e3c6c6973262130fac2b"
               "96a11693fa8bd38623e4daee121f60b4301aef012c")
CODES = ('14360570', '00138233', '23494714')


def setup_routing(app, func, path='/api/2.3/spore', method='GET'):
    app.route(path, method, func)


def response_spore():
    response.set_cookie("SERVER_ID", SPORE_COOKIES)
    return response


def response_412():
    response.status = 412
    response.set_cookie("SERVER_ID", COOKIES_412)
    return response


def response_get_tender():
    response.status = 200
    response.headers['X-Request-ID'] = '125'
    return dumps({'prev_page': {'offset': '123'},
                  'next_page': {'offset': '1234'},
                  'data': {'status': tender_status,
                           'id': '123',
                           'procurementMethodType': 'aboveThresholdEU',
                           'awards': [{'id': '124',
                                       'bid_id': '111',
                                       'status': AWARD_STATUS,
                                       'suppliers': [{'identifier': {'scheme': 'UA-EDR', 'id': CODES[0],
                                                                     "legalName": "company_name"}}]}]}})


def generate_response():
    global SERVER_RESPONSE_FLAG
    if SERVER_RESPONSE_FLAG == 0:
        SERVER_RESPONSE_FLAG = 1
        return response_412()
    return response_get_tender()


class TestFilterWorker(unittest.TestCase):
    def setUp(self):
        self.filtered_tender_ids_queue = Queue(10)
        self.edrpou_codes_queue = Queue(10)
        self.process_tracker = ProcessTracker()
        self.tender_id = uuid.uuid4().hex
        self.filtered_tender_ids_queue.put(self.tender_id)
        self.sleep_change_value = APIRateController()
        self.client = MagicMock()
        self.sna = event.Event()
        self.sna.set()
        self.worker = FilterTenders.spawn(self.client, self.filtered_tender_ids_queue, self.edrpou_codes_queue,
                                          self.process_tracker, self.sna, self.sleep_change_value)
        self.bid_ids = [uuid.uuid4().hex for _ in range(5)]
        self.qualification_ids = [uuid.uuid4().hex for _ in range(5)]
        self.award_ids = [uuid.uuid4().hex for _ in range(5)]
        self.request_ids = [generate_request_id() for _ in range(2)]
        self.response = ResponseMock({'X-Request-ID': self.request_ids[0]},
                                     munchify({'prev_page': {'offset': '123'},
                                               'next_page': {'offset': '1234'},
                                               'data': {'status': tender_status,
                                                        'id': self.tender_id,
                                                        'procurementMethodType': 'aboveThresholdEU',
                                                        'awards': [self.awards(0, 0, AWARD_STATUS, CODES[0])]}}))

    def tearDown(self):
        self.worker.shutdown()
        del self.worker

    def awards(self, counter_id, counter_bid_id, status, sup_id):
        return {'id': self.award_ids[counter_id], 'bid_id': self.bid_ids[counter_bid_id], 'status': status,
                'suppliers': [{'identifier': {'scheme': 'UA-EDR', 'id': sup_id, "legalName": "company_name"}}]}

    def bids(self, counter_id, edr_id):
        return {'id': self.bid_ids[counter_id],
                'tenderers': [{'identifier': {'scheme': 'UA-EDR', 'id': edr_id, "name": "company_name"}}]}

    def test_init(self):
        worker = FilterTenders.spawn(None, None, None, None, self.sna, self.sleep_change_value)
        self.assertGreater(datetime.datetime.now().isoformat(), worker.start_time.isoformat())
        self.assertEqual(worker.tenders_sync_client, None)
        self.assertEqual(worker.filtered_tender_ids_queue, None)
        self.assertEqual(worker.edrpou_codes_queue, None)
        self.assertEqual(worker.process_tracker, None)
        self.assertEqual(worker.services_not_available, self.sna)
        self.assertEqual(worker.sleep_change_value.time_between_requests, 0)
        self.assertEqual(worker.delay, 15)
        self.assertEqual(worker.exit, False)
        worker.shutdown()
        del worker

    @patch('gevent.sleep')
    def test_worker_award(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        self.client.request.side_effect = [
            ResponseMock({'X-Request-ID': self.request_ids[0]},
                         munchify({'prev_page': {'offset': '123'},
                                   'next_page': {'offset': '1234'},
                                   'data': {'status': "active.pre-qualification",
                                            'id': self.tender_id,
                                            'procurementMethodType': 'aboveThresholdEU',
                                            'awards': [
                                                self.awards(0, 0, AWARD_STATUS, CODES[0]),
                                                self.awards(3, 3, 'unsuccessful', CODES[2]),
                                                {'id': self.bid_ids[4],
                                                 'tenderers': [{'identifier': {
                                                     'scheme': 'UA-ED',
                                                     'id': CODES[2],
                                                     "name": "company_name"}}]}]}}))]
        data = Data(self.tender_id, self.award_ids[0], CODES[0], "company_name", {"meta": {"sourceRequests": [self.request_ids[0]]}})
        self.assertEqual(self.edrpou_codes_queue.get(), data)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(),
                              [item_key(self.tender_id, self.award_ids[0])])

    @patch('gevent.sleep')
    def test_get_tender_exception(self, gevent_sleep):
        """ We must not lose tender after restart filter worker """
        gevent_sleep.side_effect = custom_sleep
        self.client.request.side_effect = [Exception(), self.response]
        data = Data(self.tender_id, self.award_ids[0], CODES[0], "company_name", {"meta": {"sourceRequests": [self.request_ids[0]]}})
        self.assertEqual(self.edrpou_codes_queue.get(), data)
        self.assertEqual(self.worker.sleep_change_value.time_between_requests, 0)
        gevent_sleep.assert_called_with_once(1)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(),
                              [item_key(self.tender_id, self.award_ids[0])])
        self.assertEqual(self.edrpou_codes_queue.qsize(), 0)

    @patch('gevent.sleep')
    def test_get_tender_429(self, gevent_sleep):
        """ We must not lose tender after restart filter worker """
        gevent_sleep.side_effect = custom_sleep
        self.client.request.side_effect = [ResourceError(http_code=429), self.response]
        data = Data(self.tender_id, self.award_ids[0], CODES[0], "company_name", {"meta": {"sourceRequests": [self.request_ids[0]]}})
        self.sleep_change_value.increment_step = 2
        self.sleep_change_value.decrement_step = 1
        self.assertEqual(self.edrpou_codes_queue.get(), data)
        self.assertEqual(self.worker.sleep_change_value.time_between_requests, 1)
        gevent_sleep.assert_called_with_once(1)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(),
                              [item_key(self.tender_id, self.award_ids[0])])
        self.assertEqual(self.edrpou_codes_queue.qsize(), 0)

    @patch('gevent.sleep')
    def test_worker_restart(self, gevent_sleep):
        """ Process tender after catch Unauthorized exception """
        gevent_sleep.side_effect = custom_sleep
        self.client.request.side_effect = [
            Unauthorized(http_code=403),
            Unauthorized(http_code=403),
            Unauthorized(http_code=403),
            ResponseMock({'X-Request-ID': self.request_ids[0]},
                         munchify({'prev_page': {'offset': '123'},
                                   'next_page': {'offset': '1234'},
                                   'data': {'status': tender_status,
                                            'id': self.tender_id,
                                            'procurementMethodType': 'aboveThresholdEU',
                                            'awards': [self.awards(0, 0, AWARD_STATUS, CODES[0]),
                                                       self.awards(1, 1, 'unsuccessful', CODES[2])]}}))]
        data = Data(self.tender_id, self.award_ids[0], CODES[0], "company_name", {"meta": {"sourceRequests": [self.request_ids[0]]}})
        self.assertEqual(self.edrpou_codes_queue.get(), data)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(),
                              [item_key(self.tender_id, self.award_ids[0])])

    @patch('gevent.sleep')
    def test_worker_dead(self, gevent_sleep):
        """ Test that worker will process tender after exception  """
        gevent_sleep.side_effect = custom_sleep
        self.filtered_tender_ids_queue.put(self.tender_id)
        self.client.request.side_effect = [
            ResponseMock({'X-Request-ID': self.request_ids[i]},
                         munchify({'prev_page': {'offset': '123'},
                                   'next_page': {'offset': '1234'},
                                   'data': {
                                       'status': tender_status,
                                       'id': self.tender_id,
                                       'procurementMethodType': 'aboveThresholdEU',
                                       'awards': [self.awards(i, i, AWARD_STATUS, CODES[0])]}})) for i in range(2)]
        for i in range(2):
            data = Data(self.tender_id, self.award_ids[i], CODES[0], "company_name", {"meta": {"sourceRequests": [self.request_ids[i]]}})
            self.assertEqual(self.edrpou_codes_queue.get(), data)
        self.worker.immortal_jobs['prepare_data'].kill(timeout=1)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(),
                              [item_key(self.tender_id, self.award_ids[i]) for i in range(2)])

    @patch('gevent.sleep')
    def test_filtered_tender_ids_queue_loop_exit(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        filtered_tender_ids_queue = MagicMock()
        filtered_tender_ids_queue.peek.side_effect = [LoopExit(), self.tender_id]
        self.client.request.return_value = self.response
        first_data = Data(self.tender_id, self.award_ids[0], CODES[0], "company_name", {"meta": {"sourceRequests": [self.request_ids[0]]}})
        self.worker.filtered_tender_ids_queue = filtered_tender_ids_queue
        self.assertEqual(self.edrpou_codes_queue.get(), first_data)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(),
                              [item_key(self.tender_id, self.award_ids[0])])

    @patch('gevent.sleep')
    def test_worker_award_with_cancelled_lot(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        self.client.request.return_value = ResponseMock(
            {'X-Request-ID': self.request_ids[0]},
            munchify({'prev_page': {'offset': '123'},
                      'next_page': {'offset': '1234'},
                      'data': {'status': tender_status,
                               'id': self.tender_id,
                               'procurementMethodType': 'aboveThresholdEU',
                               'lots': [{'status': 'cancelled', 'id': '123456789'},
                                        {'status': 'active', 'id': '12345678'}],
                               'awards': [{'id': self.award_ids[0],
                                           'bid_id': self.bid_ids[0],
                                           'status': AWARD_STATUS,
                                           'suppliers': [{'identifier': {'scheme': 'UA-EDR', 'id': CODES[0],
                                                                         "legalName": "company_name"}}],
                                           'lotID': '12345678'},
                                          {'id': self.award_ids[1],
                                           'bid_id': self.bid_ids[1],
                                           'status': 'cancelled',
                                           'suppliers': [{'identifier': {'scheme': 'UA-EDR', 'id': CODES[1],
                                                                         "legalName": "company_name"}}],
                                           'lotID': '123456789'}]}}))
        data = Data(self.tender_id, self.award_ids[0], CODES[0], "company_name", {"meta": {"sourceRequests": [self.request_ids[0]]}})
        self.assertEqual(self.edrpou_codes_queue.get(), data)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(),
                              [item_key(self.tender_id, self.award_ids[0])])

    @patch('gevent.sleep')
    def test_award_not_valid_identifier_id(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        self.client.request.return_value = ResponseMock(
            {'X-Request-ID': self.request_ids[0]},
            munchify({'prev_page': {'offset': '123'},
                      'next_page': {'offset': '1234'},
                      'data': {'status': tender_status,
                               'id': self.tender_id,
                               'procurementMethodType': 'aboveThresholdEU',
                               'awards': [self.awards(0, 0, AWARD_STATUS, '')]}}))
        sleep(1)
        self.assertEqual(self.edrpou_codes_queue.qsize(), 0)
        self.assertItemsEqual(self.process_tracker.processing_items, {})

    @patch('gevent.sleep')
    def test_412(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        self.worker.kill()
        filtered_tender_ids_queue = Queue(10)
        filtered_tender_ids_queue.put('123')
        api_server_bottle = Bottle()
        api_server = WSGIServer(('127.0.0.1', 20604), api_server_bottle, log=None)
        setup_routing(api_server_bottle, response_spore)
        setup_routing(api_server_bottle, generate_response, path='/api/2.3/tenders/123')
        api_server.start()
        client = TendersClientSync('', host_url='http://127.0.0.1:20604', api_version='2.3')
        self.assertEqual(client.headers['Cookie'], 'SERVER_ID={}'.format(SPORE_COOKIES))
        worker = FilterTenders.spawn(client, filtered_tender_ids_queue, self.edrpou_codes_queue, self.process_tracker,
                                     MagicMock(), self.sleep_change_value)
        data = Data('123', '124', CODES[0], "company_name", {"meta": {"sourceRequests": ['125']}})
        self.assertEqual(self.edrpou_codes_queue.get(), data)
        self.assertEqual(client.headers['Cookie'], 'SERVER_ID={}'.format(COOKIES_412))
        self.assertEqual(self.edrpou_codes_queue.qsize(), 0)
        self.assertItemsEqual(self.process_tracker.processing_items.keys(), ['123_124'])
        worker.shutdown()
        del worker
        api_server.stop()

    @patch('gevent.sleep')
    def test_request_failed(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        self.client.request.side_effect = [
            RequestFailed(http_code=401, msg=RequestFailed()),
            ResponseMock({'X-Request-ID': self.request_ids[0]},
                         munchify({'prev_page': {'offset': '123'},
                                   'next_page': {'offset': '1234'},
                                   'data': {'status': tender_status,
                                            'id': self.tender_id,
                                            'procurementMethodType': 'aboveThresholdEU',
                                            'awards': [self.awards(0, 0, AWARD_STATUS, '')]}}))]
        sleep(1)
        self.assertEqual(self.client.request.call_count, 2)
        self.assertEqual(self.edrpou_codes_queue.qsize(), 0)
        self.assertItemsEqual(self.process_tracker.processing_items, {})

    def test_process_response_fail(self):
        response = MagicMock(body_string=MagicMock(return_value="""{"data": {"id": 1, "legalName": "cname"}}"""))
        self.worker.process_response(response)

    def test_process_response(self):
        res_json = {"data": {"id": 1, "awards": [{"status": "active", "id": 2, "bid_id": 1, "name": "naaame",
                                                  "suppliers": [{"identifier": {"scheme": "UA-EDR", "legalName": "cname",
                                                                                "id": 12345678}}]}]}}
        response = MagicMock(body_string=MagicMock(return_value=dumps(res_json)))
        self.worker.process_response(response)
