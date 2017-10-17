# coding=utf-8
from gevent import monkey, sleep

monkey.patch_all()
from datetime import datetime

from bot.dfs.bridge.workers.base_worker import BaseWorker
from bot.dfs.tests.utils import generate_request_id


class SfsWorker(BaseWorker):
    def __init__(self, sfs_client, sfs_reqs_queue, upload_to_api_queue, process_tracker, redis_db,
                 services_not_available, sleep_change_value, delay=15):
        super(SfsWorker, self).__init__(services_not_available)
        self.start_time = datetime.now()

        self.delay = delay
        self.process_tracker = process_tracker

        # init queues for workers
        self.sfs_reqs_queue = sfs_reqs_queue
        self.upload_to_api_queue = upload_to_api_queue
        self.requests_db = redis_db
        self.sfs_client = sfs_client
        self.sleep_change_value = sleep_change_value

    def send_sfs_request(self):
        while not self.exit:
            data = self.sfs_reqs_queue.get()
            recent_reqs = self.requests_db.recent_requests_with(data.edr_code)
            if not recent_reqs:
                self.process_new_request(data)
            else:
                self.process_existing_request(data, recent_reqs[0])
            sleep(self.delay)

    def process_new_request(self, data):
        """Make a new request, bind award in question to it"""
        request_id = generate_request_id()
        data.file_content['meta']['sourceRequests'].append(request_id)
        response = self.sfs_client.post(data, "", "", request_id)
        self.requests_db.add_sfs_request(request_id, {"code": data.code, "tender_id": data.tender_id,
                                                      "name": data.name})

    def process_existing_request(self, data, existing_request_id):
        """bind award to existing request, load the answer which is already there into Central Database"""
        completed_reqs = self.requests_db.recent_complete_requests_with(data.code)
        if completed_reqs:  # this way we upload the completed request, not pending one
            self.requests_db.add_award(data.tender_id, data.award_id, completed_reqs[0])
            self.upload_to_api_queue.put((data, self.requests_db.get_request(completed_reqs[0])))
        else:  # this way we upload receipt from existing request into the award
            self.requests_db.add_award(data.tender_id, data.award_id, existing_request_id)
            self.upload_to_api_queue.put((data, self.requests_db.get_request(existing_request_id)))

    def _start_jobs(self):
        return {"send_sfs_request": self.send_sfs_request()}
