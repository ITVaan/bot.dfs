# -*- coding: utf-8 -*-
import logging.config

from zeep import Client

from bot.dfs.bridge.xml_utils import form_xml_to_post

logger = logging.getLogger(__name__)


class RequestsToSfs(object):
    def __init__(self):
        super(RequestsToSfs, self).__init__()
        self.sfs_client = Client('http://obmen.sfs.gov.ua/SwinEd.asmx?WSDL')

    def sfs_check_request(self, code):
        # sfs_check = self.sfs_client.service.Check(recipientEDRPOU=code, recipientDept=1, procAllDepts=1)
        # qtDocs = sfs_check.qtDocs
        return 1

    def sfs_receive_request(self, code, ca_name, cert):
        logger.info(u"Pretended to send sfs_receive_request({}, {}, {})".format(code, ca_name, cert))
        # sfs_receive = self.sfs_client.service.Receive(recipientEDRPOU=code, recipientDept=1, procAllDepts=1,
        #                                               caName=ca_name, cert=cert)
        # docs = sfs_receive.docs
        # return "placeholder"

    def sfs_get_certificate_request(self, ca_name):
        logger.info(u"Pretended to send sfs_get_certificate_request({})".format(ca_name))

        # sfs_get_certificate = self.sfs_client.service.GetCertificate(caName=ca_name)
        # cert = sfs_get_certificate.certs.Certificate[0].cert
        # return "placeholder"

    def post(self, data, ca_name, cert, request_id):
        """Post request to sfs"""
        document = form_xml_to_post(data, request_id)
        logger.info(u"Pretended to send post request with data {}".format(data))
        # return "This is a test return because lol what is specification"
        # return self.sfs_client.service.Post(document=document, recipientDept=1, procAllDepts=1,
        #                                               caName=ca_name, cert=cert)
