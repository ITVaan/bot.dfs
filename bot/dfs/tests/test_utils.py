# -*- coding: utf-8 -*-
import os
import subprocess
from unittest import TestCase

from time import sleep

from mock import MagicMock, patch
from bot.dfs.bridge.caching import Db, db_key
from bot.dfs.bridge.process_tracker import ProcessTracker
from bot.dfs.bridge.utils import *
from redis import StrictRedis
from restkit import ResourceError
from simplejson import JSONDecodeError

config = {
    "main": {
        "cache_host": "127.0.0.1",
        "cache_port": "16379",
        "cache_db_name": 0
    }
}


class TestUtils(TestCase):
    relative_to = os.path.dirname(__file__)  # crafty line
    redis = None
    redis_process = None
    PORT = 16379
    db = Db(config)

    @classmethod
    def setUpClass(cls):
        cls.redis_process = subprocess.Popen(['redis-server', '--port', str(cls.PORT)])
        sleep(0.1)
        cls.redis = StrictRedis(port=cls.PORT)

    def setUp(self):
        self.process_tracker = ProcessTracker(self.db)
        self.tender_id = "111"
        self.item_id = "222"

    @classmethod
    def tearDownClass(cls):
        cls.redis_process.terminate()
        cls.redis_process.wait()

    def tearDown(self):
        self.redis.flushall()

    def test_db_init(self):
        self.assertEqual(self.db._backend, "redis")
        self.assertEqual(self.db._db_name, 0)
        self.assertEqual(self.db._port, "16379")
        self.assertEqual(self.db._host, "127.0.0.1")

    def test_db_get(self):
        self.assertIsNone(self.db.get("111"))
        self.db.put("111", "test data")
        self.assertEqual(self.db.get("111"), "test data")

    def test_db_set(self):
        self.db.put("111", "test data")
        self.assertEqual(self.db.get("111"), "test data")

    def test_db_has(self):
        self.assertFalse(self.db.has("111"))
        self.db.put("111", "test data")
        self.assertTrue(self.db.has("111"))

    def test_set_item(self):
        self.assertEqual(self.process_tracker.processing_items, {})
        self.assertEqual(self.process_tracker.tender_documents_to_process, {})
        self.process_tracker.set_item(self.tender_id, self.item_id, 1)
        self.assertEqual(self.process_tracker.processing_items, {item_key(self.tender_id, self.item_id): 1})
        self.assertEqual(self.process_tracker.tender_documents_to_process, {db_key(self.tender_id): 1})

    def test_add_docs_amount_to_tender(self):
        self.assertEqual(self.process_tracker.tender_documents_to_process, {})
        self.process_tracker.add_docs_amount_to_tender(self.tender_id, 2)
        self.assertEqual(self.process_tracker.tender_documents_to_process, {db_key(self.tender_id): 2})
        self.process_tracker.add_docs_amount_to_tender(self.tender_id, 3)
        self.assertEqual(self.process_tracker.tender_documents_to_process, {db_key(self.tender_id): 5})

    def test_remove_docs_amount_from_tender(self):
        self.assertEqual(self.process_tracker.tender_documents_to_process, {})
        self.process_tracker.tender_documents_to_process = {db_key(self.tender_id): 2}
        self.assertEqual(self.process_tracker.tender_documents_to_process, {db_key(self.tender_id): 2})
        self.process_tracker.remove_docs_amount_from_tender(self.tender_id)
        self.assertEqual(self.process_tracker.tender_documents_to_process, {db_key(self.tender_id): 1})
        self.process_tracker.remove_docs_amount_from_tender(self.tender_id)
        self.assertEqual(self.process_tracker.tender_documents_to_process, {})

    def test_check_processing_item(self):
        self.assertEqual(self.process_tracker.processing_items, {})
        self.assertFalse(self.process_tracker.check_processing_item(self.tender_id, self.item_id))
        self.process_tracker.set_item(self.tender_id, self.item_id)
        self.assertTrue(self.process_tracker.check_processing_item(self.tender_id, self.item_id))

    def test_check_processed_item(self):
        self.assertEqual(self.process_tracker.processed_items, {})
        self.assertFalse(self.process_tracker.check_processed_item(self.tender_id, self.item_id))
        self.process_tracker.set_item(self.tender_id, self.item_id)
        self.process_tracker.update_items_and_tender(self.tender_id, self.item_id)
        self.assertTrue(self.process_tracker.check_processed_item(self.tender_id, self.item_id))

    def test_check_processed_tender(self):
        self.assertFalse(self.process_tracker.check_processed_tenders(self.tender_id))
        self.redis.set(self.tender_id, "333")
        self.assertTrue(self.process_tracker.check_processed_tenders(self.tender_id))

    def test_update_processing_items(self):
        self.process_tracker.processing_items = {item_key(self.tender_id, self.item_id): 2}
        self.assertEqual(self.process_tracker.processing_items, {item_key(self.tender_id, self.item_id): 2})
        self.process_tracker.update_processing_items(self.tender_id, self.item_id)
        self.assertEqual(self.process_tracker.processing_items, {item_key(self.tender_id, self.item_id): 1})
        self.process_tracker.update_processing_items(self.tender_id, self.item_id)
        self.assertEqual(self.process_tracker.processing_items, {})

    def test_check_412_function(self):
        func = check_412(MagicMock(side_effect=ResourceError(
            http_code=412, response=MagicMock(headers={'Set-Cookie': 1}))))
        with self.assertRaises(ResourceError):
            func(MagicMock(headers={'Cookie': 1}))
        func = check_412(MagicMock(side_effect=ResourceError(
            http_code=403, response=MagicMock(headers={'Set-Cookie': 1}))))
        with self.assertRaises(ResourceError):
            func(MagicMock(headers={'Cookie': 1}))
        f = check_412(MagicMock(side_effect=[1]))
        self.assertEqual(f(1), 1)

    def test_item_key(self):
        tender_id = '123'
        item_id = '456'
        self.assertEqual(item_key(tender_id, item_id), '{}_{}'.format(tender_id, item_id))

    def test_journal_context(self):
        params = {'text': '123'}
        self.assertTrue(journal_context(params=params))

    def test_generate_req_id(self):
        self.assertTrue(isinstance(generate_req_id(), str))

    def test_generate_doc_id(self):
        self.assertTrue(isinstance(generate_doc_id(), str))

    def test_check_add_suffix(self):
        list_ids = ['123', '456', '678']
        document_id = '12345'
        number = 2
        suff = '{document_id}.{amount}.{number}'.format(document_id=document_id, amount=len(list_ids), number=number)
        self.assertEqual(check_add_suffix(list_ids, document_id, number), suff)

    def test_check_add_suffix_no_ids(self):
        list_ids = []
        document_id = '12345'
        number = 2
        self.assertEqual(check_add_suffix(list_ids, document_id, number), document_id)

    def test_is_no_document_in_edr(self):
        response = MagicMock(headers={'Set-Cookie': 1})
        res_json = {'errors': [{'description': [{'error': {'code': 'notFound'}}]}]}
        self.assertFalse(is_no_document_in_edr(response, res_json))

    def test_should_process_item(self):
        item = {'status': 'active', 'documents': [{'documentType': 'sfsConfirmation'}]}
        self.assertFalse(should_process_item(item))

    def test_is_code_invalid(self):
        code = 123
        self.assertFalse(is_code_invalid(code))

    def test_check_related_lot_status_active(self):
        tender = {'lots': [{'status': 'active', 'id': '123'}]}
        award = {'lotID': '123'}
        self.assertTrue(check_related_lot_status(tender, award))

    def test_check_related_lot_status_not_active(self):
        tender = {'lots': [{'status': 'complete', 'id': '123'}]}
        award = {'lotID': '123'}
        self.assertFalse(check_related_lot_status(tender, award))

    def test_journal_item_params(self):
        tender = {'id': "123"}
        item = {'id': "1234", 'bidID': '456'}
        self.assertTrue(journal_item_params(tender, item))

    def test_more_tenders(self):
        params = {'offset': '123', 'descending': 1}
        response = MagicMock(headers={'Set-Cookie': 1})
        self.assertTrue(more_tenders(params, response))

    def test_valid_qualification_tender(self):
        tender = {'status': "active.qualification", 'procurementMethodType': 'aboveThresholdUA'}
        self.assertTrue(valid_qualification_tender(tender))

    @patch('bot.dfs.bridge.utils.datetime')
    def test_business_date_checker_business_date(self, datetime_mock):
        datetime_mock.now = MagicMock(return_value=datetime(2017, 10, 10, 12, 00, 00, 000000))
        self.assertTrue(business_date_checker())

    @patch('bot.dfs.bridge.utils.datetime')
    def test_business_date_checker_weekend(self, datetime_mock):
        datetime_mock.now = MagicMock(return_value=datetime(2017, 10, 16, 12, 00, 00, 000000))
        self.assertFalse(business_date_checker())

    @patch('bot.dfs.bridge.utils.datetime')
    def test_business_date_checker_free_time(self, datetime_mock):
        datetime_mock.now = MagicMock(return_value=datetime(2017, 10, 10, 06, 00, 00, 000000))
        self.assertFalse(business_date_checker())
