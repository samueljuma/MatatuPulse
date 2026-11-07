from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import OtpCode
from accounts.otp import hash_code, request_code, verify_code
from messaging.models import OutboundSms

PHONE = "+254712000111"


def sent_code():
    """The console provider stores the text; pull the 4 digits out of the last OTP SMS."""
    text = OutboundSms.objects.filter(kind="otp").latest("id").text
    return text.split("code is ")[1][:4]


class OtpTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_full_login_with_real_code(self):
        r = self.client.post("/api/auth/otp/request", {"phone": "0712000111"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["demo"])
        self.assertEqual(r.data["resend_in"], 30)
        otp = OtpCode.objects.get(phone=PHONE)
        code = sent_code()
        self.assertNotIn(code, otp.code_hash)  # only the hash is stored
        self.assertEqual(otp.code_hash, hash_code(PHONE, code))
        r = self.client.post("/api/auth/otp/verify", {"phone": PHONE, "code": code}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        # single use
        r = self.client.post("/api/auth/otp/verify", {"phone": PHONE, "code": code}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_resend_cooldown_and_newest_code_wins(self):
        now = timezone.now()
        self.assertTrue(request_code(PHONE, now).ok)
        first = sent_code()
        blocked = request_code(PHONE, now + timedelta(seconds=10))
        self.assertEqual((blocked.ok, blocked.status), (False, 429))
        self.assertGreater(blocked.retry_after, 0)
        self.assertTrue(request_code(PHONE, now + timedelta(seconds=31)).ok)
        second = sent_code()
        if first != second:
            self.assertFalse(verify_code(PHONE, first, now + timedelta(seconds=40)))
        self.assertTrue(verify_code(PHONE, second, now + timedelta(seconds=40)))

    def test_hourly_cap(self):
        now = timezone.now()
        for i in range(5):
            self.assertTrue(request_code(PHONE, now + timedelta(minutes=i)).ok)
        r = request_code(PHONE, now + timedelta(minutes=6))
        self.assertEqual((r.ok, r.status), (False, 429))

    def test_expiry(self):
        now = timezone.now()
        request_code(PHONE, now)
        self.assertFalse(verify_code(PHONE, sent_code(), now + timedelta(minutes=6)))

    def test_attempts_burn_the_code(self):
        now = timezone.now()
        request_code(PHONE, now)
        code = sent_code()
        wrong = "0000" if code != "0000" else "1111"
        for _ in range(5):
            self.assertFalse(verify_code(PHONE, wrong, now))
        self.assertFalse(verify_code(PHONE, code, now))  # burned

    def test_send_failure_returns_503_and_discards_code(self):
        failed = OutboundSms(status="failed")
        with mock.patch("accounts.otp.send_sms", return_value=failed):
            r = self.client.post("/api/auth/otp/request", {"phone": PHONE}, format="json")
        self.assertEqual(r.status_code, 503)
        self.assertFalse(OtpCode.objects.exists())

    @override_settings(OTP_TEST_NUMBERS=[PHONE])
    def test_test_number_uses_fixed_code_without_sms(self):
        r = self.client.post("/api/auth/otp/request", {"phone": PHONE}, format="json")
        self.assertTrue(r.data["demo"])
        self.assertFalse(OutboundSms.objects.exists())
        r = self.client.post("/api/auth/otp/verify", {"phone": PHONE, "code": "4729"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_4729_does_not_work_for_normal_numbers(self):
        self.client.post("/api/auth/otp/request", {"phone": PHONE}, format="json")
        if sent_code() != "4729":
            r = self.client.post("/api/auth/otp/verify", {"phone": PHONE, "code": "4729"}, format="json")
            self.assertEqual(r.status_code, 400)
