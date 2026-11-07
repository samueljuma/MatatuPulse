import { Link } from 'react-router-dom'
import RouteChip from './RouteChip'
import StatusPill from './StatusPill'

/**
 * One route row. `compact` is the desktop sidebar (narrow column): the status pill sits under
 * the name. On phones the pill is on the right from 380px up, and under the name below that.
 */
export default function RouteListItem({ route, selected, compact }) {
  const sub = [route.via ? `via ${route.via}` : route.line, route.alert_count ? `${route.alert_count} alert${route.alert_count > 1 ? 's' : ''}` : null]
    .filter(Boolean)
    .join(' · ')
  const pillBelow = compact ? 'mt-1.5 flex' : 'mt-1.5 flex xs:hidden'
  return (
    <Link
      to={`/routes/${route.id}`}
      aria-current={selected ? 'page' : undefined}
      className={`flex items-center border-b border-border last:border-b-0 transition ${
        compact ? 'gap-3 px-4 py-3' : 'gap-3 px-4 py-4 xs:gap-4 xs:px-5'
      } ${selected ? `border-l-4 border-l-primary bg-primary-tint ${compact ? 'pl-3' : 'pl-3 xs:pl-4'}` : 'bg-surface hover:bg-background'}`}
    >
      {selected ? (
        <span className={`shrink-0 text-center font-semibold text-primary ${compact ? 'w-12 text-base' : 'w-12 text-lg xs:w-14 xs:text-xl'}`}>
          {route.number}
        </span>
      ) : (
        <RouteChip number={route.number} tone="tint" size={compact ? 'sm' : 'md'} className={compact ? 'w-12' : 'w-12 xs:w-14'} />
      )}
      <span className="min-w-0 flex-1">
        <span className={`block font-semibold leading-snug text-ink ${compact ? 'text-sm' : 'text-base'}`}>{route.name}</span>
        <span className={`block text-muted ${compact ? 'text-xs' : 'text-sm'}`}>{sub}</span>
        <span className={pillBelow}>
          <StatusPill status={route.pill} />
        </span>
      </span>
      {!compact && (
        <span className="hidden xs:block">
          <StatusPill status={route.pill} />
        </span>
      )}
    </Link>
  )
}
