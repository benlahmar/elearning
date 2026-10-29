import { useEffect, useRef, useState } from 'react'
import { api, type Progress, type Resource } from './api'
import { continuousInterval } from './intervals.mjs'

export function VideoPlayer({ resource, sessionId, initial, onProgress }: { resource: Resource; sessionId: string; initial: Progress; onProgress: (p: Progress) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [status, setStatus] = useState('Collecte active')
  const [mediaError, setMediaError] = useState(false)
  useEffect(() => {
    const v = video.current!
    let sequence = 0, disposed = false, busy = false, failures = 0
    let queue: any[] = []
    let anchor: { position: number; time: number; rate: number } | null = null
    let stable = 0, seekFrom = 0, resuming = false, rate = v.playbackRate
    let initialized = false, renewedAt = 0
    const emit = (event_type: string, payload = {}) => {
      if (queue.length >= 500) { queue.shift(); if (!disposed) setStatus('File pleine : certaines interactions ont été perdues') }
      queue.push({ schema_version: 1, event_id: crypto.randomUUID(), session_id: sessionId, resource_id: resource.id, sequence: ++sequence, event_type, occurred_at: new Date().toISOString(), position_seconds: v.currentTime, payload })
    }
    const reset = () => { anchor = !v.paused && !v.seeking && v.readyState >= 3 ? { position: v.currentTime, time: performance.now(), rate: v.playbackRate } : null }
    const sample = () => {
      if (anchor) {
        const interval = continuousInterval(anchor.position, v.currentTime, (performance.now() - anchor.time) / 1000, anchor.rate)
        if (interval) emit('heartbeat', interval)
      }
      reset()
    }
    const flush = async (keepalive = false) => {
      if (busy || !queue.length) return
      busy = true
      const batch = queue.slice(0, keepalive ? 20 : 100)
      try {
        const response = await api<{ results: { event_id: string; status: string }[] }>('/events/batch', { method: 'POST', body: JSON.stringify({ events: batch }), keepalive })
        const handled = new Set(response.results.map(r => r.event_id))
        queue = queue.filter(e => !handled.has(e.event_id))
        failures = 0
        if (!disposed) {
          setStatus(response.results.some(r => r.status === 'rejected') ? 'Certaines interactions ont été rejetées' : 'Interactions enregistrées')
          const progress = await api<Progress>(`/resources/${resource.id}/progress`)
          if (!disposed) onProgress(progress)
        }
      } catch { failures++; if (!disposed) setStatus('Collecte en attente de connexion') }
      finally { busy = false }
    }
    const loaded = () => {
      if (initialized) return
      initialized = true
      if (initial.position_seconds > 0 && initial.position_seconds < v.duration - 2) {
        resuming = true
        v.currentTime = Math.min(initial.position_seconds, v.duration)
      }
    }
    const play = () => emit('play')
    const playing = () => { emit('playing'); reset() }
    const pause = () => { sample(); anchor = null; emit('pause'); void flush() }
    const waiting = () => { sample(); anchor = null; emit('waiting') }
    const seeking = () => { seekFrom = stable; anchor = null }
    const seeked = () => {
      emit('seek', { from_seconds: seekFrom, to_seconds: v.currentTime, reason: resuming ? 'resume' : 'user' })
      resuming = false; stable = v.currentTime; reset()
    }
    const timeupdate = () => { if (!v.seeking) stable = v.currentTime }
    const ratechange = () => { sample(); emit('rate_change', { from_rate: rate, to_rate: v.playbackRate }); rate = v.playbackRate; reset() }
    const ended = () => { sample(); anchor = null; emit('ended'); void flush() }
    const visibility = () => { sample(); emit('visibility_change', { visible: document.visibilityState === 'visible' }); void flush() }
    const pagehide = () => { sample(); void flush(true) }
    const error = async () => {
      if (!v.src.includes('X-Amz-') || Date.now() - renewedAt < 60000) return
      renewedAt = Date.now()
      const position = v.currentTime, wasPlaying = !v.paused
      try {
        const access = await api<{ url: string }>(`/resources/${resource.id}/access-url`)
        if (disposed) return
        v.addEventListener('loadedmetadata', () => {
          resuming = position > 0
          v.currentTime = position
          if (wasPlaying) void v.play().catch(() => {})
        }, { once: true })
        v.src = access.url
        v.load()
        setMediaError(false)
      } catch { if (!disposed) setMediaError(true) }
    }
    const handlers = { loadedmetadata: loaded, play, playing, pause, waiting, seeking, seeked, timeupdate, ratechange, ended, error }
    for (const [name, handler] of Object.entries(handlers)) v.addEventListener(name, handler)
    document.addEventListener('visibilitychange', visibility)
    window.addEventListener('pagehide', pagehide)
    // Sample frequently; flush separately with bounded exponential retry delay.
    const sampler = window.setInterval(() => { if (!v.paused && !v.seeking) sample() }, 1000)
    let retryAt = 0
    const sender = window.setInterval(() => {
      if (Date.now() >= retryAt) { void flush(); retryAt = Date.now() + Math.min(60000, 10000 * 2 ** Math.min(failures, 3)) }
    }, 1000)
    if (v.readyState >= 1) loaded()
    return () => {
      sample(); disposed = true; void flush(true)
      clearInterval(sampler); clearInterval(sender)
      for (const [name, handler] of Object.entries(handlers)) v.removeEventListener(name, handler)
      document.removeEventListener('visibilitychange', visibility)
      window.removeEventListener('pagehide', pagehide)
    }
  }, [resource.id, sessionId])
  return <>
    <video ref={video} controls preload="metadata" src={resource.url} onError={() => setMediaError(true)} aria-label={resource.title} />
    {mediaError && <p role="alert">Le média externe est indisponible. Réessayez plus tard.</p>}
    <div className="player-tools"><label>Vitesse <select defaultValue="1" onChange={e => { if (video.current) video.current.playbackRate = Number(e.target.value) }}><option value="0.75">0,75×</option><option value="1">1×</option><option value="1.5">1,5×</option><option value="2">2×</option></select></label><span role="status">● {status}</span></div>
  </>
}
