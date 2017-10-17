# -*- coding: utf-8 -*-
from uuid import uuid4

from base import BaseServersTest
from bot.dfs.bridge.requests_db import RequestsDb, award_key


class TestRequestsDb(BaseServersTest):
    """docstring for TestRequestsDb"""

    def setUp(self):
        super(TestRequestsDb, self).setUp()
        self.requests_db = RequestsDb(self.db)

    def tearDown(self):
        del self.requests_db

    def test_add_request(self):
        req_data = {"status": "pending", "tender_id": "111", "code": "222"}
        self.requests_db.add_sfs_request("1", req_data)
        self.assertEqual(self.redis.hgetall("requests:1"), req_data)
        self.assertEqual(self.redis.smembers("requests:pending"), set("1", ))

    def test_get_pending_requests(self):
        req_data = {"status": "pending", "tender_id": "111", "code": "222"}
        self.requests_db.add_sfs_request("1", req_data)
        self.assertEqual(self.requests_db.get_pending_requests(), {"1": req_data})

    def test_complete_request(self):
        req_data = {"status": "pending", "tender_id": "111", "code": "222"}
        self.requests_db.add_sfs_request("1", req_data)
        self.requests_db.complete_request("1")
        self.assertEqual(self.redis.hgetall("requests:1")['status'], "complete")
        self.assertEqual(self.redis.smembers("requests:pending"), set())

    def test_add_award(self):
        tender_id = uuid4().hex
        award_id = uuid4().hex
        request_id = uuid4().hex
        self.requests_db.add_award(tender_id, award_id, request_id)
        self.assertEqual(self.redis.get(award_key(tender_id, award_id)), request_id)

    def test_requests_within_range(self):
        reqs_to_add = {uuid4().hex: {"status": "pending", "code": uuid4().hex} for _ in range(4)}
        [self.requests_db.add_sfs_request(key, value) for (key, value) in reqs_to_add.items()]
        for i in range(4):
            self.assertEqual([reqs_to_add.keys()[i]],
                             self.requests_db.recent_requests_with(reqs_to_add.values()[i]['code']))
