import io
import json
import urllib.error
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from messaging.models import OutboundSms
from messaging.providers import ThriveWaveProvider, extract_message_id
from messaging.service import send_sms


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def provider():
    return ThriveWaveProvider(api_key="k-123", base_url="https://sms.thrivevas.com", path="/v1/message/send",
                              sender_id="MATPULSE", callback_url="https://api.example/api/sms/delivery?token=t")


class ThriveWaveProviderTests(TestCase):
    def test_request_shape(self):
        req = provider().build_request("+254712345678", "hello")
        self.assertEqual(req.full_url, "https://sms.thrivevas.com/v1/message/send")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("X-api-key"), "k-123")
        self.assertIsNone(req.get_header("Authorization"))
        body = json.loads(req.data)
        self.assertEqual(body, {"message": "hello", "msisdn": "254712345678", "sender_id": "MATPULSE",
                                "callback_url": "https://api.example/api/sms/delivery?token=t"})

    def test_success_and_id_extraction(self):
        resp = FakeResp(json.dumps({"status": 200, "message": "queued", "transaction_id": 98765}).encode())
        with mock.patch("urllib.request.urlopen", return_value=resp):
            r = provider().send("+254712345678", "hi")
        self.assertTrue(r.success)
        self.assertEqual(r.provider_message_id, "98765")

    def test_error_status_in_body(self):
        resp = FakeResp(json.dumps({"status": "error", "message": "Insufficient balance"}).encode())
        with mock.patch("urllib.request.urlopen", return_value=resp):
            r = provider().send("+254712345678", "hi")
        self.assertFalse(r.success)
        self.assertIn("Insufficient balance", r.error)

    def test_http_error(self):
        err = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b'{"message": "Invalid API key"}'))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            r = provider().send("+254712345678", "hi")
        self.assertFalse(r.success)
        self.assertIn("401", r.error)
        self.assertIn("Invalid API key", r.error)

    def test_network_error_retries_once(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")) as m:
            r = provider().send("+254712345678", "hi")
        self.assertFalse(r.success)
        self.assertEqual(m.call_count, 2)

    def test_missing_key(self):
        self.assertFalse(ThriveWaveProvider(api_key="").send("+254712345678", "hi").success)

    def test_id_shapes(self):
        self.assertEqual(extract_message_id({"data": {"message_id": "a1"}}), "a1")
        self.assertEqual(extract_message_id({"data": {"sms_ids": [7]}}), "7")
        self.assertEqual(extract_message_id({"messages": [{"id": "x"}]}), "x")
        self.assertEqual(extract_message_id({"data": [{"messageId": "z"}]}), "z")


class SendAndDlrTests(TestCase):
    def test_send_sms_logs_and_dlr_updates(self):
        resp = FakeResp(json.dumps({"status": "success", "data": {"id": "m-1"}}).encode())
        with mock.patch("urllib.request.urlopen", return_value=resp):
            msg = send_sms("0712345678", "alert!", kind="alert", provider=provider())
        self.assertEqual((msg.status, msg.to, msg.provider_message_id), ("sent", "+254712345678", "m-1"))

        client = APIClient()
        self.assertEqual(client.post("/api/sms/delivery", {"id": "m-1", "status": "DELIVRD"}).status_code, 403)
        r = client.post("/api/sms/delivery?token=test-webhook-token", {"id": "m-1", "status": "DELIVRD"}, format="json")
        self.assertTrue(r.data["matched"])
        msg.refresh_from_db()
        self.assertEqual(msg.status, "delivered")

    def test_provider_crash_never_raises(self):
        class Boom:
            name = "boom"

            def send(self, to, text):
                raise RuntimeError("bug")

        msg = send_sms("0712345678", "x", provider=Boom())
        self.assertEqual(msg.status, "failed")
        self.assertEqual(OutboundSms.objects.count(), 1)
