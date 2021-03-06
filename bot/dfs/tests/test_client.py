# -*- coding: utf-8 -*-
from unittest import TestCase

from bot.dfs.client import ProxyClient


class TestClient(TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.user = 'bot'
        self.password = 'bot'
        self.port = 6547
        self.version = '2.3'

    def test_proxy_client_init(self):
        proxy_client = ProxyClient(self.host, self.user, self.password, timeout=None, port=self.port,
                                   version=self.version)
        self.assertEqual(proxy_client.user, self.user)
        self.assertEqual(proxy_client.password, self.password)
        self.assertEqual(proxy_client.verify_url, "{}:{}/api/{}/verify".format(self.host, self.port, self.version))
        self.assertEqual(proxy_client.health_url, "{}:{}/api/{}/health".format(self.host, self.port, self.version))

    def test_verify(self):
        pass
