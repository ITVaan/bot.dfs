# -*- coding: utf-8 -*-
from bot.dfs.bridge.workers.sfs_worker import SfsWorker
from gevent import monkey

monkey.patch_all()

import logging
import logging.config
import os
import argparse
import gevent

from functools import partial
from yaml import load
from gevent import event
from gevent.queue import Queue
from retrying import retry
from restkit import RequestError, ResourceError
from constants import retry_mult

from openprocurement_client.client import TendersClientSync as BaseTendersClientSync, TendersClient as BaseTendersClient
from process_tracker import ProcessTracker
from bot.dfs.bridge.workers.scanner import Scanner
from requests_db import RequestsDb
from requests_to_sfs import RequestsToSfs
from caching import Db
from bot.dfs.bridge.workers.filter_tender import FilterTenders
from utils import journal_context, check_412
from journal_msg_ids import (DATABRIDGE_RESTART_WORKER, DATABRIDGE_START, DATABRIDGE_DOC_SERVICE_CONN_ERROR)

from sleep_change_value import APIRateController

logger = logging.getLogger(__name__)


class TendersClientSync(BaseTendersClientSync):
    @check_412
    def request(self, *args, **kwargs):
        return super(TendersClientSync, self).request(*args, **kwargs)


class TendersClient(BaseTendersClient):
    @check_412
    def _create_tender_resource_item(self, *args, **kwargs):
        return super(TendersClient, self)._create_tender_resource_item(*args, **kwargs)


class EdrDataBridge(object):
    """ Edr API Data Bridge """

    def __init__(self, config):
        logger.info("initialization start")
        super(EdrDataBridge, self).__init__()
        self.config = config

        api_server = self.config_get('tenders_api_server')
        self.api_version = self.config_get('tenders_api_version')
        ro_api_server = self.config_get('public_tenders_api_server') or api_server
        buffers_size = self.config_get('buffers_size') or 500
        self.delay = self.config_get('delay') or 15
        self.increment_step = self.config_get('increment_step') or 1
        self.decrement_step = self.config_get('decrement_step') or 1
        self.sleep_change_value = APIRateController(self.increment_step, self.decrement_step)
        self.sandbox_mode = os.environ.get('SANDBOX_MODE', 'False')
        self.time_to_live = self.config_get('time_to_live') or 300
        self.time_range = self.config_get('time_range') or 0

        # init clients
        self.tenders_sync_client = TendersClientSync('', host_url=ro_api_server, api_version=self.api_version)
        self.client = TendersClient(self.config_get('api_token'), host_url=api_server, api_version=self.api_version)

        # init queues for workers
        self.filtered_tender_ids_queue = Queue(maxsize=buffers_size)  # queue of tender IDs with appropriate status
        self.edrpou_codes_queue = Queue(maxsize=buffers_size)  # queue with edrpou codes (XmlData objects stored in it)
        self.reference_queue = Queue(maxsize=buffers_size)  # queue of request IDs and documents
        self.upload_to_api_queue = Queue(maxsize=buffers_size)  # queue with data to upload back into central DB

        # blockers
        self.initialization_event = event.Event()
        self.services_not_available = event.Event()
        self.services_not_available.set()
        self.db = Db(config)
        self.process_tracker = ProcessTracker(self.db, self.time_to_live)
        self.request_db = RequestsDb(self.db, self.time_range)
        self.request_to_sfs = RequestsToSfs()

        # Workers
        self.scanner = partial(Scanner.spawn,
                               tenders_sync_client=self.tenders_sync_client,
                               filtered_tender_ids_queue=self.filtered_tender_ids_queue,
                               services_not_available=self.services_not_available,
                               process_tracker=self.process_tracker,
                               sleep_change_value=self.sleep_change_value,
                               delay=self.delay)

        self.filter_tender = partial(FilterTenders.spawn,
                                     tenders_sync_client=self.tenders_sync_client,
                                     filtered_tender_ids_queue=self.filtered_tender_ids_queue,
                                     edrpou_codes_queue=self.edrpou_codes_queue,
                                     process_tracker=self.process_tracker,
                                     services_not_available=self.services_not_available,
                                     sleep_change_value=self.sleep_change_value,
                                     delay=self.delay)

        self.sfs_reqs_worker = partial(SfsWorker.spawn, sfs_client=self.request_to_sfs,
                                       sfs_reqs_queue=self.edrpou_codes_queue,
                                       upload_to_api_queue=self.upload_to_api_queue,
                                       process_tracker=self.process_tracker,
                                       redis_db=self.request_db,
                                       services_not_available=self.services_not_available,
                                       sleep_change_value=self.sleep_change_value,
                                       delay=15)

        # self.request_for_reference = partial(RequestForReference.spawn,
        #                                      reference_queue=self.reference_queue,
        #                                      request_to_sfs=self.request_to_sfs,
        #                                      request_db=self.request_db,
        #                                      services_not_available=self.services_not_available,
        #                                      sleep_change_value=self.sleep_change_value,
        #                                      delay=self.delay)

    def config_get(self, name):
        return self.config.get('main').get(name)

    @retry(stop_max_attempt_number=5, wait_exponential_multiplier=retry_mult)
    def check_openprocurement_api(self):
        """Makes request to the TendersClient, returns True if it's up, raises RequestError otherwise"""
        try:
            self.client.head('/api/{}/spore'.format(self.api_version))
        except (RequestError, ResourceError) as e:
            logger.info('TendersServer connection error, message {}'.format(e),
                        extra=journal_context({"MESSAGE_ID": DATABRIDGE_DOC_SERVICE_CONN_ERROR}, {}))
            raise e
        else:
            return True

    def set_sleep(self):
        self.services_not_available.clear()

    def set_wake_up(self):
        self.services_not_available.set()

    def all_available(self):
        try:
            self.check_openprocurement_api()
        except Exception as e:
            logger.info("Service is unavailable, message {}".format(e))
            return False
        else:
            return True

    def check_services(self):
        if self.all_available():
            logger.info("All services are available")
            self.set_wake_up()
        else:
            logger.info("Pausing bot")
            self.set_sleep()

    def _start_jobs(self):
        self.jobs = {'scanner': self.scanner(),
                     'filter_tender': self.filter_tender(),
                     'sfs_reqs_worker': self.sfs_reqs_worker(),
                     # 'request_for_reference': self.request_for_reference()
                     }

    def launch(self):
        while True:
            if self.all_available():
                self.run()
                break
            gevent.sleep(self.delay)

    def run(self):
        logger.info('Start EDR API Data Bridge', extra=journal_context({"MESSAGE_ID": DATABRIDGE_START}, {}))
        self._start_jobs()
        counter = 0
        try:
            while True:
                gevent.sleep(self.delay)
                self.check_services()
                if counter == 20:
                    counter = 0
                    logger.info(
                        'Current state: Filtered tenders {}; Edrpou codes queue {}; References queue {}'.format(
                            self.filtered_tender_ids_queue.qsize(),
                            self.edrpou_codes_queue.qsize(),
                            self.reference_queue.qsize()))
                counter += 1
                self.check_and_revive_jobs()
        except KeyboardInterrupt:
            logger.info('Exiting...')
            gevent.killall(self.jobs, timeout=5)
        except Exception as e:
            logger.error(e)

    def check_and_revive_jobs(self):
        for name, job in self.jobs.items():
            logger.debug("{}.dead: {}".format(name, job.dead))
            if job.dead:
                self.revive_job(name)

    def revive_job(self, name):
        logger.warning('Restarting {} worker'.format(name),
                       extra=journal_context({"MESSAGE_ID": DATABRIDGE_RESTART_WORKER}))
        self.jobs[name] = gevent.spawn(getattr(self, name))


def main():
    parser = argparse.ArgumentParser(description='Edr API XmlData Bridge')
    parser.add_argument('config', type=str, help='Path to configuration file')
    parser.add_argument('--tender', type=str, help='Tender id to sync', dest="tender_id")
    params = parser.parse_args()
    if os.path.isfile(params.config):
        with open(params.config) as config_file_obj:
            config = load(config_file_obj.read())
        logging.config.dictConfig(config)
        bridge = EdrDataBridge(config)
        bridge.launch()
    else:
        logger.info('Invalid configuration file. Exiting...')


if __name__ == "__main__":
    main()
