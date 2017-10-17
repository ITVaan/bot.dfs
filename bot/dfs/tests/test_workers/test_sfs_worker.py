# coding=utf-8
from bot.dfs.bridge.data import Data
from bot.dfs.bridge.process_tracker import ProcessTracker
from bot.dfs.bridge.requests_db import RequestsDb
from bot.dfs.bridge.requests_to_sfs import RequestsToSfs
from bot.dfs.bridge.sleep_change_value import APIRateController
from bot.dfs.bridge.workers.sfs_worker import SfsWorker
from bot.dfs.tests.base import BaseServersTest
from gevent import event
from gevent.queue import Queue


class TestSfsWorker(BaseServersTest):
    def setUp(self):
        super(TestSfsWorker, self).setUp()
        sfs_client = RequestsToSfs()
        sfs_reqs_queue = Queue(10)
        upload_to_api_queue = Queue(10)
        process_tracker = ProcessTracker()
        redis_db = RequestsDb(self.db)
        services_not_available = event.Event()
        services_not_available.set()
        sleep_change_value = APIRateController()
        self.worker = SfsWorker(sfs_client, sfs_reqs_queue, upload_to_api_queue,
                                process_tracker, redis_db, services_not_available, sleep_change_value)

    def test_init(self):
        sfs_client = RequestsToSfs()
        sfs_reqs_queue = Queue(10)
        upload_to_api_queue = Queue(10)
        process_tracker = ProcessTracker()
        requests_db = RequestsDb(self.db)
        services_not_available = event.Event()
        services_not_available.set()
        sleep_change_value = APIRateController()
        worker = SfsWorker(sfs_client, sfs_reqs_queue, upload_to_api_queue,
                           process_tracker, requests_db, services_not_available, sleep_change_value)
        self.assertEqual(sfs_client, worker.sfs_client)
        self.assertEqual(sfs_reqs_queue, worker.sfs_reqs_queue)
        self.assertEqual(upload_to_api_queue, worker.upload_to_api_queue)
        self.assertEqual(process_tracker, worker.process_tracker)
        self.assertEqual(requests_db, worker.requests_db)
        self.assertEqual(services_not_available, worker.services_not_available)
        self.assertEqual(sleep_change_value, worker.sleep_change_value)

    def test_process_new_request(self):
        data = Data(1, 1, 12345678, "comname", {"meta": {"sourceRequests": []}})
        self.worker.process_new_request(data)

    def test_process_new_request_physical(self):
        data = Data(1, 1, 1234, "last_name first_name family_name", {"meta": {"sourceRequests": []}})
        self.worker.process_new_request(data)

    def test_process_existing_request(self):
        data = Data(1, 1, 12345678, "comname", {"meta": {"sourceRequests": []}})
        req_id = 111
        self.worker.process_existing_request(data, req_id)

    def test_processing_existing_request_with_completed(self):
        data = Data(1, 1, 12345678, "comname", {"meta": {"sourceRequests": []}})
        req_id = 111
        self.worker.requests_db.add_sfs_request(req_id, {"code": data.code, "status": "pending"})
        self.worker.requests_db.complete_request(req_id)
        self.worker.process_existing_request(data, req_id)
