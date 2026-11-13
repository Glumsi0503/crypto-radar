import datetime as dt
import unittest
from publish_reports import stamp

class PublicationTests(unittest.TestCase):
    def test_parse_iso_utc(self):
        value=stamp('{"generated_at_utc":"2026-11-13T15:00:00+00:00"}')
        self.assertEqual(value,dt.datetime(2026,11,13,15,tzinfo=dt.timezone.utc))
    def test_missing_or_naive_timestamp_is_not_fresh(self):
        self.assertIsNone(stamp('{}'))
        self.assertIsNone(stamp('{"generated_at_utc":"2026-11-13T15:00:00"}'))
    def test_invalid_json_rejected(self):
        self.assertIsNone(stamp('{not_json}'))

if __name__=="__main__":
    unittest.main()
