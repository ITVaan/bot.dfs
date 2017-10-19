# -*- coding: utf-8 -*-

from logging import getLogger

LOGGER = getLogger(__name__)


class Db(object):
    """ Database proxy """

    def __init__(self, config):
        self.config = config

        self._backend = None
        self._db_name = None
        self._port = None
        self._host = None
        if 'cache_host' in self.config.get('main'):
            import redis
            self._backend = "redis"
            self._host = self.config_get('cache_host')
            self._port = self.config_get('cache_port') or 6379
            self._db_name = self.config_get('cache_db_name') or 0
            self.db = redis.StrictRedis(host=self._host, port=self._port, db=self._db_name)
            self.set_value = self.db.set
            self.has_value = self.db.exists
            self.remove_value = self.db.delete
            LOGGER.info("Cache initialized")
        else:
            self.set_value = lambda x, y, z: None
            self.has_value = lambda x: None
            self.remove_value = lambda x: None

    def config_get(self, name):
        return self.config.get('main').get(name)

    def get(self, key):
        LOGGER.info("Getting item {} from the cache".format(key))
        return self.db.get(key)

    def put(self, key, value, ex=86400):
        LOGGER.info("Saving key {} to cache".format(key))
        self.set_value(key, value, ex)

    def remove(self, key):
        self.remove_value(key)

    def has(self, key):
        LOGGER.info("Checking if code {} is in the cache".format(key))
        return self.has_value(key)

    def hgetall(self, key):
        return self.db.hgetall(key)

    def smembers(self, key):
        return self.db.smembers(key) if self.db.keys(key) else []

    def sadd(self, key, value):
        return self.db.sadd(key, value)

    def hmset(self, key, value):
        return self.db.hmset(key, value)

    def srem(self, key, value):
        self.db.srem(key, value)

    def hset(self, key, field, value):
        self.db.hset(key, field, value)

    def zadd(self, name, *args, **kwargs):
        return self.db.zadd(name, *args, **kwargs)

    def zinterstore(self, name, sets):
        return self.db.zinterstore(name, sets, aggregate="MAX")

    def zrangebyscore(self, name, min, max):
        return self.db.zrangebyscore(name, min, max)


def db_key(tender_id):
    return "{}".format(tender_id)
