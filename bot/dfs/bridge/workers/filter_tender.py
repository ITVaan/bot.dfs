# -*- coding: utf-8 -*-
from gevent import monkey

monkey.patch_all()

import logging.config
import gevent
from datetime import datetime
from gevent import spawn
from gevent.hub import LoopExit
from simplejson import loads

from bot.dfs.bridge.utils import generate_req_id, journal_context, is_code_invalid
from bot.dfs.bridge.data import Data
from bot.dfs.bridge.workers.base_worker import BaseWorker
from bot.dfs.bridge.journal_msg_ids import DATABRIDGE_TENDER_NOT_PROCESS
from bot.dfs.bridge.constants import scheme

logger = logging.getLogger(__name__)


class FilterTenders(BaseWorker):
    """ Edr API Data Bridge """

    def __init__(self, tenders_sync_client, filtered_tender_ids_queue, edrpou_codes_queue, process_tracker,
                 services_not_available, sleep_change_value, delay=15):
        super(FilterTenders, self).__init__(services_not_available)
        self.start_time = datetime.now()

        self.delay = delay
        self.process_tracker = process_tracker
        # init clients
        self.tenders_sync_client = tenders_sync_client

        # init queues for workers
        self.filtered_tender_ids_queue = filtered_tender_ids_queue
        self.edrpou_codes_queue = edrpou_codes_queue
        self.sleep_change_value = sleep_change_value

    def prepare_data(self):
        """Get tender_id from filtered_tender_ids_queue, check award/qualification status, documentType; get
        identifier's id and put into edrpou_codes_queue."""
        while not self.exit:
            self.services_not_available.wait()
            try:
                tender_id = self.filtered_tender_ids_queue.peek()
            except LoopExit:
                gevent.sleep()
                continue
            try:
                response = self.tenders_sync_client.request("GET",
                                                            path='{}/{}'.format(self.tenders_sync_client.prefix_path,
                                                                                tender_id),
                                                            headers={'X-Client-Request-ID': generate_req_id()})
            except Exception as e:
                if getattr(e, "status_int", False) == 429:
                    self.sleep_change_value.increment()
                    logger.info("Waiting tender {} for sleep_change_value: {} seconds".format(
                        tender_id, self.sleep_change_value.time_between_requests))
                else:
                    logger.warning('Fail to get tender info {}. Message {}'.format(tender_id, e.message),
                                   extra=journal_context(params={"TENDER_ID": tender_id}))
                    gevent.sleep()
            else:
                self.sleep_change_value.decrement()
                if response.status_int == 200:
                    self.process_response(response)
                else:
                    logger.warning('Fail to get tender info {}'.format(tender_id),
                                   extra=journal_context(params={"TENDER_ID": tender_id}))
                self.filtered_tender_ids_queue.get()
            gevent.sleep(self.sleep_change_value.time_between_requests)

    def process_response(self, response):
        tender = loads(response.body_string())['data']
        for aw in active_award(tender):
            for code in get_codes(aw):
                data = Data(tender['id'], aw['id'], code[0], code[1])
                self.process_tracker.set_item(data.tender_id, data.item_id)
                self.edrpou_codes_queue.put(data)
            else:
                logger.info('Tender {} bid {} award {} identifier schema isn\'t UA-EDR,.'.format(
                    tender['id'], aw['bid_id'], aw['id']),
                    extra=journal_context({"MESSAGE_ID": DATABRIDGE_TENDER_NOT_PROCESS},
                                          journal_item_params(tender['id'], aw['bid_id'], aw['id'])))
            break
        else:
            logger.info('Tender {} is already in process or was processed.'.format(tender['id']),
                        extra=journal_context({"MESSAGE_ID": DATABRIDGE_TENDER_NOT_PROCESS},
                                              {"TENDER_ID": tender['id']}))

    def _start_jobs(self):
        return {'prepare_data': spawn(self.prepare_data)}


def journal_item_params(tender_id, bid_id, award_id):
    return {"TENDER_ID": tender_id, "BID_ID": bid_id, "AWARD_ID": award_id}


def active_award(tender):
    return [aw for aw in tender.get('awards', []) if aw.get('status') == 'active']


def get_codes(award):
    return [(supplier['identifier']['id'], supplier['identifier']['name'])
            for supplier in award['suppliers'] if is_valid(supplier)]


def is_valid(supplier):
    return (not is_code_invalid(supplier['identifier']['id'])) and supplier['identifier']['scheme'] == scheme
