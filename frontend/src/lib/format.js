import { useEffect, useState } from 'react'

export function minutesAgo(iso, now = Date.now()) {
  if (!iso) return null
  return Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000))
}

export function timeAgo(iso, now = Date.now()) {
  const m = minutesAgo(iso, now)
  if (m === null) return ''
  if (m < 1) return 'just now'
  if (m < 60) return `${m} min ago`
  const h = Math.floor(m / 60)
  return `${h} h ago`
}

export function clock(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Nairobi' })
}

/** Re-render every 30 s so "N min ago" stays fresh between polls. */
export function useNow(interval = 30000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), interval)
    return () => clearInterval(t)
  }, [interval])
  return now
}

/** "712345678" -> "712 345 678" */
export function groupPhone(digits) {
  const d = digits.replace(/\D/g, '').slice(0, 9)
  return [d.slice(0, 3), d.slice(3, 6), d.slice(6, 9)].filter(Boolean).join(' ')
}

export function useMediaQuery(query) {
  const get = () => typeof window !== 'undefined' && window.matchMedia(query).matches
  const [matches, setMatches] = useState(get)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const on = () => setMatches(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [query])
  return matches
}

// The sidebar layout needs ~1024px; tablets in portrait use the phone layout (centred).
export const useIsDesktop = () => useMediaQuery('(min-width: 1024px)')

const RECENT_KEY = 'mp_recent_routes'
export function getRecent() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY)) || []
  } catch {
    return []
  }
}
export function pushRecent(route) {
  try {
    const item = { id: route.id, number: route.number, destination: route.destination }
    const next = [item, ...getRecent().filter((r) => r.id !== route.id)].slice(0, 2)
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    /* ignore */
  }
}
