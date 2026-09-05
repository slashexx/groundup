import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { SidecarUnavailable, cadastre } from './cadastreApi'

const CadastreContext = createContext(null)

/**
 * One project document, fetched once and shared by every screen.
 *
 * It is a provider rather than a per-component hook for a specific reason. When each
 * component fetched independently, the shell and the page it framed held *separate*
 * statuses — so a single transient failure produced a window where the nav badge showed
 * live counts while the page beside it said the sidecar was not running. Two parts of
 * the same screen disagreeing about whether the data is real is worse than either answer
 * on its own, and no amount of retry logic fixes it while the states are independent.
 *
 * It also stops the app refetching the whole project on every navigation.
 */
export function CadastreProvider({ children }) {
  const [doc, setDoc] = useState(null)
  const [status, setStatus] = useState('loading')   // loading | live | offline | error
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setStatus('loading')
    setError(null)
    try {
      const d = await cadastre.document()
      setDoc(d)
      setStatus('live')
    } catch (e) {
      setDoc(null)
      if (e instanceof SidecarUnavailable) {
        setStatus('offline')
      } else {
        setStatus('error')
        setError(e.message)
      }
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const value = useMemo(
    () => ({ doc, live: status === 'live', status, error, reload: load }),
    [doc, status, error, load],
  )
  return <CadastreContext.Provider value={value}>{children}</CadastreContext.Provider>
}

/**
 * The shared project document.
 *
 * `live` is the flag every screen uses to decide whether it is showing the real project
 * or nothing at all — it must be surfaced, not swallowed. A reviewer looking at invented
 * numbers believing they are the project is the failure mode this exists to prevent,
 * which is why there is no longer any sample data for a screen to fall back to.
 */
export function useCadastreDocument() {
  const ctx = useContext(CadastreContext)
  if (!ctx) {
    throw new Error(
      'useCadastreDocument() outside <CadastreProvider>. Wrap the app in App.jsx — the ' +
      'document is shared deliberately so the shell and the page cannot disagree about ' +
      'whether the data is real.')
  }
  return ctx
}

/**
 * The banner every wired screen shows above its content.
 *
 * Deliberately not silent when offline: the alternative is a dashboard that looks
 * authoritative and is not.
 */
export function DataSourceBanner({ status, error, onRetry }) {
  if (status === 'live') return null

  const message =
    status === 'loading'
      ? 'Connecting to the cadastre sidecar…'
      : status === 'offline'
        ? 'Cadastre sidecar not running — this screen has no data to show. ' +
          'Start it with: python -m uvicorn cadastre.app:app --app-dir sidecar --port 8000'
        : `Cadastre sidecar returned an error: ${error}`

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '8px 24px',
        fontSize: 'var(--text-sm)',
        color: status === 'error' ? 'var(--text-primary)' : 'var(--text-tertiary)',
        background: status === 'error' ? 'var(--error-bg, #3a1f1f)' : 'var(--bg-tertiary, #23262b)',
        borderBottom: '1px solid var(--border-primary)',
      }}
    >
      <span style={{ flex: 1 }}>{message}</span>
      {status !== 'loading' && (
        <button className="btn btn-ghost btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

/**
 * What a screen shows when the project genuinely holds nothing for it yet.
 *
 * Not a spinner and not a zero: both read as "checked, and there is nothing", which is a
 * different claim from "nothing has been run". A fresh project has no findings because
 * validation has not happened, and a screen reporting "0 errors" would be stating a
 * clean bill of health it has no basis for.
 */
export function NothingYet({ title, children }) {
  return (
    <div className="upload-dropzone" style={{ cursor: 'default' }}>
      <div className="upload-dropzone-title">{title}</div>
      <div className="upload-dropzone-subtitle">{children}</div>
    </div>
  )
}
