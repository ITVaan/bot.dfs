# -*- coding: utf-8 -*-
from gevent import monkey

monkey.patch_all()

import logging.config
from datetime import datetime
from gevent import spawn, sleep

from bot.dfs.bridge.workers.base_worker import BaseWorker
from bot.dfs.bridge.utils import business_date_checker

logger = logging.getLogger(__name__)


class RequestForReference(BaseWorker):
    """ Edr API XmlData Bridge """

    def __init__(self, reference_queue, request_to_sfs, request_db, services_not_available, sleep_change_value,
                 delay=15):
        super(RequestForReference, self).__init__(services_not_available)
        self.start_time = datetime.now()
        self.delay = delay
        self.request_to_sfs = request_to_sfs
        self.request_db = request_db

        # init queues for workers
        self.reference_queue = reference_queue

        # blockers
        self.sleep_change_value = sleep_change_value

    def sfs_checker(self):
        """Get request ids from redis, check date, check quantity of documents"""
        while not self.exit:
            self.services_not_available.wait()
            if business_date_checker():
                try:
                    request_ids = self.request_db.get_pending_requests()
                except Exception as e:
                    logger.warning('Fail to get pending requests. Message {}'.format(e.message))
                else:
                    self.check_incoming_correspondence(request_ids)

    def check_incoming_correspondence(self, request_ids):
        for request_id, request_data in request_ids.items():
            code = request_data['code']
            ca_name = ''
            try:
                cert = self.request_to_sfs.sfs_get_certificate_request(ca_name)
            except Exception as e:
                logger.warning('Fail to get certificate. Message {}'.format(e.message))
                sleep()
            else:
                try:
                    quantity_of_docs = self.request_to_sfs.sfs_check_request(code)
                except Exception as e:
                    logger.warning(
                        'Fail to check for incoming correspondence. Message {}'.format(e.message))
                    sleep()
                else:
                    if int(quantity_of_docs) == 0:
                        self.sfs_receiver(request_id, code, ca_name, cert)

    def sfs_receiver(self, request_id, code, ca_name, cert):
        """Get documents from SFS, put request id with received documents to queue"""
        try:
            received_docs = self.request_to_sfs.sfs_receive_request(code, ca_name, cert)
        except Exception as e:
            logger.warning('Fail to check for incoming correspondence. Message {}'.format(e.message))
            sleep()
        else:
            try:
                logger.info('Put request_id {} to process...'.format(request_id))
                self.reference_queue.put((request_id, received_docs))
            except Exception as e:
                logger.exception("Message: {}".format(e.message))
            else:
                logger.info(
                    'Received docs with request_id {} is already in process or was processed.'.format(request_id))

    def _start_jobs(self):
        return {'sfs_checker': spawn(self.sfs_checker)}
