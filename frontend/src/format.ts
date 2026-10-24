// All times are shown in UK local time – the market's clock.
const TZ = 'Europe/London'

export const fmtTime = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

export const fmtDateTime = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', {
    timeZone: TZ,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))

export const fmtDay = (isoDate: string) =>
  new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(`${isoDate}T00:00:00Z`),
  )

export const fmtShortDay = (isoDate: string) =>
  new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(`${isoDate}T00:00:00Z`),
  )

export const mw = (v: number | null | undefined, digits = 0) =>
  v == null ? '—' : `${v.toLocaleString('en-GB', { maximumFractionDigits: digits })}`

export const gw = (v: number | null | undefined) => (v == null ? '—' : (v / 1000).toFixed(2))

export const signed = (v: number | null | undefined) =>
  v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toLocaleString('en-GB', { maximumFractionDigits: 0 })}`

export const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v)}%`)

export const gbp = (v: number | null | undefined) => {
  if (v == null) return '—'
  const a = Math.abs(v)
  const s = a >= 1e6 ? `£${(a / 1e6).toFixed(1)}m` : a >= 1e3 ? `£${Math.round(a / 1e3)}k` : `£${Math.round(a)}`
  return v < 0 ? `−${s}` : s
}

export const addDays =(isoDate: string, n: number) => {
  const d = new Date(`${isoDate}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}
