"""Unit tests for backend/security_utils.py. Run: python -m unittest discover -s tests -v"""
import hashlib
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import security_utils as su  # noqa: E402


class PasswordPolicy(unittest.TestCase):
    def test_rejects_short_password(self):
        with self.assertRaises(ValueError):
            su.validate_password("Short1!")

    def test_accepts_twelve_chars(self):
        su.validate_password("CorrectHorse9")

    def test_rejects_password_containing_username(self):
        with self.assertRaises(ValueError):
            su.validate_password("alice-password-1", "alice")

    def test_rejects_repetitive_password(self):
        with self.assertRaises(ValueError):
            su.validate_password("aaaaaaaaaaaaaaaa")

    def test_rejects_overlong_password(self):
        with self.assertRaises(ValueError):
            su.validate_password("a1B2" * 40)


class Usernames(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(su.validate_username("  soc.analyst_01 "), "soc.analyst_01")

    def test_invalid(self):
        for bad in ("ab", "has space", "semi;colon", "x" * 41, "", "<script>"):
            with self.assertRaises(ValueError, msg=bad):
                su.validate_username(bad)


class Hashing(unittest.TestCase):
    def test_roundtrip_and_wrong_password(self):
        h = su.hash_pw("CorrectHorse9")
        self.assertNotIn("CorrectHorse9", h)
        self.assertTrue(su.check_pw("CorrectHorse9", h))
        self.assertFalse(su.check_pw("CorrectHorse8", h))

    def test_hashes_are_salted(self):
        self.assertNotEqual(su.hash_pw("CorrectHorse9"), su.hash_pw("CorrectHorse9"))

    def test_legacy_pbkdf2_hash_from_original_project_still_verifies(self):
        # Exact format produced by the ORIGINAL saas.hash_pw: salt + "$" + pbkdf2_sha256(100k).hex()
        salt = "0123456789abcdef"
        legacy = salt + "$" + hashlib.pbkdf2_hmac("sha256", b"pass123456789", salt.encode(), 100_000).hex()
        ok, _ = su.verify_pw("pass123456789", legacy)
        self.assertTrue(ok)
        self.assertFalse(su.verify_pw("wrong-password-1", legacy)[0])

    def test_legacy_hash_flagged_for_upgrade_only_when_argon2_present(self):
        h = su.hash_pw("x", salt="abcd")
        ok, rehash = su.verify_pw("x", h)
        self.assertTrue(ok)
        self.assertEqual(rehash, su.argon2_available())

    def test_garbage_stored_values_never_verify(self):
        for bad in (None, "", "nodollar", 12345, "$argon2id$broken"):
            self.assertEqual(su.verify_pw("whatever-123456", bad)[0], False)


class CsvInjection(unittest.TestCase):
    def test_formula_prefixes_are_neutralised(self):
        for evil in ("=1+1", "+cmd", "-2+3", "@SUM(A1)", "\tcmd"):
            self.assertTrue(su.csv_safe(evil).startswith("'"), evil)

    def test_normal_values_untouched_and_none_blank(self):
        self.assertEqual(su.csv_safe("Mozilla/5.0"), "Mozilla/5.0")
        self.assertEqual(su.csv_safe(None), "")
        self.assertEqual(su.csv_safe(42), "42")

    def test_datetime_iso(self):
        self.assertTrue(su.csv_safe(datetime(2026, 1, 2, tzinfo=timezone.utc)).startswith("2026-01-02"))


class Dates(unittest.TestCase):
    def test_blank_is_none(self):
        self.assertIsNone(su.parse_day(""))
        self.assertIsNone(su.parse_day(None))

    def test_end_of_day(self):
        d = su.parse_day("2026-11-14", end_of_day=True)
        self.assertEqual((d.hour, d.minute, d.second), (23, 59, 59))
        self.assertIsNotNone(d.tzinfo)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            su.parse_day("14/11/2026")


class Lockout(unittest.TestCase):
    def test_threshold(self):
        self.assertFalse(su.is_locked_out(7, 8))
        self.assertTrue(su.is_locked_out(8, 8))


if __name__ == "__main__":
    unittest.main()
