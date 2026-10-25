import { Activity, Gauge, History, Radio, ShieldCheck, Sunrise, Target, Timer, TrendingUp, Wind, Zap } from 'lucide-react'
import { useMemo } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api, type Basis, type SeriesPoint } from '../api'
import { fmtDateTime, fmtDay, fmtTime, gw, mw, pct, signed } from '../format'
import { useAsync } from '../hooks'
import { AiNote } from './AiNote'
import { C, axisProps, tooltipStyle } from './chartTheme'
import { ErrorBox, Loading, Panel, Stat } from './Stat'

interface Props {
  date: string
  cutoff: string
  basis: Basis
}

const gwTick = (v: number) => (v / 1000).toLocaleString('en-GB', { maximumFractionDigits: 1 })

/** Share of half-hours where at least the firm figure arrived. */
function firmHeld(series: SeriesPoint[]) {
  const p = series.filter((x) => x.actual != null && x.firm != null)
  if (!p.length) return null
  return (100 * p.filter((x) => x.actual! >= x.firm!).length) / p.length
}

export function DayAheadView({ date, cutoff, basis }: Props) {
  const day = useAsync(() => api.day(date, cutoff, basis), [date, cutoff, basis])

  const rows = useMemo(() => {
    if (!day.data) return []
    const metered = day.data.basis === 'metered'
    return day.data.series.map((p) => ({
      t: p.t,
      actual: p.actual,
      forecast: p.forecast,
      plan: p.plan,
      firm: p.firm,
      // Between the firm figure and the plan: where to expect delivered wind.
      band: p.firm == null || p.plan == null ? null : [p.firm, Math.max(p.firm, p.plan)],
      // On the delivered basis, what wind could have done without the grid switching it off.
      available: metered && p.actual != null && (p.curtailed ?? 0) > 0 ? p.actual + (p.curtailed ?? 0) : null,
    }))
  }, [day.data])

  const vintageRows = useMemo(() => {
    if (!day.data) return []
    const byT = new Map<string, Record<string, number | string | null>>()
    for (const p of day.data.series) byT.set(p.t, { t: p.t, actual: p.actual })
    day.data.vintages.forEach((v, i) => {
      for (const pt of v.points) {
        const row = byT.get(pt.t) ?? { t: pt.t }
        row[`v${i}`] = pt.v
        byT.set(pt.t, row)
      }
    })
    return [...byT.values()].sort((a, b) => String(a.t).localeCompare(String(b.t)))
  }, [day.data])

  if (day.loading && !day.data) return <Loading />
  if (day.error) return <ErrorBox message={day.error} />
  const d = day.data!
  const s = d.summary
  const o = d.outlook
  const curtailed = d.series.map((p) => p.curtailed ?? 0)
  const meanCurtailed = curtailed.length ? curtailed.reduce((a, b) => a + b, 0) / curtailed.length : 0
  const held = firmHeld(d.series)
  const used = d.forecast_publish_time
  const leadAtStart = used && d.series.length ? (new Date(d.series[0].t).getTime() - new Date(used).getTime()) / 3.6e6 : null

  return (
    <div className="stack">
      <div className="decision-banner">
        <div>
          <Timer className="ico" size={20} strokeWidth={1.75} aria-hidden />
          <div>
            <span className="eyebrow">Decision point</span>
            <strong>{d.cutoff_utc ? fmtDateTime(d.cutoff_utc) : '—'}</strong>
            <span className="muted"> for delivery on {fmtDay(d.date)}</span>
          </div>
        </div>
        <div>
          <Radio className="ico" size={20} strokeWidth={1.75} aria-hidden />
          <div>
            <span className="eyebrow">Latest forecast available</span>
            {used ? (
              <>
                <strong>published {fmtDateTime(used)}</strong>
                <span className="muted"> · {leadAtStart?.toFixed(0)} h before delivery starts</span>
              </>
            ) : (
              <strong className="warn">No forecast had been published yet</strong>
            )}
          </div>
        </div>
      </div>

      <section className="brief" aria-label="Morning brief">
        <div className="brief__head">
          <span className="brief__title">
            <Sunrise className="ico" size={18} strokeWidth={1.75} aria-hidden />
            Morning brief · buying for {fmtDay(d.date)}
          </span>
          {o.ran_high_pct != null && (
            <span className={`brief__tag${o.ran_high_pct > 0 ? ' brief__tag--warn' : ''}`}>
              <TrendingUp size={13} strokeWidth={2} aria-hidden />
              Last {o.n_days} days: forecast ran {pct(Math.abs(o.ran_high_pct))} {o.ran_high_pct > 0 ? 'high' : 'low'}
            </span>
          )}
        </div>
        <div className="brief__nums">
          <div>
            <span>
              <Gauge size={14} strokeWidth={1.75} aria-hidden /> Forecast says
            </span>
            <strong>
              {gw(o.forecast_mean)}
              <small>GW</small>
            </strong>
            <em>latest run before the cutoff</em>
          </div>
          <div className="brief__plan">
            <span>
              <Target size={14} strokeWidth={1.75} aria-hidden /> Plan on
            </span>
            <strong>
              {gw(o.plan_mean)}
              <small>GW</small>
            </strong>
            <em>forecast {signed(o.bias != null ? -o.bias : null)} MW recent bias</em>
          </div>
          <div>
            <span>
              <ShieldCheck size={14} strokeWidth={1.75} aria-hidden /> Firm · 90% safe
            </span>
            <strong>
              {gw(o.firm_mean)}
              <small>GW</small>
            </strong>
            <em>forecast − {mw(o.buffer_p90)} MW buffer</em>
          </div>
        </div>
        <p className="brief__foot">
          {o.plan_mean == null
            ? `Not enough settled history before this day (${o.n_days ?? 0} days) to size planning figures.`
            : `Sized only from the ${o.n_days} delivery days already settled at the decision (D-15 to D-2), so no hindsight.`}
        </p>
      </section>

      <AiNote date={d.date} cutoff={d.cutoff_local} basis={d.basis} />

      <div className="stats">
        <Stat
          label="Actual wind (day avg)"
          icon={Wind}
          value={gw(s.mean_actual)}
          unit="GW"
          note={d.basis === 'metered' ? 'metered, delivered (FUELHH)' : 'delivered + switched off'}
          tone="accent"
        />
        <Stat
          label="Forecast error this day"
          icon={Activity}
          value={mw(s.mae)}
          unit="MW MAE"
          note={s.bias != null ? `bias ${signed(s.bias)} MW · ${s.bias > 0 ? 'wind fell short' : 'wind beat forecast'}` : undefined}
        />
        <Stat
          label="Wind switched off by grid"
          icon={Zap}
          value={gw(meanCurtailed)}
          unit="GW avg"
          note="paid to reduce output (constraints)"
          tone={meanCurtailed > 1000 ? 'warn' : 'default'}
        />
        <Stat
          label="Firm figure held"
          icon={ShieldCheck}
          value={pct(held)}
          unit="of half-hours"
          note="delivered wind ≥ firm figure (target 90%)"
          tone={held != null && held < 80 ? 'warn' : 'default'}
        />
      </div>

      <Panel
        title="Forecast at decision time vs what actually happened"
        icon={Activity}
        subtitle="Shaded band: from the firm figure (90% safe) up to the plan figure, both sized from settled days only. Grey dotted: wind that was available but switched off by the grid."
      >
        <div className="chart">
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="t" tickFormatter={fmtTime} minTickGap={40} {...axisProps} />
              <YAxis tickFormatter={gwTick} width={44} {...axisProps} label={{ value: 'GW', angle: -90, position: 'insideLeft', fill: C.axis, fontSize: 11 }} />
              <Tooltip
                {...tooltipStyle}
                labelFormatter={(l) => fmtTime(String(l))}
                formatter={(v, name) =>
                  Array.isArray(v) ? [`${mw(v[0] as number)} – ${mw(v[1] as number)} MW`, name] : [`${mw(v as number)} MW`, name]
                }
              />
              <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
              <Area dataKey="band" name="Firm → plan range" fill={C.band} fillOpacity={0.16} stroke="none" connectNulls isAnimationActive={false} />
              <Line dataKey="forecast" name="Day-ahead forecast" stroke={C.forecast} strokeWidth={2.5} strokeDasharray="6 4" dot={false} connectNulls isAnimationActive={false} />
              <Line dataKey="plan" name="Plan figure" stroke={C.forecast} strokeWidth={1.5} dot={false} connectNulls isAnimationActive={false} />
              <Line dataKey="firm" name="Firm (90%)" stroke={C.shortfall} strokeWidth={1.5} strokeDasharray="2 3" dot={false} connectNulls isAnimationActive={false} />
              <Line dataKey="available" name="Available (incl. switched off)" stroke={C.later} strokeWidth={1.5} strokeDasharray="1 3" dot={false} connectNulls isAnimationActive={false} />
              <Line dataKey="actual" name="Actual" stroke={C.actual} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel
        title="How the forecast evolved"
        icon={History}
        subtitle="Teal runs were available before your cutoff; grey runs arrived after it. Shows how much the picture could still move."
      >
        <div className="chart">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={vintageRows} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="t" tickFormatter={fmtTime} minTickGap={40} {...axisProps} />
              <YAxis tickFormatter={gwTick} width={44} {...axisProps} />
              <Tooltip {...tooltipStyle} labelFormatter={(l) => fmtTime(String(l))} formatter={(v, name) => [`${mw(v as number)} MW`, name]} />
              {d.vintages.map((v, i) => (
                <Line
                  key={v.publish_time}
                  dataKey={`v${i}`}
                  name={`Run ${fmtDateTime(v.publish_time)}${v.available_at_cutoff ? '' : ' (after cutoff)'}`}
                  stroke={v.available_at_cutoff ? C.forecast : C.later}
                  strokeOpacity={v.available_at_cutoff ? 0.45 + (0.55 * (i + 1)) / d.vintages.length : 0.8}
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
              <Line dataKey="actual" name="Actual" stroke={C.actual} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
              <ReferenceLine y={0} stroke={C.grid} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  )
}
