from collections import defaultdict
from datetime import datetime, timedelta

class Cache_:
    def __init__(self, ttl=300):
        self.store = defaultdict
        self.ttl = ttl
        self.timestamps = {}
    
    def get(self, user_id, key):
        if user_id in self.store and key in self.store[user_id]:
            if datetime.now() < self.timestamps[user_id][key]:
                return self.store[user_id][key]
            else:
                self.remove(user_id, key)
        return None
    
    def set(self, user_id, key, value):
        self.store[user_id][key] = value
        self.timestamps[user_id] = self.timestamps.get(user_id, {})
        self.timestamps[user_id][key] = datetime.now() + timedelta(seconds=self.ttl)

    def remove(self, user_id, key):
        if user_id in self.store and key in self.store[user_id]:
            del self.store[user_id][key] 
            del self.timestamps[user_id][key]
    
    def clear_cache(self, user_id):
        if user_id in self.store:
            del self.store[user_id]
            del self.timestamps[user_id]

cart_cache = Cache_(ttl=600)
products_cache = Cache_(ttl=600)



