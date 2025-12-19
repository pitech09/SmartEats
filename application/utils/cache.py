from collections import defaultdict
from datetime import datetime, timedelta

MAX_USERS = 5000  # 👈 guardrail (top-level, once)


class Cache_:
    def __init__(self, ttl=300):
        self.store = defaultdict(dict)
        self.timestamps = defaultdict(dict)
        self.ttl = ttl

    def get(self, user_id, key):
        expires_at = self.timestamps[user_id].get(key)

        if expires_at and datetime.now() < expires_at:
            return self.store[user_id].get(key)

        self.remove(user_id, key)
        return None

    def set(self, user_id, key, value):
        # 👇 GUARDRAIL LIVES HERE
        if user_id not in self.store and len(self.store) >= MAX_USERS:
            return

        self.store[user_id][key] = value
        self.timestamps[user_id][key] = (
            datetime.now() + timedelta(seconds=self.ttl)
        )

    def remove(self, user_id, key):
        self.store[user_id].pop(key, None)
        self.timestamps[user_id].pop(key, None)

        if not self.store[user_id]:
            self.store.pop(user_id, None)
            self.timestamps.pop(user_id, None)

    def clear_cache(self, user_id):
        self.store.pop(user_id, None)
        self.timestamps.pop(user_id, None)


# Cache instances (bottom of file)
cart_cache = Cache_(ttl=600)
products_cache = Cache_(ttl=600)
