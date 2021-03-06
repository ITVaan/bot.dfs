# -*- coding: utf-8 -*-
from json import dumps
from time import sleep
from uuid import uuid4

from gevent import sleep as gsleep


def custom_sleep(seconds=0):
    return gsleep(seconds=0)


def generate_answers(answers, default):
    """ Yield results, or default """

    def answer_generator():
        for i in answers:
            yield i
        while True:
            yield default

    return answer_generator()


def generate_request_id():
    return 'req-{}'.format(uuid4().hex)


class ResponseMock(object):
    def __init__(self, headers, data, status_int=200):
        self.data = data
        self.headers = headers
        self.status_int = status_int

    def body_string(self):
        return dumps(self.data)

    def next(self):
        pass


class AlmostAlwaysFalse(object):
    def __init__(self, total_iterations=1):
        self.total_iterations = total_iterations
        self.current_iteration = 0

    def __nonzero__(self):
        if self.current_iteration < self.total_iterations:
            self.current_iteration += 1
            return bool(0)
        return bool(1)


class AlmostAlwaysTrue(object):
    def __init__(self, total_iterations=1):
        self.total_iterations = total_iterations
        self.current_iteration = 0

    def __nonzero__(self):
        if self.current_iteration < self.total_iterations:
            self.current_iteration += 1
            return bool(1)
        return bool(0)


def sleep_until_done(worker, func):
    while func(worker):
        sleep(0.1)


def is_working_filter(worker):
    return worker.filtered_tender_ids_queue.qsize() or not worker.edrpou_codes_queue.qsize()


def is_working_all(worker):
    return (worker.filtered_tender_ids_queue.qsize() or worker.edrpou_codes_queue.qsize()
            or worker.upload_to_tender_queue.qsize() or worker.upload_to_doc_service_queue.qsize())
