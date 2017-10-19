# -*- coding: utf-8 -*-
import logging.config

from bot.dfs.bridge.xml_utils import form_xml_to_post
from zeep import Client

logger = logging.getLogger(__name__)


class RequestsToSfs(object):
    def __init__(self):
        super(RequestsToSfs, self).__init__()
        self.sfs_client = Client('resources/soap.wsdl')

    def sfs_check_request(self, code):
        """Check request to sfs"""
        sfs_check = self.sfs_client.service.Check(recipientEDRPOU=code)
        qtDocs = sfs_check.qtDocs
        return qtDocs

    def sfs_receive_request(self, code, ca_name, cert):
        """Receive request to sfs"""
        sfs_receive = self.sfs_client.service.Receive(recipientEDRPOU=code, caName=ca_name, cert=cert)
        docs = sfs_receive.docs
        return docs

    def sfs_get_certificate_request(self, ca_name):
        """GetCertificate request to sfs"""
        sfs_get_certificate = self.sfs_client.service.GetCertificate(caName=ca_name)
        cert = sfs_get_certificate.certs.Certificate[0].cert
        return cert

    def sfs_post_request(self, data, request_id):
        """Post request to sfs"""
        document = form_xml_to_post(data, request_id)
        logger.info(u"Pretended to send post request with data {}".format(data))
        # return "This is a test return because lol what is specification"
        # return self.sfs_client.service.Post(senderEDRPOU=document, docsType=docsType, docs=document)
