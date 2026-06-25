import unittest
from unittest.mock import patch

from docpipe.utils.infrastructure.caching import LRUCache


class TestLRUCache(unittest.TestCase):
    def setUp(self):
        LRUCache._is_initialized = False
        # if hasattr(LRUCache, "_cache"):
        #    del LRUCache._cache

    def tearDown(self):
        LRUCache._is_initialized = False
        # if hasattr(LRUCache, "_LRUCache__instance"):
        #    del LRUCache._LRUCache__instance

    def test_initialization_valid(self):
        cache = LRUCache(maxsize=10, ttl=2)
        self.assertIsInstance(cache, LRUCache)

    @patch.dict("docpipe.utils.core.patterns.Singleton._instances", clear=True)
    def test_initialization_invalid_ttl(self):
        with self.assertRaises(ValueError):
            LRUCache(maxsize=10, ttl=-5)

    def test_singleton_behavior(self):
        cache1 = LRUCache(maxsize=10, ttl=10)
        cache2 = LRUCache(maxsize=20, ttl=20)
        self.assertIs(cache1, cache2)

    def test_put_and_get(self):
        cache = LRUCache(maxsize=5, ttl=5)
        cache.put(cache_key="key1", value="value1")
        self.assertEqual(cache.get(cache_key="key1"), "value1")

    def test_cache_miss(self):
        cache = LRUCache(maxsize=5, ttl=5)
        self.assertIsNone(cache.get(cache_key="nonexistent"))

    def test_remove_keys(self):
        """Test remove_keys method removes specified keys from cache."""
        cache = LRUCache(maxsize=10, ttl=10)
        # Add multiple items to cache
        cache.put(cache_key="key1", value="value1")
        cache.put(cache_key="key2", value="value2")
        cache.put(cache_key="key3", value="value3")

        # Verify items are in cache
        self.assertEqual(cache.get(cache_key="key1"), "value1")
        self.assertEqual(cache.get(cache_key="key2"), "value2")
        self.assertEqual(cache.get(cache_key="key3"), "value3")

        # Remove keys
        cache.remove_keys(keys=["key1", "key3"])

        # Verify removed keys are gone
        self.assertIsNone(cache.get(cache_key="key1"))
        self.assertIsNone(cache.get(cache_key="key3"))
        # Verify key2 still exists
        self.assertEqual(cache.get(cache_key="key2"), "value2")

    def test_remove_keys_empty_list(self):
        """Test remove_keys with empty list doesn't cause errors."""
        cache = LRUCache(maxsize=10, ttl=10)
        cache.put(cache_key="key1", value="value1")

        # Remove empty list
        cache.remove_keys(keys=[])

        # Verify key1 still exists
        self.assertEqual(cache.get(cache_key="key1"), "value1")

    @patch.dict("docpipe.utils.core.patterns.Singleton._instances", clear=True)
    def test_document_class_lru_cache_default_ttl(self):
        """Test DocumentClassLRUCache has correct default TTL."""
        LRUCache._is_initialized = False
        cache: LRUCache = LRUCache(maxsize=256, ttl=3600)
        self.assertEqual(first=cache._cache.maxsize, second=256)
        # Verify TTL is 1 hour (3600 seconds)
        self.assertEqual(first=cache._cache.ttl, second=3600)


if __name__ == "__main__":
    unittest.main()
