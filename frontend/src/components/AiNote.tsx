import { Info, RefreshCw, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { api, type AiNote as Note, type Basis, type NoteMode } from '../api'
import { useAsync } from '../hooks'

interface Props {
  date: string
  cutoff: string
  basis: Basis
}

const MODES: { value: NoteMode; label: string; hint: string }[] = [
  { value: 'brief', label: 'Before decision', hint: 'Only what the desk knew at the cutoff – no hindsight.' },
  { value: 'review', label: 'After delivery', hint: 'Looks back at what actually happened on the day.' },
]

/** Gemini-written desk note. Generated on request (saves quota) and grounded in the app's own figures. */
export function AiNote({ date, cutoff, basis }: Props) {
  const status = useAsync(() => api.aiStatus(), [])
  const [mode, setMode] = useState<NoteMode>('brief')
  // Each result remembers what it was written for; a different day, cutoff, basis or mode makes it stale.
  const key = `${date}|${cutoff}|${basis}|${mode}`
  const [result, setResult] = useState<{ key: string; note?: Note; error?: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const note = result?.key === key ? result.note : undefined
  const error = result?.key === key ? result.error : undefined

  if (!status.data) return null
  const generate = async () => {
    setLoading(true)
    try {
      setResult({ key, note: await api.aiNote(date, cutoff, basis, mode) })
    } catch (e) {
      setResult({ key, error: String(e) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="ainote glass" aria-label="AI desk note">
      <div className="ainote__head">
        <span className="ainote__title">
          <Sparkles className="ico" size={18} strokeWidth={1.75} aria-hidden />
          AI desk note
        </span>
        <div className="seg" role="tablist" aria-label="Note type">
          {MODES.map((m) => (
            <button key={m.value} role="tab" aria-selected={mode === m.value} className={mode === m.value ? 'on' : ''} onClick={() => setMode(m.value)}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {!status.data.enabled ? (
        <p className="ainote__muted">
          <Info size={14} strokeWidth={1.75} aria-hidden /> AI notes are off. Set <code>GEMINI_API_KEY</code> on the server to turn on
          Gemini-written briefs.
        </p>
      ) : note ? (
        <div className="ainote__body" aria-live="polite">
          <h3>{note.headline}</h3>
          <ul>
            {note.points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
          <p className="ainote__action">{note.action}</p>
          <div className="ainote__foot">
            <span>
              Written by {note.model} from the figures below only. {MODES.find((m) => m.value === note.mode)!.hint}
            </span>
            <button className="ainote__btn ainote__btn--ghost" onClick={generate} disabled={loading}>
              <RefreshCw size={14} strokeWidth={1.75} aria-hidden /> Regenerate
            </button>
          </div>
          <details className="ainote__facts">
            <summary>Facts given to the AI</summary>
            <pre>{JSON.stringify(note.facts, null, 2)}</pre>
          </details>
        </div>
      ) : (
        <div className="ainote__empty">
          <p className="ainote__muted">{MODES.find((m) => m.value === mode)!.hint}</p>
          <button className="ainote__btn" onClick={generate} disabled={loading}>
            <Sparkles size={15} strokeWidth={1.75} aria-hidden />
            {loading ? 'Writing…' : 'Write note with Gemini'}
          </button>
        </div>
      )}
      {error && <p className="ainote__err">Couldn’t write the note. {error}</p>}
    </section>
  )
}
