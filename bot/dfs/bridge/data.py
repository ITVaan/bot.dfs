# -*- coding: utf-8 -*-
from constants import id_passport_len


class Data(object):
    def __init__(self, tender_id, award_id=None, code=None, company_name=None, file_content=None):
        self.tender_id = tender_id
        self.award_id = award_id
        self.code = code
        if len(str(code)) != 8:
            self.is_physical = True
            names = company_name.strip().split(" ")
            self.last_name = names[-2]
            self.first_name = names[-1]
            self.family_name = names[0]
            self.name = " ".join([self.last_name, self.first_name, self.family_name])
        else:
            self.is_physical = False
            self.company_name = company_name
            self.name = self.company_name
        self.file_content = file_content or {}

    def __eq__(self, other):
        return (self.tender_id == other.tender_id and
                self.award_id == other.award_id and
                self.code == other.code and
                self.is_physical == other.is_physical and
                self.file_content == other.file_content)

    def __str__(self):
        return "tender {} {} id: {}".format(self.tender_id, self.company_name[:-1], self.award_id)

    def doc_id(self):
        return self.file_content['meta']['id']

    def param(self):
        return 'id' if self.code.isdigit() and len(self.code) != id_passport_len else 'passport'

    def add_unique_req_id(self, response):
        if response.headers.get('X-Request-ID'):
            self.file_content['meta']['sourceRequests'].append(response.headers['X-Request-ID'])

    def log_params(self):
        return {"TENDER_ID": self.tender_id, "AWARD_ID": self.award_id, "DOCUMENT_ID": self.doc_id()}
