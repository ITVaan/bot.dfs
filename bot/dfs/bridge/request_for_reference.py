# -*- coding: utf-8 -*-
from gevent import monkey

monkey.patch_all()

import logging.config
from datetime import datetime
from gevent import spawn, sleep
from base_worker import BaseWorker

logger = logging.getLogger(__name__)


class RequestForReference(BaseWorker):
    """ Edr API Data Bridge """
    def __init__(self, reference_queue, request_to_sfs, request_db, services_not_available, sleep_change_value, delay=15):
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
            request_ids = self.request_db.get_pending_requests()
            for request_id, request_data in request_ids.items():
                edr_id = request_data['edr_id']
                dept_id = 1
                depts_proc = 1
                ca_name = ""
                cert = ""
                if self.date_checker:
                    try:
                        sfs_check = self.request_to_sfs.sfs_check_request(edr_id, dept_id, depts_proc)
                    except Exception as e:
                        logger.warning('Fail to check for incoming correspondence. Message {}'.format(e.message))
                        sleep()
                    else:
                        quantity_of_docs = sfs_check['qtDocs']
                        if quantity_of_docs != 0:
                            self.sfs_receiver(request_id, edr_id, dept_id, depts_proc, ca_name, cert)

    def sfs_receiver(self, request_id, edr_id, dept_id, depts_proc, ca_name, cert):
        """Get documents from SFS, put request id with received documents to queue"""
        try:
            sfs_receive = self.request_to_sfs.sfs_receive_request(edr_id, dept_id, depts_proc, ca_name, cert)
        except Exception as e:
            logger.warning('Fail to check for incoming correspondence. Message {}'.format(e.message))
            sleep()
        else:
            sfs_received_docs = sfs_receive['docs']
            try:
                logger.info('Put request_id {} to process...'.format(request_id))
                self.reference_queue.put((request_id, sfs_received_docs))
            except Exception as e:
                logger.exception("Message: {}".format(e.message))
            else:
                logger.info(
                    'Received docs with request_id {} is already in process or was processed.'.format(request_id))

    def date_checker(self):
        """Check if the working time is now or not"""
        return True

    def _start_jobs(self):
        return {'sfs_checker': spawn(self.sfs_checker)}