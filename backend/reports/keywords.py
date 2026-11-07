"""Every word list the SMS parser uses lives here, so it is easy to extend on the day.

All entries are lowercase. Single words are matched as whole tokens; entries with a
space are matched as phrases.
"""

# Event type keywords. Checked in this priority order: a message that mentions an
# accident and a lane being closed is an accident.
TYPE_KEYWORDS = [
    ("accident_police", [
        "acc", "accident", "ajali", "crash", "ameangushwa", "imegongwa", "gongwa",
        "karao", "karaos", "polisi", "police", "cops", "crackdown", "msako", "leseni",
    ]),
    ("route_closed", ["imefungwa", "closed", "fungwa", "barabara imefungwa", "maandamano"]),
    ("jam", ["jam", "imejam", "jammed", "kwama", "tumekwama", "stall", "traffic", "hatusongi", "squeeze"]),
    ("fare_hike", ["fare", "bei", "kes", "ksh", "bob", "doo", "pesa ya gari", "nauli", "wameweka", "wameongeza", "imepanda"]),
]

# Words that mean "police" rather than "accident" inside accident_police.
POLICE_WORDS = {"karao", "karaos", "polisi", "police", "cops", "crackdown", "msako", "leseni"}

# A message containing any of these is spam.
BLOCKLIST_WORDS = {"win", "winner", "zawadi", "loan", "loans", "mkopo", "click", "promo", "jackpot", "bonus"}
BLOCKLIST_PHRASES = ["tuma pesa", "send money", "umeshinda"]
URL_PATTERN = r"(https?://|www\.|\b[a-z0-9-]+\.(com|ke|ly|net|org|co)\b)"

# Short names for saccos, matched against Route sacco names.
SACCO_ALIASES = {
    "Thika Road Flyers": ["flyers", "flyer", "thika road flyers", "trf"],
    "Mwangaza Sacco": ["mwangaza"],
    "Haraka Shuttle": ["haraka"],
    "Zuri Line": ["zuri", "zuri line"],
}

# "kutoka X mpaka Y": the trouble is usually at Y.
DESTINATION_MARKERS = ["mpaka", "hadi", "till", "until"]

RATE_LIMIT_COUNT = 5
RATE_LIMIT_MINUTES = 10
