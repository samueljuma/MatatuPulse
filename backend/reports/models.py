from django.conf import settings
from django.db import models


class EventType(models.TextChoices):
    FARE_HIKE = "fare_hike", "Fare hike"
    JAM = "jam", "Jam / Stall"
    ACCIDENT_POLICE = "accident_police", "Accident / Police"
    ROUTE_CLOSED = "route_closed", "Route closed"


class Report(models.Model):
    SOURCE_CHOICES = [("app", "App"), ("sms", "SMS")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    sender_phone = models.CharField(max_length=16, db_index=True)
    source = models.CharField(max_length=3, choices=SOURCE_CHOICES)
    raw_text = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=EventType.choices, blank=True)
    # "accident" or "police" — refines accident_police for labels and expiry.
    subtype = models.CharField(max_length=10, blank=True)
    route = models.ForeignKey("transit.Route", null=True, blank=True, on_delete=models.SET_NULL)
    sacco = models.ForeignKey("transit.RouteSacco", null=True, blank=True, on_delete=models.SET_NULL)
    stage = models.ForeignKey("transit.Stage", null=True, blank=True, on_delete=models.SET_NULL)
    fare = models.PositiveIntegerField(null=True, blank=True)
    is_spam = models.BooleanField(default=False)
    spam_reason = models.CharField(max_length=32, blank=True)
    event = models.ForeignKey("Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.source}:{self.sender_phone}:{self.raw_text[:40]}"


class Event(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("cleared", "Cleared"),
        ("expired", "Expired"),
    ]

    type = models.CharField(max_length=20, choices=EventType.choices)
    subtype = models.CharField(max_length=10, blank=True)
    route = models.ForeignKey("transit.Route", on_delete=models.CASCADE, related_name="events")
    # Extra routes affected (e.g. a Moi Ave closure hits 23 and 46).
    extra_routes = models.ManyToManyField("transit.Route", blank=True, related_name="+")
    sacco = models.ForeignKey("transit.RouteSacco", null=True, blank=True, on_delete=models.SET_NULL)
    stage = models.ForeignKey("transit.Stage", null=True, blank=True, on_delete=models.SET_NULL)
    fare = models.PositiveIntegerField(null=True, blank=True)
    previous_fare = models.PositiveIntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    reporter_count = models.PositiveIntegerField(default=0)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen", "-id"]

    def __str__(self):
        return f"E-{self.id} {self.type} {self.status}"

    @property
    def ref(self):
        return f"E-{self.id}"


class Vote(models.Model):
    KIND_CHOICES = [("still", "Still accurate"), ("cleared", "Cleared")]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    created_at = models.DateTimeField()

    class Meta:
        unique_together = [("event", "user")]


class Alert(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="alerts")
    sent_at = models.DateTimeField()
    channel = models.CharField(max_length=16)  # "sms", "push", "sms+push"
    routes_notified = models.CharField(max_length=64)  # "100" or "23, 46"
    recipients_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-sent_at", "-id"]
