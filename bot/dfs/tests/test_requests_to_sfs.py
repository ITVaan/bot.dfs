# -*- coding: utf-8 -*-
from unittest import TestCase

from bot.dfs.bridge.requests_to_sfs import RequestsToSfs
from zeep import Client


class TestRequestsToSfs(TestCase):
    """docstring for TestRequestsToSfs"""

    def setUp(self):
        self.sfs_client = Client('http://obmen.sfs.gov.ua/SwinEd.asmx?WSDL')
        self.edr_code = '14360570'
        self.ca_name = ''
        self.cert = ''
        self.r = RequestsToSfs()

    def test_sfs_check_request(self):
        qtDocs = self.r.sfs_check_request(self.edr_code)
        sfs_check = self.sfs_client.service.Check(recipientEDRPOU=self.edr_code, recipientDept=1, procAllDepts=1)
        self.assertEqual(qtDocs, sfs_check.qtDocs)

    def test_sfs_receive_request(self):
        docs = self.r.sfs_receive_request(self.edr_code, self.ca_name, self.cert)
        sfs_receive = self.sfs_client.service.Receive(recipientEDRPOU=self.edr_code, recipientDept=1, procAllDepts=1,
                                                      caName=self.ca_name, cert=self.cert)
        self.assertEqual(docs, sfs_receive.docs)

    def test_sfs_get_certificate_request(self):
        cert = self.r.sfs_get_certificate_request(self.ca_name)
        sfs_get_certificate = self.sfs_client.service.GetCertificate(caName=self.ca_name)
        self.assertEqual(cert, sfs_get_certificate.certs.Certificate[0].cert)
