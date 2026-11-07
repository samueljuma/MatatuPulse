"""Deterministic demo data: routes, stages, saccos and the 200 seed SMS.

The SMS are generated relative to "now" so the replay always looks live:
200 raw -> 61 spam -> 139 valid merging into 27 events -> 12 verified (15 pending).
"""

import random
from datetime import timedelta

ROUTES = [
    # number, name, via, [stages in order]
    ("23", "Kencom → Kangemi", "Waiyaki Way", ["Kencom", "Moi Ave", "Museum Hill", "Westlands", "Kangemi"]),
    ("46", "Kencom → Kawangware", "Ngong Road", ["Kencom", "Moi Ave", "Junction", "Kawangware"]),
    ("58", "Ambassadeur → Buruburu", "Jogoo Road", ["Ambassadeur", "Muthurwa", "Makadara", "Donholm", "Buruburu"]),
    ("111", "Ambassadeur → Ngong", "Ngong Road", ["Ambassadeur", "Prestige", "Karen", "Ngong"]),
    ("100", "Odeon → Githurai 45", "Thika Road", ["Odeon", "Ngara", "Pangani", "Muthaiga", "Roysambu", "Kasarani", "Githurai 45"]),
]

STAGE_ALIASES = {
    "Kencom": ["kencom"],
    "Moi Ave": ["moi ave", "moi avenue", "moi av"],
    "Museum Hill": ["museum hill", "museum"],
    "Westlands": ["westlands", "westie", "westi"],
    "Kangemi": ["kangemi"],
    "Junction": ["junction", "the junction"],
    "Kawangware": ["kawangware", "kawangs", "kawa"],
    "Ambassadeur": ["ambassadeur", "ambasa", "ambassador"],
    "Muthurwa": ["muthurwa"],
    "Makadara": ["makadara"],
    "Donholm": ["donholm", "donnie"],
    "Buruburu": ["buruburu", "buru", "buru buru"],
    "Prestige": ["prestige"],
    "Karen": ["karen"],
    "Ngong": ["ngong town", "ngong"],
    "Odeon": ["odeon"],
    "Ngara": ["ngara"],
    "Pangani": ["pangani"],
    "Muthaiga": ["muthaiga"],
    "Roysambu": ["roysambu", "roy"],
    "Kasarani": ["kasarani", "kasa"],
    "Githurai 45": ["githurai 45", "g45", "githurai", "g 45"],
}

SACCOS = {
    "100": [("Thika Road Flyers", 70), ("Mwangaza Sacco", 80), ("Haraka Shuttle", 70), ("Zuri Line", 70)],
    "23": [("Westlink Sacco", 60), ("Kangemi Express", 70)],
    "46": [("Kawangware Shuttle", 60), ("Metro Line", 50)],
    "58": [("Buruburu Express", 70), ("Jogoo Line", 60)],
    "111": [("Ngong Line", 100), ("Karen Shuttle", 90)],
}

# Each event: (key, minutes_before_now_of_first_report, spacing_minutes, texts...).
# The number of texts is the number of distinct reporters.
VERIFIED_EVENTS = [
    ("moi_closed", 92, 1.2, [
        "moi ave imefungwa kabisa, maandamano",
        "moi avenue closed, magari zinazungushwa",
        "barabara imefungwa moi ave",
        "imefungwa moi ave, tumia haile selassie",
        "moi ave closed na askari",
        "moi av imefungwa, tushuke kencom",
        "closed moi avenue bado",
    ]),
    ("kasarani_police", 66, 2.0, [
        "karao kasarani wanacheck leseni",
        "polisi wako kasarani stage",
        "police crackdown kasarani",
    ]),
    ("westlands_jam", 118, 1.2, [
        "imejam westlands vibaya", "jam westlands hatusongi", "westlands traffic ni mob",
        "tumekwama westlands", "jam mbaya westie", "westlands imejam saa hii",
        "kwama westlands roundabout", "jam westlands mpaka sarit", "imejam westi",
        "traffic westlands bado", "westlands jam ya kufa", "hatusongi westlands",
        "jam westlands tangu saa tano", "tumekwama westie bana", "westlands imejam kabisa",
    ]),
    ("junction_jam", 115, 1.2, [
        "jam junction ngong rd", "imejam junction", "tumekwama junction",
        "junction traffic mob", "jam the junction", "junction hatusongi",
        "imejam junction mbaya", "kwama junction", "jam junction bado",
        "junction imejam sana", "traffic junction", "tumekwama the junction",
        "jam junction saa hii", "junction jam ya kufa",
    ]),
    ("donholm_jam", 112, 1.2, [
        "jam donholm", "imejam donholm", "tumekwama donholm", "donholm traffic mob",
        "jam donholm round about", "donholm hatusongi", "imejam donnie", "kwama donholm",
        "jam donholm bado", "donholm imejam sana", "traffic donholm", "jam donholm saa hii",
        "donholm jam ya kufa",
    ]),
    ("karen_jam", 110, 1.2, [
        "jam karen", "imejam karen", "tumekwama karen", "karen traffic mob",
        "jam karen roundabout", "karen hatusongi", "imejam karen sana", "kwama karen",
        "jam karen bado", "karen imejam", "traffic karen", "jam karen saa hii",
        "karen jam ya kufa",
    ]),
    ("roysambu_jam", 108, 1.2, [
        "jam roysambu", "imejam roysambu", "tumekwama roysambu", "roysambu traffic mob",
        "jam roy", "roysambu hatusongi", "imejam roysambu sana", "kwama roysambu",
        "jam roysambu bado", "roysambu imejam", "traffic roysambu", "jam roysambu saa hii",
        "roysambu jam ya kufa",
    ]),
    ("makadara_police", 105, 1.1, [
        "karao makadara", "polisi makadara wanashika magari", "police makadara",
        "karao wako makadara", "msako makadara", "polisi makadara bado", "karaos makadara",
        "police check makadara", "karao makadara leseni", "crackdown makadara",
        "polisi makadara saa hii", "karao makadara wengi", "makadara polisi",
    ]),
    ("mwangaza_fare", 20, 3.0, [
        "mwangaza wameongeza fare 120",
        "bei ya mwangaza ni 120 sasa",
        "mwangaza 120 bob odeon",
    ]),
    ("ngara_accident", 22, 2.0, [
        "ajali ngara, matatu imegongwa",
        "acc ngara lane moja",
        "ACC NGARA msee ameangushwa, lane moja imefungwa",
        "ngara accident still there? traffic ni mob",
        "ajali ngara bado iko",
    ]),
    ("flyers_fare", 26, 3.6, [
        "100 bob odeon to g45 ni wizi, flyers",
        "flyers fare 100 kutoka odeon",
        "flyers wameweka 100 odeon",
        "bei ya flyers 100 odeon mvua",
        "fare ni 100 sasa odeon, flyers wameongeza",
        "flyers 100 bob odeon bado",
    ]),
    ("kasarani_jam", 14, 1.6, [
        "imejam kasarani bana, hatusongi",
        "jam kasarani mbaya",
        "imejam kutoka roysambu mpaka kasarani, kama 40 min",
        "tumekwama kasarani",
    ]),
]

PENDING_EVENTS = [
    # still active at "now"
    ("g45_police", 11, 2.0, ["karao wako stage githurai 45", "polisi g45 wanacheck leseni"]),
    ("zuri_fare", 18, 6.0, ["zuri line fare 90 odeon", "zuri wameweka 90 bob"]),
    ("kangemi_jam", 25, 5.0, ["jam kangemi", "imejam kangemi bana"]),
    ("ngong_jam", 30, 6.0, ["jam ngong town", "imejam ngong"]),
    # older ones that never reached 3 and have since expired
    ("kawangware_jam", 119, 2.0, ["jam kawangware", "imejam kawangware"]),
    ("buruburu_jam", 117, 2.0, ["jam buruburu", "imejam buru"]),
    ("muthurwa_jam", 102, 2.0, ["jam muthurwa", "tumekwama muthurwa"]),
    ("prestige_police", 114, 2.0, ["karao prestige", "polisi prestige"]),
    ("ngong_jam_old", 85, 2.0, ["jam ngong", "tumekwama ngong"]),
    ("pangani_jam", 116, 2.0, ["jam pangani", "imejam pangani"]),
    ("muthaiga_police", 100, 2.0, ["karao muthaiga", "polisi muthaiga"]),
    ("museum_jam", 113, 2.0, ["jam museum hill", "imejam museum"]),
    ("westlands_police", 88, 2.0, ["karao westlands", "polisi westie"]),
    ("junction_police", 90, 2.0, ["karao junction", "polisi the junction"]),
    ("donholm_police", 85, 2.0, ["karao donholm", "polisi donholm"]),
]

BLOCKLIST_SPAM = [
    "WIN KES 50,000!! tuma 200 upate zawadi",
    "Loans in 5 min, click link sasa hivi",
    "Umeshinda zawadi ya simu! tuma pesa 100",
    "Instant loan bila security www.pesa-haraka.com",
    "click hapa upate bonus bit.ly/xx12",
    "WIN a car! sms WIN to 22333",
    "mkopo wa haraka, tuma ID yako",
    "jackpot ya leo, tuma pesa 50",
    "Congratulations winner of KES 10,000",
    "loan ya 5k ndani ya dakika 2",
    "promo! click to claim zawadi",
    "send money 200 to activate prize",
    "zawadi yako inakungoja click link",
    "https://free-airtime.ke claim now",
    "loans loans loans dm",
    "win iphone 15, click hapa",
    "tuma pesa 99 upate 1000",
    "BONUS ya Safaricom click hapa",
    "Get loan now www.mkopo-now.co",
    "WIN WIN WIN tuma pesa",
    "umeshinda KES 30,000",
    "loan offer for matatu drivers",
    "zawadi! jibu YES",
    "click this link for free fare",
    "promo code ya bure, click",
    "jackpot imefika, send money",
    "win shopping voucher",
    "mkopo bila stress",
    "fast loans 24/7 www.loanzz.com",
    "tuma pesa kwa hii namba upate zawadi",
]

UNPARSEABLE_SPAM = [
    "hi", "?", "sasa", "niaje", "ok", "test", "mambo vipi", "asante", "nani anajua",
    "hello", "stop", "yes", "no", "help", "...", "poa", "uko wapi", "nitumie", "aaaa",
    "subscribe", "sawa", "ni nini hii",
]

# One phone flooding: 5 nonsense texts, then 4 real-looking ones that the rate limit stops.
FLOOD_NONSENSE = ["hello", "hello?", "hello??", "mko?", "jibu"]
FLOOD_REAL = ["jam kasarani", "imejam kasarani", "jam kasarani bado", "kasarani jam"]

# Votes that clear events after they were verified: (event key, minutes_before_now).
CLEARING_VOTES = [("moi_closed", 35), ("moi_closed", 34), ("kasarani_police", 45), ("kasarani_police", 44)]


def _phone(rng, used):
    while True:
        p = "+2547" + "".join(str(rng.randint(0, 9)) for _ in range(8))
        if p not in used:
            used.add(p)
            return p


def build_demo_sms(now):
    """Returns (messages, clearing_votes).

    messages: list of dicts {phone, text, at, key} sorted by time; key is the event key or
    a spam label. clearing_votes: list of (event_key, at).
    """
    rng = random.Random(4729)
    used = set()
    msgs = []

    for key, start, spacing, texts in VERIFIED_EVENTS + PENDING_EVENTS:
        for i, text in enumerate(texts):
            at = now - timedelta(minutes=start) + timedelta(minutes=spacing * i)
            msgs.append({"phone": _phone(rng, used), "text": text, "at": at, "key": key})

    for text in BLOCKLIST_SPAM:
        at = now - timedelta(minutes=rng.uniform(1, 119))
        msgs.append({"phone": _phone(rng, used), "text": text, "at": at, "key": "spam:blocklist"})

    for text in UNPARSEABLE_SPAM:
        at = now - timedelta(minutes=rng.uniform(1, 119))
        msgs.append({"phone": _phone(rng, used), "text": text, "at": at, "key": "spam:unparseable"})

    flood_phone = _phone(rng, used)
    base = now - timedelta(minutes=48)
    for i, text in enumerate(FLOOD_NONSENSE):
        msgs.append({"phone": flood_phone, "text": text, "at": base + timedelta(seconds=40 * i), "key": "spam:unparseable"})
    for i, text in enumerate(FLOOD_REAL):
        msgs.append({"phone": flood_phone, "text": text, "at": base + timedelta(minutes=4, seconds=40 * i), "key": "spam:rate_limit"})

    msgs.sort(key=lambda m: m["at"])
    votes = [(key, now - timedelta(minutes=m)) for key, m in CLEARING_VOTES]
    return msgs, votes
