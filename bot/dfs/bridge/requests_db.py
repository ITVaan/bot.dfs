# coding=utf-8
from time import time
from simplejson import loads

from bot.dfs.bridge.data import Data


class RequestsDb(object):
    """This class abstracts away logic of interacting with database (redis)"""

    def __init__(self, db, time_range=1000):
        super(RequestsDb, self).__init__()
        self.time_range = time_range
        self._db = db

    def add_sfs_request(self, request_id, request_data):
        self._db.hmset(req_key(request_id), request_data)
        self._db.sadd("requests:pending", request_id)
        self._db.sadd("requests:edrpou:{}".format(request_data['code']), request_id)
        self._db.zadd("requests:dates", time(), request_id)

    def get_pending_requests(self):
        return {key: self.get_request(key) for key in self._db.smembers("requests:pending")}

    def get_request(self, request_id):
        return self._db.hgetall(req_key(request_id))

    def complete_request(self, request_id):
        self._db.srem("requests:pending", request_id)
        self._db.sadd("requests:complete", request_id)
        self._db.hset(req_key(request_id), "status", "complete")

    def add_award(self, tender_id, award_id, request_id, data):
        self._db.hmset(award_key(tender_id, award_id), {"request_id": request_id, "data": data.db_dump()})
        # self._db.put(award_key(tender_id, award_id), request_id)
        self._db.sadd("tenders_of:{}".format(request_id), award_key(tender_id, award_id))

    def recent_requests_with(self, code):
        # if self._db.has("requests:dates") and self._db.has("request:edrpou"):
        self._db.zinterstore("recent:requests:edrpou:{}".format(code), ("requests:edrpou:{}".format(code),
                                                                        "requests:dates"))
        return self._db.zrangebyscore("recent:requests:edrpou:{}".format(code), time() - self.time_range, time())

    def complete_requests_with(self, code):
        return self._db.sinter("complete:requests:with", ("requests:edrpou:{}".format(code), "requests:complete"))

    def recent_complete_requests_with(self, code):
        self._db.zinterstore("recent:complete:edrpou:{}:".format(code), ("requests:edrpou:{}".format(code),
                                                                         "requests:dates"))
        return self._db.zrangebyscore("recent:complete:edrpou:{}:".format(code), time() - self.time_range, time())

    def get_award(self, key):
        return self._db.hgetall(key)

    def get_tenders_of_request(self, request_id):
        tender_dicts = [self.get_award(key) for key in self._db.smembers("tenders_of:{}".format(request_id))]
        all_the_data = []
        for tender_dict in tender_dicts:
            t_data = loads(tender_dict["data"])
            data = Data(t_data['tender_id'], t_data['award_id'], t_data['code'], t_data['name'], t_data['file_content'])
            all_the_data.append(data)
        return all_the_data

    def add_daily_request(self):
        self._db.incr("requests:number")


def award_key(tender_id, award_id):
    return "tender:{}:{}".format(tender_id, award_id)


def req_key(request_id):
    return "requests:{}".format(request_id)
