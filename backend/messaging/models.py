from django.db import models


class OutboundSms(models.Model):
    """Every SMS we try to send, with the provider's raw reply for debugging."""

    KIND_CHOICES = [("otp", "OTP"), ("alert", "Alert"), ("test", "Test")]
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("delivered", "Delivered"),
        ("undelivered", "Undelivered"),
    ]

    to = models.CharField(max_length=16, db_index=True)
    text = models.TextField()
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    provider = models.CharField(max_length=16)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="queued", db_index=True)
    provider_message_id = models.CharField(max_length=64, blank=True, db_index=True)
    error = models.TextField(blank=True)
    response = models.JSONField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "outbound SMS"
        verbose_name_plural = "outbound SMS"

    def __str__(self):
        return f"{self.kind} → {self.to} [{self.status}]"
