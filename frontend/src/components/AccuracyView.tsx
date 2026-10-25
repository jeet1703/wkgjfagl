import { Activity, AlertTriangle, BarChart3, Clock, Info, PoundSterling, ShieldCheck, Target, TrendingUp, Zap } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api, type AccuracyResponse, type Basis } from '../api'
import { fmtShortDay, gbp, mw, pct, signed } from '../format'
import { useAsync } from '../hooks'
import { C, axisProps, tooltipStyle } from './chartTheme'
import { ErrorBox, Loading, Panel, Stat } from './Stat'

interface Props {
  cutoff: string
  basis: Basis
  accuracy: AccuracyResponse | null
  onPickDay: (day: string) => void
}

export function AccuracyView({ cutoff, basis, accuracy, onPickDay }: Props) {
  const horizons = useAsync(() => api.horizons(basis), [basis])
  if (!accuracy) return <Loading />
  const s = accuracy.summary
  const c = accuracy.curtailment
  const bt = accuracy.backtest
  const cost = accuracy.cost
  const saved = cost.forecast && cost.plan ? cost.forecast.net_cost - cost.plan.net_cost : null

  return (
    <div className="stack">
      <section className="findings" aria-label="Key findings">
        <article className="finding">
          <span className="finding__n">
            <Zap size={17} strokeWidth={1.75} aria-hidden />
          </span>
          <h3>The forecast isn’t that bad – it forecasts wind the grid then switches off</h3>
          <p>
            Against delivered wind the forecast ran <b>{signed(c.bias_metered)} MW</b> high on average. On average{' '}
            <b>{mw(c.mean_curtailed)} MW</b> of wind was paid to switch off, which explains <b>{pct(c.explained_pct)}</b> of that
            gap. Against available wind, the bias is just <b>{signed(c.bias_available)} MW</b> (MAE {mw(c.mae_metered)} →{' '}
            {mw(c.mae_available)} MW).
          </p>
          <p className="finding__so">So: plan on forecast <i>minus expected curtailment</i>, not the raw forecast.</p>
        </article>
        <article className="finding">
          <span className="finding__n">
            <PoundSterling size={17} strokeWidth={1.75} aria-hidden />
          </span>
          <h3>What it cost in January</h3>
          <p>
            Buying against the raw forecast left <b>{mw((cost.forecast?.imbalance_mwh ?? 0) / 1000)} GWh</b> to settle at the imbalance
            price, a net cost of <b>{gbp(cost.forecast?.net_cost)}</b> versus buying it ahead. Buying against the plan figure instead
            would have cost <b>{gbp(cost.plan?.net_cost)}</b>
            {saved != null && saved > 0 && (
              <>
                , saving <b>{gbp(saved)}</b>
              </>
            )}
            .
          </p>
          <p className="finding__so">
            Sized as if you bought for all of GB’s metered wind – scale by your share. Model: error × (imbalance − market price) per
            half-hour, delivered wind, D-1 {cutoff} forecasts. Avg prices {gbp(cost.mean_market_price)} market /{' '}
            {gbp(cost.mean_imbalance_price)} imbalance per MWh.
          </p>
        </article>
        <article className="finding">
          <span className="finding__n">
            <ShieldCheck size={17} strokeWidth={1.75} aria-hidden />
          </span>
          <h3>An honest buffer, tested without hindsight</h3>
          <p>
            Each day’s buffer was sized only from the 14 days settled before the decision. The firm figure held in{' '}
            <b>{pct(bt.firm_coverage_pct)}</b> of hours (target 90%) across {bt.days} days. The plan figure cut the typical error from{' '}
            <b>{mw(bt.raw_mae)}</b> to <b>{mw(bt.plan_mae)} MW</b>.
          </p>
          <p className="finding__so">Buffers sized from the same month they’re scored on would look better than they are.</p>
        </article>
      </section>

      <Panel
        title="Over-forecast vs wind switched off, by day"
        icon={Zap}
        subtitle="Bars: how far the forecast ran above delivered wind. Line: wind the grid paid to switch off. Where they match, the forecast was right about the wind – the grid just didn’t take it."
      >
        <div className="chart">
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={c.by_day} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="day" tickFormatter={fmtShortDay} minTickGap={24} {...axisProps} />
              <YAxis width={52} tickFormatter={(v) => mw(v)} {...axisProps} />
              <Tooltip {...tooltipStyle} labelFormatter={(l) => fmtShortDay(String(l))} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="bias" name="Forecast − delivered (bias)" fill={C.shortfall} radius={[3, 3, 0, 0]} isAnimationActive={false}>
                {c.by_day.map((d) => (
                  <Cell key={d.day} fill={d.bias >= 0 ? C.shortfall : C.surplus} fillOpacity={0.75} />
                ))}
              </Bar>
              <Line dataKey="curtailed" name="Wind switched off" stroke={C.actual} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="stats">
        <Stat icon={Activity} label="Typical error (MAE)" value={mw(s.mae)} unit="MW" note={`${s.nmae_pct?.toFixed(1)}% of average wind output`} tone="accent" />
        <Stat icon={TrendingUp} label="Bias" value={signed(s.bias)} unit="MW" note={s.bias != null && s.bias > 0 ? 'forecasts ran high on average' : 'forecasts ran low on average'} />
        <Stat icon={Target} label="90% of periods within" value={`±${mw(s.p90_abs)}`} unit="MW" note={`P99 ±${mw(s.p99_abs)} · worst ${mw(s.max_abs)} MW`} />
        <Stat
          icon={AlertTriangle}
          label="Shortfall to cover (P95)"
          value={mw(s.shortfall_p95)}
          unit="MW"
          note="wind below forecast by more than this only 5% of the time"
          tone="warn"
        />
      </div>

      <div className="callout">
        <Info className="ico" size={18} strokeWidth={1.75} aria-hidden />
        <div>
        <strong>What this means for buying.</strong> Using the forecast available at D-1 {cutoff}, {basis === 'metered' ? 'delivered' : 'available'} wind was typically off by{' '}
        <b>{mw(s.mae)} MW</b> per half-hour. To cover wind shortfall in 9 out of 10 periods, plan for about{' '}
        <b>{mw(s.shortfall_p90)} MW</b> less wind than forecast; the remaining tail is an imbalance or intraday risk. Based on {s.n.toLocaleString()} paired
        periods ({Math.round(s.coverage * 100)}% coverage), R² = {s.r2 ?? '—'}.
        </div>
      </div>

      <Panel
        title="Error grows with lead time"
        icon={TrendingUp}
        subtitle="Accuracy of the latest forecast published at least H hours before each target. The shaded zone is where day-ahead decisions sit."
      >
        {horizons.error ? (
          <ErrorBox message={horizons.error} />
        ) : !horizons.data ? (
          <Loading />
        ) : (
          <div className="chart">
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={horizons.data.rows} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="horizon_h" type="number" domain={[0, 48]} ticks={[0, 6, 12, 18, 24, 30, 36, 42, 48]} unit="h" {...axisProps} />
                <YAxis width={52} tickFormatter={(v) => mw(v)} unit="" {...axisProps} />
                <ReferenceArea x1={15} x2={39} fill={C.band} fillOpacity={0.08} label={{ value: 'day-ahead', position: 'insideTop', fill: C.axis, fontSize: 11 }} />
                <Tooltip {...tooltipStyle} labelFormatter={(l) => `${l} h ahead`} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
                <Legend iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
                <Line dataKey="mae" name="MAE" stroke={C.forecast} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                <Line dataKey="p90_abs" name="P90 absolute error" stroke={C.actual} strokeWidth={1.5} strokeDasharray="5 4" dot={{ r: 2 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>

      <div className="grid-2">
        <Panel icon={BarChart3} title="Error by delivery day" subtitle="Mean absolute error per day. Click a bar to open that day.">
          <div className="chart">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={accuracy.by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="day" tickFormatter={fmtShortDay} minTickGap={24} {...axisProps} />
                <YAxis width={52} tickFormatter={(v) => mw(v)} unit="" {...axisProps} />
                <Tooltip {...tooltipStyle} labelFormatter={(l) => fmtShortDay(String(l))} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
                <Bar dataKey="mae" name="MAE" radius={[3, 3, 0, 0]} cursor="pointer" onClick={(e) => onPickDay(String((e as { day?: string }).day))}>
                  {accuracy.by_day.map((d) => (
                    <Cell key={d.day} fill={s.p90_abs != null && d.mae > s.p90_abs ? C.shortfall : C.forecast} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel icon={Activity} title="Error distribution" subtitle="Forecast − actual, half-hourly. Right of zero = wind fell short.">
          <div className="chart">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={accuracy.histogram} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={1}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis dataKey="from" tickFormatter={(v) => (Number(v) / 1000).toFixed(1)} minTickGap={20} unit=" GW" {...axisProps} />
                <YAxis width={40} unit="%" {...axisProps} />
                <Tooltip
                  {...tooltipStyle}
                  labelFormatter={(_, p) => {
                    const b = p?.[0]?.payload as { from: number; to: number } | undefined
                    return b ? `${signed(b.from)} to ${signed(b.to)} MW` : ''
                  }}
                  formatter={(v) => [`${v}% of periods`, 'Share']}
                />
                <Bar dataKey="pct" isAnimationActive={false}>
                  {accuracy.histogram.map((b) => (
                    <Cell key={b.from} fill={b.from >= 0 ? C.shortfall : C.surplus} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <Panel icon={Clock} title="Error by time of day" subtitle="Where in the day the forecast is least reliable (UK local time).">
        <div className="chart">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={accuracy.by_hour} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, '0')}:00`} {...axisProps} />
              <YAxis width={52} tickFormatter={(v) => mw(v)} unit="" {...axisProps} />
              <Tooltip {...tooltipStyle} labelFormatter={(h) => `${String(h).padStart(2, '0')}:00`} formatter={(v, n) => [`${mw(v as number)} MW`, n]} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="mae" name="MAE" fill={C.forecast} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="p90_abs" name="P90 abs error" fill={C.later} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  )
}

