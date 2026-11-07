# MatatuPulse

Live matatu fares and verified alerts, from commuters on the route. *Signal from the noise.*

Commuters report fare hikes, jams, accidents/police and closures by app or free-text SMS. Every report is kept raw; duplicates merge into an **Event**, and an Event becomes **verified** once 3 distinct phones confirm it. The Signal panel shows the funnel: **200 raw SMS → 61 spam → 27 events → 12 verified**.

```
backend/   Django 5 + DRF + simplejwt (SQLite locally, Postgres via DATABASE_URL)
  accounts/   phone + OTP login (hashed codes, expiry, cooldowns)
  transit/    routes, stages, saccos + the real Nairobi catalogue (data/)
  reports/    process_report, votes, Signal, demo replay
  messaging/  SMS out via ThriveWave, delivery reports, OutboundSms log
frontend/  React + Vite + Tailwind + TanStack Query (polls every 15 s)
designs/   the source designs        MatatuPulse — Build Plan.pdf   the plan
```

Data: 5 demo routes for the pitch (Route 100 Odeon → Githurai 45 …) plus the real catalogue from
Mat3Route's `scraped_routes.csv`: 97 route/sacco rows across 17 lines and 6 saccos (Super Metro,
Citi Hoppa, NACICO …) with fare ranges, and 88 stages with coordinates.

## Run it locally

```bash
# API: http://localhost:8000
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
cp .env.example .env              # then edit; never commit .env
python manage.py seed_demo        # demo routes, real catalogue, staff user, 200-SMS replay
python manage.py runserver

# App: http://localhost:5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Sign in with a Kenyan number and the code sent by SMS. With `SMS_PROVIDER=console` (the default)
the code is printed in the API's console instead. Numbers listed in `OTP_TEST_NUMBERS` skip the SMS
and accept **4729**, which is handy for judges and rehearsals.
`+254 712 345 678` is the staff user, and only staff see **Replay demo** on `/signal`.

To demo on a phone over the laptop's hotspot, run `python manage.py runserver 0.0.0.0:8000` and open `http://<laptop-ip>:5173`.

## Demo script (3 min)

1. On a phone, sign in and open **Route 100**. It shows the **Kwama** pill, the **Accident at Ngara** banner, Thika Road Flyers at **KES 100**, and Zuri Line pending at **KES 90?**.
2. On a second phone (a different number), tap **Report**, choose Fare hike, Zuri Line, KES 90, and submit. You get *"Thanks — 2 others reported this"*, and the Zuri card turns verified at KES 90 (+20).
3. On the laptop, open **/signal**. The funnel shows 200 → 61 → 27 → 12, spam is struck through, and the verified events and alert log tell the story.

Reset before each run: `python manage.py replay_sms` or the **Replay demo** button. Replay timestamps are relative to "now", so the data always looks live.

## How it works: `reports/services.py`

`process_report(report)` runs inline for every app report and inbound SMS:

1. **Parse** (SMS only). It finds the type from Sheng keywords, the stage from `Stage.aliases` (`g45` → Githurai 45, "kutoka X **mpaka** Y" → Y), the fare as the first 2–3 digit number, and the sacco by name. All word lists live in `reports/keywords.py`.
2. **Spam**. A message is spam if it has blocklisted words or a URL, if nothing usable was parsed, or if one phone sent more than 5 reports in 10 min.
3. **Merge** into an open Event with the same route and type, first seen within 30 min, and at the same stage. Fare hikes also need the same sacco and a fare within KES 10.
4. **Verify** at 3 distinct phones. This writes an Alert and SMSes route subscribers.
5. **Votes**. "Still accurate?" counts as a reporter and extends expiry. Two "Cleared?" votes clear the event.
6. **Expiry on read**. Jam and police expire after 60 min, accidents after 2 h, fare hikes after 6 h, and closures only when cleared.

Derived on read:
- **Sacco fare**: a verified hike, else a pending hike shown as "KES 90?", else the usual fare.
- **Route pill**: **Kwama** if a verified accident, closure or jam is active; **Moderate** if any other report is active; else **Maji Safi**.

## API (`/api/`)

| Method | Path | |
|---|---|---|
| POST | `auth/otp/request` | `{phone}` |
| POST | `auth/otp/verify` | `{phone, code}` → `{access, refresh, user}` |
| POST | `auth/refresh` | simplejwt refresh |
| GET | `routes?search=` | list with `pill`, `alert_count`, `subscribed` |
| GET | `routes/{id}` | saccos with derived fares, `banner`, `events` |
| POST | `routes/{id}/subscribe` | toggle the bell |
| POST | `reports` | `{route, type, subtype?, sacco?, fare?, note?}` → `{event, others_count, merged_count, verified_now}` |
| POST | `events/{id}/vote` | `{kind: "still" \| "cleared"}` |
| POST | `sms/inbound` | Africa's Talking callback (`from`, `text`), public |
| GET | `signal` | funnel, raw reports, verified events, alert log, public |
| POST | `demo/replay` | staff only |

Example responses are in `frontend/src/mocks/`.

Try an SMS by hand:

```bash
curl -X POST localhost:8000/api/sms/inbound -d from=+254733000111 -d "text=imejam kasarani bana"
```

## Tests

```bash
cd backend && python manage.py test     # parse, spam, merge, verify, votes, expiry, funnel, API
cd frontend && npm run build && npm run lint
```

## SMS and OTP

- **Login codes:** 4 digits, stored only as an HMAC, valid for 5 minutes, at most 5 wrong tries, a
  30 s resend cooldown and 5 codes per number per hour. There is also a per-IP throttle. If the SMS
  can't be sent the API returns 503 and the code is discarded.
- **ThriveWave:** set `SMS_PROVIDER=thrivewave`, `THRIVEWAVE_API_KEY` and `THRIVEWAVE_SENDER_ID`.
  Requests are `POST https://sms.thrivevas.com/v1/message/send` with an `x-api-key` header and
  `{message, msisdn, sender_id, callback_url?}`, ported from Mat3Route's adapter. The URL, path and
  sender are all settings. Check a live send with `python manage.py send_test_sms 07XXXXXXXX`, which
  prints the raw reply.
- **Every SMS** (OTPs, alerts, tests) is logged in `OutboundSms` (Django admin) with the provider's
  reply and its delivery status.
- **Webhooks** need `?token=$SMS_WEBHOOK_TOKEN`:
  - `POST /api/sms/delivery` receives delivery reports. Set `THRIVEWAVE_CALLBACK_URL` to it.
  - `POST /api/sms/inbound` receives commuter SMS (`from`/`msisdn` and `text`/`message`).

## Deploy (Fly.io, reusing `mat3route-api` and `mat3route-db`)

```bash
cd backend
fly secrets set SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(50))") \
  THRIVEWAVE_API_KEY=... THRIVEWAVE_SENDER_ID=... \
  SMS_WEBHOOK_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(24))") \
  OTP_TEST_NUMBERS=+254712345678 \
  CORS_ALLOWED_ORIGINS=https://<your-frontend>.vercel.app
# DATABASE_URL is already set by the mat3route-db attachment
fly deploy        # release_command migrates and seeds routes (no SMS replay)
fly ssh console -C "python manage.py replay_sms"   # load the pitch scenario
```

Django's tables (`transit_route`, `reports_event` …) sit alongside the old FastAPI tables in the
same database without clashing.

**Front-end (Vercel):** set the root directory to `MatatuPulse/frontend` and
`VITE_API_URL=https://mat3route-api.fly.dev`. SPA rewrites are in `vercel.json` (and
`public/_redirects` for Netlify).
