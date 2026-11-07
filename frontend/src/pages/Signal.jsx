import { ArrowDown, ArrowRight, MessageCircle, RotateCcw, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { replayDemo } from '../api/client'
import { useSignal } from '../api/queries'
import Button from '../components/Button'
import { LogoMark } from '../components/Logo'
import StatTile from '../components/StatTile'
import { clock } from '../lib/format'
import { useAuth } from '../lib/useAuth'

const SHOW_VERIFIED = 5

/** 5 — Signal panel: how 200 messy SMS become 12 alerts you can trust. */
export default function Signal() {
  const auth = useAuth()
  const qc = useQueryClient()
  const { data, isLoading, error, dataUpdatedAt } = useSignal()
  const [showAll, setShowAll] = useState(false)
  const [replaying, setReplaying] = useState(false)

  const replay = async () => {
    setReplaying(true)
    try {
      await replayDemo()
      await qc.invalidateQueries()
    } finally {
      setReplaying(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-[1280px] px-4 py-6 md:px-8 md:py-8">
        <header className="flex flex-wrap items-start gap-x-4 gap-y-3">
          <span className="sm:hidden"><LogoMark size="md" /></span>
          <span className="hidden sm:block"><LogoMark size="lg" /></span>
          <div className="min-w-0 flex-1 basis-[200px]">
            <h1 className="text-xl font-bold leading-tight text-ink sm:text-[26px] md:text-[28px]">MatatuPulse Signal</h1>
            <p className="mt-1 text-sm text-muted sm:text-base">
              Signal from the noise — how {data?.funnel.raw ?? 200} messy SMS become {data?.funnel.verified ?? 12} alerts you can trust.
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:gap-3">
            {auth?.user?.is_staff && (
              <Button variant="secondary" size="sm" onClick={replay} disabled={replaying} title="Wipe and replay the 200 seed SMS">
                <RotateCcw className={`h-4 w-4 ${replaying ? 'animate-spin' : ''}`} /> {replaying ? 'Replaying…' : 'Replay demo'}
              </Button>
            )}
            <span
              className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-ink sm:px-4 sm:py-2 sm:text-sm"
              title={dataUpdatedAt ? `Updated ${new Date(dataUpdatedAt).toLocaleTimeString()}` : undefined}
            >
              <span className={`h-2.5 w-2.5 rounded-full ${error ? 'bg-alert' : 'bg-fare-normal'}`} />
              {error ? 'Offline' : 'Live'} · Nairobi · last 2 hours
            </span>
          </div>
        </header>

        {isLoading && <p className="mt-10 text-muted">Loading the signal…</p>}
        {error && !data && <p className="mt-10 text-alert">Could not reach the API: {error.message}</p>}

        {data && (
          <>
            <Funnel f={data.funnel} />

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <RawReports reports={data.reports} />
              <section className="self-start overflow-hidden rounded-xl border border-border bg-surface">
                <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
                  <h2 className="text-xl font-semibold text-ink">Verified events</h2>
                  <span className="text-sm font-medium text-muted">
                    {data.funnel.verified} verified · {data.pending_count} pending
                  </span>
                </div>
                <ul>
                  {(showAll ? data.verified_events : data.verified_events.slice(0, SHOW_VERIFIED)).map((e) => (
                    <li key={e.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-4 last:border-b-0 sm:flex-nowrap sm:px-5">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-alert-tint text-alert">
                        <TriangleAlert className="h-5 w-5" />
                      </span>
                      <div className="w-[calc(100%-3.5rem)] min-w-0 sm:w-auto sm:flex-1">
                        <p className="text-base font-semibold text-ink">{e.title}</p>
                        <p className="text-sm text-muted">
                          {e.ref} · {e.routes} · first report {clock(e.first_seen)} · verified {clock(e.verified_at)}
                        </p>
                      </div>
                      <span className="ml-14 shrink-0 rounded-full bg-alert px-2.5 py-0.5 text-sm font-semibold text-white sm:ml-0">
                        {e.reports} reports
                      </span>
                    </li>
                  ))}
                </ul>
                {data.verified_events.length > SHOW_VERIFIED && (
                  <button
                    type="button"
                    onClick={() => setShowAll((v) => !v)}
                    className="w-full border-t border-border px-5 py-4 text-left text-base text-muted hover:bg-background"
                  >
                    {showAll ? 'Show fewer' : `+ ${data.verified_events.length - SHOW_VERIFIED} more verified today`}
                  </button>
                )}
              </section>
            </div>

            <AlertLog alerts={data.alerts} />

            <p className="mt-6 text-center text-sm text-muted">
              <Link to="/routes" className="font-semibold text-primary hover:underline">Open the commuter app →</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}

function Funnel({ f }) {
  const tiles = [
    { label: 'Raw reports', value: f.raw },
    { label: 'Spam rejected', value: f.spam, muted: true },
    { label: 'Events (merged)', value: f.events },
    { label: 'Verified (3+ confirmations)', value: f.verified, highlight: true },
  ]
  return (
    <div className="mt-6 grid grid-cols-2 gap-3 md:mt-8 md:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] md:items-center md:gap-4">
      {tiles.map((t, i) => (
        <FunnelStep key={t.label} tile={t} last={i === tiles.length - 1} />
      ))}
    </div>
  )
}

function FunnelStep({ tile, last }) {
  return (
    <>
      <StatTile {...tile} />
      {!last && (
        <span className="hidden text-muted md:block" aria-hidden="true">
          <ArrowRight className="h-6 w-6" />
        </span>
      )}
    </>
  )
}

function RawReports({ reports }) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="text-xl font-semibold text-ink">Raw SMS reports</h2>
        <span className="flex items-center gap-1 text-sm font-medium text-muted">
          Newest first <ArrowDown className="h-3.5 w-3.5" />
        </span>
      </div>
      <ul className="max-h-[640px] overflow-y-auto">
        {reports.map((r) => (
          <li key={r.id} className="flex flex-wrap items-start gap-x-3 gap-y-1.5 border-b border-border px-4 py-3 last:border-b-0 sm:flex-nowrap sm:px-5">
            <MessageCircle className="mt-0.5 h-5 w-5 shrink-0 text-muted" />
            <div className="w-[calc(100%-2rem)] min-w-0 sm:w-auto sm:flex-1">
              <p className={`break-words text-base ${r.is_spam ? 'text-muted line-through' : 'text-ink'}`}>{r.text}</p>
              <p className="text-sm text-muted">
                {r.phone} · {clock(r.at)}
                {r.source === 'app' && ' · app'}
              </p>
            </div>
            {r.is_spam ? (
              <span
                className="ml-8 shrink-0 rounded-full bg-pending-tint px-2.5 py-0.5 text-sm font-semibold text-pending-text sm:ml-0"
                title={{ blocklist: 'Blocklisted words or link', unparseable: 'Nothing usable parsed', rate_limit: 'Over 5 reports in 10 min' }[r.spam_reason]}
              >
                Spam
              </span>
            ) : r.event_ref ? (
              <span className="ml-8 shrink-0 rounded-full bg-primary-tint px-2.5 py-0.5 text-sm font-semibold text-primary sm:ml-0">
                → {r.event_ref} {r.event_label}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  )
}

const STATUS_CHIP = {
  Active: 'bg-alert text-white',
  Cleared: 'bg-fare-normal-tint text-fare-normal-text',
  Expired: 'bg-pending-tint text-pending-text',
}

function AlertLog({ alerts }) {
  return (
    <section className="mt-6 overflow-hidden rounded-xl border border-border bg-surface">
      <h2 className="border-b border-border px-5 py-4 text-xl font-semibold text-ink">Alert log</h2>
      <ul className="md:hidden">
        {alerts.map((a) => (
          <li key={a.id} className="border-t border-border px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <p className="font-semibold text-ink">{a.text}</p>
              <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-sm font-semibold ${STATUS_CHIP[a.status] || STATUS_CHIP.Expired}`}>
                {a.status}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted">
              <span className="tabular-nums">{clock(a.sent_at)}</span> · {a.sent_to}
            </p>
          </li>
        ))}
        {alerts.length === 0 && <li className="border-t border-border px-4 py-6 text-center text-muted">No alerts sent yet.</li>}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[720px] text-left">
          <thead className="bg-background text-sm text-muted">
            <tr>
              <th className="px-5 py-3 font-medium">Time</th>
              <th className="px-5 py-3 font-medium">Alert</th>
              <th className="px-5 py-3 font-medium">Routes</th>
              <th className="px-5 py-3 font-medium">Sent to</th>
              <th className="px-5 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} className="border-t border-border">
                <td className="px-5 py-3 text-muted tabular-nums">{clock(a.sent_at)}</td>
                <td className="px-5 py-3 font-semibold text-ink">{a.text}</td>
                <td className="px-5 py-3 text-ink">{a.routes}</td>
                <td className="px-5 py-3 text-muted">{a.sent_to}</td>
                <td className="px-5 py-3">
                  <span className={`rounded-full px-2.5 py-0.5 text-sm font-semibold ${STATUS_CHIP[a.status] || STATUS_CHIP.Expired}`}>
                    {a.status}
                  </span>
                </td>
              </tr>
            ))}
            {alerts.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-muted">No alerts sent yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
