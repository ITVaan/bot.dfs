# -*- coding: utf-8 -*-
from unittest import TestCase

import requests_mock
from bot.dfs.client import ProxyClient
from requests import RequestException


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

    @requests_mock.Mocker()
    def test_verify(self, mrequest):
        proxy_client = ProxyClient(self.host, self.user, self.password, timeout=None, port=self.port,
                                   version=self.version)
        mrequest.get(proxy_client.verify_url, [{'json': {}, 'status_code': 200}])
        proxy_client.verify("awards", "111", {"a": '1'})

    @requests_mock.Mocker()
    def test_health_healthy(self, mrequest):
        proxy_client = ProxyClient(self.host, self.user, self.password, timeout=None, port=self.port,
                                   version=self.version)
        mrequest.get(proxy_client.health_url, [{'json': {}, 'status_code': 200}])
        proxy_client.health("False")

    @requests_mock.Mocker()
    def test_health_unhealthy(self, mrequest):
        proxy_client = ProxyClient(self.host, self.user, self.password, timeout=None, port=self.port,
                                   version=self.version)
        mrequest.get(proxy_client.health_url, [{'json': {}, 'status_code': 403}])
        with self.assertRaises(RequestException):
            proxy_client.health("False")
