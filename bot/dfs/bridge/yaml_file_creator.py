# coding=utf-8
from uuid import uuid4
from constants import author, version
from xmljson import parker


class YamlFileCreator(object):
    def __init__(self):
        pass

    def form_metadata(self, requests, source_date):
        return {"meta": {"author": author, "version": version, "sourceDate": source_date,
                         "sourceRequests": requests, id: generate_file_id()}}

    def convert_response_to_json(self, response_xml):
        return {"data": parker.data(response_xml),
                "meta": {"version": version, "author": author, "id": generate_file_id()}}

    def convert_json_to_xml(self):
        pass


def generate_file_id():
    return uuid4().hex
