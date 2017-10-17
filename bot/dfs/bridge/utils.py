# -*- coding: utf-8 -*-
from datetime import datetime, time
from json import loads
from logging import getLogger
from string import digits, uppercase
from uuid import uuid4

import os
import yaml
import io

from constants import (AWARD_STATUS, DOC_TYPE, FORM_NAME, HOLIDAYS_FILE, TZ, qualification_procurementMethodType,
                       tender_status, file_name)
from restkit import ResourceError

LOGGER = getLogger(__name__)


def item_key(tender_id, award_id):
    return '{}_{}'.format(tender_id, award_id)


def journal_context(record={}, params={}):
    for k, v in params.items():
        record["JOURNAL_" + k] = v
    return record


def generate_req_id():
    return b'edr-api-data-bridge-req-' + str(uuid4()).encode('ascii')


def generate_doc_id():
    return uuid4().hex


class RetryException(Exception):
    pass


def check_412(func):
    def func_wrapper(obj, *args, **kwargs):
        try:
            response = func(obj, *args, **kwargs)
        except ResourceError as re:
            if re.status_int == 412:
                obj.headers['Cookie'] = re.response.headers['Set-Cookie']
                response = func(obj, *args, **kwargs)
            else:
                raise ResourceError(re)
        return response

    return func_wrapper


def is_no_document_in_edr(response, res_json):
    return (response.status_code == 404 and isinstance(res_json, dict)
            and res_json.get('errors')[0].get('description')[0].get('error').get('code') == u"notFound")


def should_process_item(item):
    return (item['status'] == AWARD_STATUS and not [document for document in item.get('documents', [])
                                                    if document.get('documentType') == DOC_TYPE])


def is_code_invalid(code):
    return (not (type(code) == int or (type(code) == str and code.isdigit()) or
                 (type(code) == unicode and code.isdigit())))


def more_tenders(params, response):
    return not (params.get('descending')
                and not len(response.data) and params.get('offset') == response.next_page.offset)


def valid_qualification_tender(tender):
    return (tender['status'] == tender_status and
            tender['procurementMethodType'] in qualification_procurementMethodType)


def sfs_file_name(edr_code, request_number):
    date = datetime.now()
    m = to_base36(date.month)
    d = to_base36(date.day)
    return "ieK{}{}{}{}{}{}.xml".format(edr_code, FORM_NAME, m, d, date.year, request_number)


def to_base36(number):
    """Converts an integer to a base36 string."""
    alphabet = digits + uppercase
    base36 = ''
    sign = ''
    if number < 0:
        sign = '-'
        number = -number

    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36

    return sign + base36


def business_date_checker():
    current_date = datetime.now(TZ)
    holidays = read_json(HOLIDAYS_FILE)
    if cond1(current_date, holidays) or cond2(current_date, holidays):
        return False
    else:
        if time(9, 0) <= current_date.time() <= time(18, 0):
            return True
        else:
            return False


def cond1(current_date, holidays):
    return current_date.weekday() in [5, 6] and holidays.get(current_date.date().isoformat(), True)


def cond2(current_date, holidays):
    return holidays.get(current_date.date().isoformat(), False)


#
# def is_weekend(current_date, holidays):
#     return current_date.weekday() in [5, 6] and holidays.get(current_date.date().isoformat(), False)
#
#
# def is_holiday(current_date, holidays):
#     return holidays.get(current_date.date().isoformat(), True)
#
#
# def is_working_day_and_time(current_date):
#     import pdb;
#     pdb.set_trace()
#     return current_date.weekday() in [5, 6] and is_working_day(current_date)
#
#
# def is_working_day(today):
#     import pdb;
#     pdb.set_trace()
#     return (read_json(HOLIDAYS_FILE).get(today.date().isoformat(), True) or
#             read_json(HOLIDAYS_FILE).get(today.date().isoformat(), False))


def read_json(name):
    curr_dir = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(curr_dir, name)
    with open(file_path) as lang_file:
        data = lang_file.read()
    return loads(data)


def create_file(details):
    """ Return temp file with details """
    temporary_file = io.BytesIO()
    temporary_file.name = file_name
    temporary_file.write(yaml.safe_dump(details, allow_unicode=True, default_flow_style=False))
    temporary_file.seek(0)

    return temporary_file
