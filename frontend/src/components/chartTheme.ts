// One palette for every chart so the app reads as a single system.
export const C = {
  actual: '#0f172a',
  forecast: '#0d9488',
  band: '#14b8a6',
  later: '#94a3b8',
  shortfall: '#dc6b2f',
  surplus: '#3b82f6',
  grid: '#e5e7eb',
  axis: '#64748b',
}

export const axisProps = {
  stroke: C.axis,
  tick: { fill: C.axis, fontSize: 11, fontFamily: 'IBM Plex Mono, monospace' },
  tickLine: false,
  axisLine: { stroke: C.grid },
}

export const tooltipStyle = {
  contentStyle: {
    borderRadius: 8,
    border: '1px solid #e2e8f0',
    boxShadow: '0 6px 20px rgba(15,23,42,.08)',
    fontSize: 12,
    fontFamily: 'Inter Tight, sans-serif',
  },
  labelStyle: { fontWeight: 600, color: '#0f172a', marginBottom: 4 },
}
