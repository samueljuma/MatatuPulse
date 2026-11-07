from django.db import models


class Stage(models.Model):
    name = models.CharField(max_length=64, unique=True)
    # Lowercase spellings used to match free-text SMS ("g45", "githurai").
    aliases = models.JSONField(default=list, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name


class Route(models.Model):
    number = models.CharField(max_length=8, db_index=True)  # not unique: "23" runs on two lines
    name = models.CharField(max_length=128)  # "Odeon → Githurai 45"
    via = models.CharField(max_length=64, blank=True)  # "Thika Road"
    line = models.CharField(max_length=32, blank=True)  # "A Line" (imported routes)
    is_demo = models.BooleanField(default=False)  # the pitch scenario routes
    stages = models.ManyToManyField(Stage, through="RouteStage", related_name="routes")

    class Meta:
        ordering = ["-is_demo", "id"]
        unique_together = [("line", "number", "name")]

    def __str__(self):
        return f"{self.number} {self.name}"

    @property
    def destination(self):
        return self.name.split("→")[-1].strip()


class RouteStage(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]
        unique_together = [("route", "stage")]


class RouteSacco(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="saccos")
    sacco_name = models.CharField(max_length=64)
    sacco_code = models.CharField(max_length=8, blank=True)
    usual_fare = models.PositiveIntegerField()  # the low end of the usual range
    fare_max = models.PositiveIntegerField(null=True, blank=True)  # off-peak..peak range, if known

    class Meta:
        ordering = ["id"]
        unique_together = [("route", "sacco_name")]

    def __str__(self):
        return f"{self.sacco_name} ({self.route.number})"
