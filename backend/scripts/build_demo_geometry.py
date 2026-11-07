"""Build road-following paths for the 5 demo routes (run once; output is committed).

Each route is routed through a few points that sit on its main corridor (Thika Road, Waiyaki Way,
Ngong Road, Jogoo Road) using the public OSRM demo server, the same source the Mat3Route team used
for the real routes. Usage:  python scripts/build_demo_geometry.py
"""

import json
import math
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "transit" / "data" / "demo_route_geometry.json"

# (lat, lon) corridor waypoints, in travel order.
WAYPOINTS = {
    "100": [(-1.2828, 36.8262), (-1.2676, 36.8352), (-1.2324, 36.8780), (-1.2006, 36.9124)],  # Odeon, Pangani, Garden City, Githurai 45
    "23": [(-1.2856, 36.8253), (-1.2738, 36.8146), (-1.2640, 36.8030), (-1.2650, 36.7484)],  # Kencom, Museum Hill, Westlands, Kangemi
    "46": [(-1.2856, 36.8253), (-1.2995, 36.8070), (-1.2989, 36.7627), (-1.2843, 36.7470)],  # Kencom, Ngong Rd, Junction, Kawangware
    "58": [(-1.2854, 36.8282), (-1.2930, 36.8640), (-1.2858, 36.8783)],  # Ambassadeur, Jogoo Rd/Makadara, Buruburu
    "111": [(-1.2854, 36.8282), (-1.2994, 36.7872), (-1.3197, 36.7073), (-1.3527, 36.6699)],  # Ambassadeur, Prestige, Karen, Ngong
}


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def main():
    out = {}
    for number, pts in WAYPOINTS.items():
        coords = ";".join(f"{lon},{lat}" for lat, lon in pts)
        url = f"https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
        req = urllib.request.Request(url, headers={"User-Agent": "MatatuPulse/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            route = json.load(resp)["routes"][0]
        path = [[round(lat, 5), round(lon, 5)] for lon, lat in route["geometry"]["coordinates"]]
        straight = sum(km(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        road = route["distance"] / 1000
        out[number] = {"distance_km": round(road, 1), "duration_min": round(route["duration"] / 60), "path": path}
        legs = [round(leg["distance"] / 1000, 1) for leg in route["legs"]]
        print(f"{number:>4}: {road:5.1f} km by road vs {straight:5.1f} km straight (x{road / straight:.2f}), legs {legs}")
        time.sleep(1.2)  # be polite to the free demo server
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
