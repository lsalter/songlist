import urlparse
import redis
from music import app
import datetime
from datetime import timedelta


class Database(object):
    """
    Wrapper to access the local data store.
    """
    CACHE_HOURS = 1
    EXPIRY_SUFFIX = '_expiry'
    
    def __init__(self):
        url = urlparse.urlparse(app.config.get('REDIS'))
        self.r = redis.Redis(host=url.hostname, port=url.port, password=url.password)
        
    def get(self, key):
        return self.r.get(key)

    def get_cache(self, key):
        # Use the expiry key to see if the cached data is still valid
        expiry_key = key + self.EXPIRY_SUFFIX
        if self.r.get(expiry_key) and self.r.get(expiry_key) > datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'):
            # Cache still valid so return cached data
            return self.r.get(key)
        else:
            # Cache has expired or is invalid so return nothing
            return None

    def set(self, key, value):
        return self.r.set(key, value)

    def set_cache(self, key, value):
        # Set the cache expiry key
        expiry_key = key + self.EXPIRY_SUFFIX
        expiry_time = (datetime.datetime.now() + timedelta(hours=self.CACHE_HOURS))
        self.r.set(expiry_key, expiry_time.strftime('%Y-%m-%dT%H:%M:%S'))
        
        # Set the key value
        self.r.set(key, value)

    def delete(self, key):
        return self.r.delete(key)