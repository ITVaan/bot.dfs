# -*- coding: utf-8 -*-

from gevent import event, monkey

monkey.patch_all()

import datetime
from uuid import uuid4
from gevent.queue import Queue
from mock import patch, MagicMock

from bot.dfs.bridge.data import Data
from bot.dfs.tests.base import BaseServersTest
from bot.dfs.bridge.requests_db import RequestsDb
from bot.dfs.bridge.requests_to_sfs import RequestsToSfs
from bot.dfs.tests.utils import custom_sleep, AlmostAlwaysFalse
from bot.dfs.bridge.sleep_change_value import APIRateController
from bot.dfs.bridge.workers.request_for_reference import RequestForReference


class TestRequestForReferenceWorker(BaseServersTest):
    def setUp(self):
        super(TestRequestForReferenceWorker, self).setUp()
        self.sleep_change_value = APIRateController()
        self.request_db = RequestsDb(self.redis)
        self.request_to_sfs = RequestsToSfs()
        self.request_ids = {'req1': {'code': '14360570'}, 'req2': {'code': '0013823'}}
        for key, value in self.request_ids.items():
            self.request_db.add_sfs_request(key, value)
        self.reference_queue = Queue(10)
        self.sna = event.Event()
        self.sna.set()
        self.worker = RequestForReference.spawn(self.reference_queue, self.request_to_sfs, self.request_db, self.sna,
                                                self.sleep_change_value)

    def tearDown(self):
        self.worker.shutdown()
        del self.worker
        self.redis.flushall()

    def test_init(self):
        self.assertGreater(datetime.datetime.now().isoformat(), self.worker.start_time.isoformat())
        self.assertEqual(self.worker.reference_queue, self.reference_queue)
        self.assertEqual(self.worker.request_to_sfs, self.request_to_sfs)
        self.assertEqual(self.worker.request_db, self.request_db)
        self.assertEqual(self.worker.services_not_available, self.sna)
        self.assertEqual(self.worker.sleep_change_value.time_between_requests, 0)
        self.assertEqual(self.worker.delay, 15)
        self.assertEqual(self.worker.exit, False)

    @patch('gevent.sleep')
    def test_worker(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        self.assertEqual(self.reference_queue.qsize(), 0)

    @patch('gevent.sleep')
    def test_sfs_checker(self, gevent_sleep):
        gevent_sleep.side_effect = custom_sleep
        self.assertEqual(self.reference_queue.get(), ({"meta": {"id": "123"}}, []))

    def test_check_incoming_correspondence(self):
        rfr = RequestForReference(self.reference_queue, self.request_to_sfs, self.request_db, self.sna,
                                  self.sleep_change_value)
        self.assertIsNone(rfr.check_incoming_correspondence(self.request_ids))
        # self.assertIsNone(self.reference_queue.get()[1])
        self.assertEqual(self.reference_queue.get(), ({"meta": {"id": "123"}}, []))

    def test_check_incoming_correspondence_sfs_get_certificate_request_exception(self):
        request_to_sfs = ''
        rfr = RequestForReference(self.reference_queue, request_to_sfs, self.request_db, self.sna,
                                  self.sleep_change_value)
        self.assertIsNone(rfr.check_incoming_correspondence(self.request_ids))
        self.assertEqual(self.reference_queue.get(), ({"meta": {"id": "123"}}, []))

    def test_check_incoming_correspondence_sfs_check_request_exception(self):
        self.redis.flushall()
        self.request_ids = {'req1': {'code': []}}
        for key, value in self.request_ids.items():
            self.request_db.add_sfs_request(key, value)
        rfr = RequestForReference(self.reference_queue, self.request_to_sfs, self.request_db, self.sna,
                                  self.sleep_change_value)
        self.assertIsNone(rfr.check_incoming_correspondence(self.request_ids))
        self.assertEqual(self.reference_queue.get(), ({"meta": {"id": "123"}}, []))

    def test_sfs_receiver_exception(self):
        rfr = RequestForReference(self.reference_queue, self.request_to_sfs, self.request_db, self.sna,
                                  self.sleep_change_value)
        for request_id, request_data in self.request_ids.items():
            code = []
            ca_name = ''
            cert = ''
            self.assertIsNone(rfr.sfs_receiver(request_id, code, ca_name, cert))
        self.assertEqual(self.reference_queue.get(), ({"meta": {"id": "123"}}, []))

    def test_sfs_receiver_reference_queue_put_exception(self):
        reference_queue = ''
        rfr = RequestForReference(reference_queue, self.request_to_sfs, self.request_db, self.sna,
                                  self.sleep_change_value)
        for request_id, request_data in self.request_ids.items():
            code = request_data['code']
            ca_name = ''
            cert = ''
            self.assertIsNone(rfr.sfs_receiver(request_id, code, ca_name, cert))

    def test_sfs_receiver(self):
        reference_queue = Queue(10)
        rfr = RequestForReference(reference_queue, self.request_to_sfs, self.request_db, self.sna,
                                  self.sleep_change_value)
        tender_id = uuid4().hex
        award_id = uuid4().hex
        request_id = uuid4().hex
        data = Data(tender_id, award_id, "12345678", "comname", {"meta": {"id": 122}})
        self.request_db.add_award(tender_id, award_id, request_id, data)
        rfr.sfs_receiver(request_id, "12345678", "", "")

    def test_db_connection_problem(self):
        reference_queue = Queue(10)
        mock_request_db = MagicMock(get_pending_requests=MagicMock(side_effect=Exception))
        rfr = RequestForReference(reference_queue, self.request_to_sfs, mock_request_db, self.sna,
                                  self.sleep_change_value, 1)
        with patch.object(rfr, 'exit', AlmostAlwaysFalse()):
            rfr.sfs_checker()

    def test_sfs_check_exception(self):
        reference_queue = Queue(10)
        self.request_ids = {'req1': {'code': []}}
        mock_request_sfs = MagicMock(sfs_check_request=MagicMock(side_effect=Exception))
        rfr = RequestForReference(reference_queue, mock_request_sfs, self.request_db, self.sna,
                                  self.sleep_change_value, 1)
        rfr.check_incoming_correspondence(self.request_ids)

    def test_sfs_receive_request_exception(self):
        reference_queue = Queue(10)
        self.request_ids = {'req1': {'code': []}}
        mock_request_sfs = MagicMock(sfs_receive_request=MagicMock(side_effect=Exception))
        rfr = RequestForReference(reference_queue, mock_request_sfs, self.request_db, self.sna,
                                  self.sleep_change_value, 1)
        code = []
        ca_name = ''
        cert = ''
        rfr.sfs_receiver(self.request_ids, code, ca_name, cert)
