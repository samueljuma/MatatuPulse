"""Import the real Nairobi route catalogue (from Mat3Route's scraped_routes.csv + geocoded stages)."""

import csv
import json
from pathlib import Path

from django.db import transaction

from .models import Route, RouteSacco, RouteStage, Stage

DATA = Path(__file__).resolve().parent / "data"


@transaction.atomic
def import_routes(csv_path=DATA / "scraped_routes.csv", locations_path=DATA / "nairobi_locations.json"):
    locations = json.loads(Path(locations_path).read_text())
    with open(csv_path, newline="") as fh:
        rows = list(csv.DictReader(fh))

    stages = {}

    def stage(name):
        if name not in stages:
            loc = locations.get(name) or {}
            st, created = Stage.objects.get_or_create(name=name, defaults={"lat": loc.get("lat"), "lon": loc.get("lon")})
            if not created and st.lat is None and loc:
                st.lat, st.lon = loc.get("lat"), loc.get("lon")
                st.save(update_fields=["lat", "lon"])
            stages[name] = st
        return stages[name]

    routes = saccos = 0
    for row in rows:
        start, end = row["start"].strip(), row["end"].strip()
        route, created = Route.objects.update_or_create(
            line=row["line"].strip(),
            number=row["route_number"].strip(),
            name=f"{start} → {end}",
            defaults={"is_demo": False},
        )
        routes += created
        for order, name in enumerate((start, end)):
            RouteStage.objects.update_or_create(route=route, stage=stage(name), defaults={"order": order})
        fare_min, fare_max = int(row["fare_min"]), int(row["fare_max"])
        _, created = RouteSacco.objects.update_or_create(
            route=route,
            sacco_name=row["sacco"].strip(),
            defaults={"sacco_code": row["sacco_code"].strip(), "usual_fare": fare_min, "fare_max": fare_max},
        )
        saccos += created
    return {"rows": len(rows), "routes_created": routes, "saccos_created": saccos, "stages": len(stages)}
