// One palette for every chart so the app reads as a single system.
// Tuned for the light glass theme: dark strokes on frosted white panels.
export const C = {
  actual: '#0f172a',
  forecast: '#0d9488',
  band: '#14b8a6',
  later: '#94a3b8',
  shortfall: '#ea7a3c',
  surplus: '#3b82f6',
  grid: 'rgba(15,23,42,0.08)',
  axis: '#5b6474',
}

export const axisProps = {
  stroke: C.axis,
  tick: { fill: C.axis, fontSize: 11, fontFamily: 'IBM Plex Mono, monospace' },
  tickLine: false,
  axisLine: { stroke: C.grid },
}

export const tooltipStyle = {
  contentStyle: {
    borderRadius: 12,
    background: 'rgba(255,255,255,0.92)',
    border: '1px solid rgba(15,23,42,0.08)',
    boxShadow: '0 10px 30px rgba(15,23,42,.1)',
    backdropFilter: 'blur(12px)',
    fontSize: 12,
    fontFamily: 'Inter Tight, sans-serif',
  },
  labelStyle: { fontWeight: 600, color: '#0f172a', marginBottom: 4 },
  itemStyle: { color: '#334155' },
  cursor: { stroke: 'rgba(15,23,42,0.2)', fill: 'rgba(15,23,42,0.04)' },
}
