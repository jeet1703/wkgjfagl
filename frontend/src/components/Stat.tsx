import type { LucideIcon } from 'lucide-react'
import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  unit?: string
  note?: ReactNode
  tone?: 'default' | 'accent' | 'warn'
  icon?: LucideIcon
}

export function Stat({ label, value, unit, note, tone = 'default', icon: Icon }: Props) {
  return (
    <div className={`stat stat--${tone}`}>
      <div className="stat__label">
        {Icon && <Icon className="ico" size={15} strokeWidth={1.75} aria-hidden />}
        {label}
      </div>
      <div className="stat__value">
        {value}
        {unit && <span className="stat__unit">{unit}</span>}
      </div>
      {note && <div className="stat__note">{note}</div>}
    </div>
  )
}

export function Panel({
  title,
  subtitle,
  children,
  aside,
  icon: Icon,
}: {
  title: string
  subtitle?: ReactNode
  children: ReactNode
  aside?: ReactNode
  icon?: LucideIcon
}) {
  return (
    <section className="panel">
      <header className="panel__head">
        <div>
          <h2>
            {Icon && <Icon className="ico" size={17} strokeWidth={1.75} aria-hidden />}
            {title}
          </h2>
          {subtitle && <p className="panel__sub">{subtitle}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  )
}

export function Loading() {
  return <div className="state">Loading…</div>
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="state state--error">
      <AlertTriangle size={16} strokeWidth={1.75} aria-hidden style={{ verticalAlign: '-3px', marginRight: 6 }} />
      Couldn’t load data. {message}
    </div>
  )
}
