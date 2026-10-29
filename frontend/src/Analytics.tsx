import { useEffect, useState } from 'react'
import { api } from './api'
import './analytics.css'

type Video = { resource_id: string; title: string; archived: boolean; opens: number; learners: number; average_coverage: number; completion_rate: number; replayed_seconds: number; backward_seeks: number; forward_seeks: number }
type Quality = { accepted: number; duplicate: number; rejected: number; duplicate_sequences: number; clock_skew_events: number; retained_events: number }
type Overview = { from: string; to: string; videos: Video[]; quality: Quality }
type Learner = { participant: string; events: number; sessions: number; resources: number; last_activity: string }
type Segment = { start: number; end: number; viewed_learners: number; replayed_learners: number; skipped_learners: number }
type Map = { title: string; bin_seconds: number; bins: Segment[] }
type Detail = { participant: string; resources: { resource_id: string; title: string; kind: string; coverage: number; sessions: number; resume_seeks: number; backward_seeks: number; replayed_seconds: number }[]; history: { type: string; resource_id: string; position_seconds: number; received_at: string }[]; history_truncated: boolean }
type Policy = { retention_days: number; enabled: boolean }
type Participant = { id: string; email: string; participant: string; bootstrap: boolean }
type Preview = { cutoff: string; counts: Record<string, number> }
const percent = (value: number) => `${Math.round(value * 100)} %`
const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
const date = (value: string) => new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z').toLocaleString('fr-FR')

export function Analytics() {
  const [days, setDays] = useState(30), [revision, setRevision] = useState(0)
  const [overview, setOverview] = useState<Overview | null>(null), [learners, setLearners] = useState<Learner[]>([])
  const [videoId, setVideoId] = useState(''), [map, setMap] = useState<Map | null>(null)
  const [mode, setMode] = useState<'viewed_learners' | 'replayed_learners' | 'skipped_learners'>('viewed_learners')
  const [segment, setSegment] = useState<Segment | null>(null)
  const [participant, setParticipant] = useState(''), [detail, setDetail] = useState<Detail | null>(null)
  const [settings, setSettings] = useState<Policy>({ retention_days: 90, enabled: false })
  const [participants, setParticipants] = useState<Participant[]>([]), [deleteId, setDeleteId] = useState('')
  const [confirmed, setConfirmed] = useState(false), [purgeConfirmed, setPurgeConfirmed] = useState(false)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true)
  const [policyReady, setPolicyReady] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true); setPolicyReady(false); setOverview(null); setError(''); setPreview(null); setPurgeConfirmed(false)
    Promise.all([api<Overview>(`/admin/analytics?days=${days}`), api<Learner[]>(`/admin/analytics/learners?days=${days}`), api<Policy>('/admin/data-policy'), api<Participant[]>('/admin/participants')]).then(([o, l, p, participants]) => {
      if (!active) return
      setOverview(o); setLearners(l); setSettings(p); setPolicyReady(true); setParticipants(participants)
      setVideoId(previous => o.videos.some(v => v.resource_id === previous) ? previous : o.videos[0]?.resource_id || '')
      setParticipant(previous => l.some(row => row.participant === previous) ? previous : '')
    }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [days, revision])
  useEffect(() => {
    let active = true
    setMap(null); setSegment(null)
    if (videoId) api<Map>(`/admin/analytics/videos/${videoId}?days=${days}`).then(data => { if (active) setMap(data) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [videoId, days, revision])
  useEffect(() => {
    let active = true
    setDetail(null)
    if (participant) api<Detail>(`/admin/analytics/learners/${participant}?days=${days}`).then(data => { if (active) setDetail(data) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [participant, days, revision])

  async function action(work: () => Promise<void>) {
    setError(''); setNotice(''); setBusy(true)
    try { await work() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function download() {
    const data = await api(`/admin/exports?days=${days}`)
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a'); link.href = url; link.download = `learning-interactions-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    setNotice(`${data.events.length} événements exportés. Identifiants pseudonymisés ; aucune adresse e-mail incluse.`)
  }
  const selectedVideo = overview?.videos.find(v => v.resource_id === videoId)
  const max = Math.max(1, ...(map?.bins.map(b => b[mode]) || []))
  return <section className="analytics"><div className="section-heading"><div><span className="eyebrow">OBSERVER LES PARCOURS</span><h1>Les interactions, en perspective.</h1><p className="muted">Des comportements observés. Leur sens pédagogique reste à explorer.</p></div><div className="analytics-controls"><label>Période<select value={days} onChange={e => setDays(Number(e.target.value))}>{[1, 7, 30, 90, 365, 3650].map(d => <option value={d} key={d}>{d} derniers jours</option>)}</select></label><button className="secondary" onClick={() => setRevision(r => r + 1)} disabled={busy || loading}>Actualiser</button><button className="primary" onClick={() => void action(download)} disabled={busy || loading}>Exporter JSON ↓</button></div></div>
    {error && <p className="alert" role="alert">{error}</p>}{notice && <p className="analytics-notice" role="status">{notice}</p>}{loading && <p role="status">Calcul des indicateurs…</p>}
    {overview && <><div className="stats"><article><span>OUVERTURES VIDÉO</span><strong>{overview.videos.reduce((n, v) => n + v.opens, 0)}</strong><small>Sessions de consultation</small></article><article><span>PARTICIPANTS ACTIFS</span><strong>{learners.length}</strong><small>Avec des événements sur la période</small></article><article><span>ÉVÉNEMENTS CONSERVÉS</span><strong>{overview.quality.retained_events}</strong><small>Après déduplication et rétention</small></article><article><span>LOTS · ÉVÉNEMENTS REJETÉS</span><strong>{overview.quality.rejected}</strong><small>Depuis la version 0.3</small></article></div>
    <section className="detail"><h2>Les vidéos</h2><p className="muted small">Couverture : portions distinctes vues par participant. Complétion : couverture ≥ 90 %. Calculs limités à la période sélectionnée, sur la date de réception serveur.</p><div className="analytics-table"><table><thead><tr><th>Vidéo</th><th>Ouvertures</th><th>Participants</th><th>Couverture moyenne</th><th>Complétion</th><th>Retours / avances</th></tr></thead><tbody>{overview.videos.map(v => <tr key={v.resource_id}><td><button className="text-button" aria-pressed={videoId === v.resource_id} onClick={() => setVideoId(v.resource_id)}>{v.title}{v.archived ? ' · Archivée' : ''}</button></td><td>{v.opens}</td><td>{v.learners}</td><td>{v.learners ? percent(v.average_coverage) : '—'}</td><td>{v.learners ? percent(v.completion_rate) : '—'}</td><td>{v.backward_seeks} / {v.forward_seeks}</td></tr>)}</tbody></table></div>{!overview.videos.length && <p>Aucune vidéo à analyser.</p>}</section>
    <section className="detail"><div className="section-heading"><div><h2>Carte des passages</h2><p className="muted small">{selectedVideo?.title || 'Choisissez une vidéo'}</p></div><label>Afficher<select value={mode} onChange={e => setMode(e.target.value as typeof mode)}><option value="viewed_learners">Participants ayant visionné</option><option value="replayed_learners">Participants ayant revu</option><option value="skipped_learners">Participants ayant sauté</option></select></label></div>
    {map && <><div className="heatmap" aria-label="Segments de la vidéo dans l’ordre chronologique">{map.bins.map(b => <button key={b.start} className={segment?.start === b.start ? 'selected' : ''} style={{ backgroundColor: `rgba(38, 105, 76, ${.07 + .9 * b[mode] / max})`, color: b[mode] / max > .5 ? 'white' : '#183b35' }} title={`${clock(b.start)}–${clock(b.end)} : ${b[mode]} participants`} aria-label={`${clock(b.start)} à ${clock(b.end)}, ${b[mode]} participants`} onFocus={() => setSegment(b)} onMouseEnter={() => setSegment(b)} onClick={() => setSegment(b)}>{b[mode]}</button>)}</div><p className="small">Segments de {map.bin_seconds} secondes · du début vers la fin · plus foncé = plus de participants.</p>{segment && <p className="analytics-notice" role="status">{clock(segment.start)} → {clock(segment.end)} : {segment.viewed_learners} ont visionné · {segment.replayed_learners} ont revu · {segment.skipped_learners} ont sauté.</p>}<p className="muted small">Un segment peut être sauté, puis regardé. Les catégories peuvent se recouper ; une répétition ne prouve pas une difficulté.</p></>}
    </section>
    <section className="detail"><h2>Par participant</h2><label>Parcours<select value={participant} onChange={e => setParticipant(e.target.value)}><option value="">Choisir un participant</option>{learners.map(l => <option value={l.participant} key={l.participant}>{l.participant} · {l.sessions} sessions · {l.events} événements</option>)}</select></label>{!learners.length && <p>Aucune interaction sur cette période.</p>}
    {detail && <><div className="analytics-table"><table><thead><tr><th>Ressource</th><th>Sessions</th><th>Couverture</th><th>Secondes revues</th><th>Reprises automatiques</th><th>Retours</th></tr></thead><tbody>{detail.resources.map(r => <tr key={r.resource_id}><td>{r.title}</td><td>{r.sessions}</td><td>{r.kind === 'video' ? percent(r.coverage) : 'Document'}</td><td>{Math.round(r.replayed_seconds)}</td><td>{r.resume_seeks}</td><td>{r.backward_seeks}</td></tr>)}</tbody></table></div><details><summary>Historique des événements{detail.history_truncated ? ' · 200 derniers événements' : ''}</summary><ol className="event-history">{detail.history.map((e, i) => <li key={i}><time>{date(e.received_at)}</time><span>{e.type}</span><span>{clock(e.position_seconds)}</span></li>)}</ol></details></>}
    </section>
    <section className="detail"><h2>Qualité de collecte</h2><div className="quality-grid">{([['Acceptés dans les lots', 'accepted'], ['Doublons reçus et ignorés', 'duplicate'], ['Rejetés dans les lots', 'rejected'], ['Numéros de séquence répétés', 'duplicate_sequences'], ['Écart d’horloge supérieur à 5 min', 'clock_skew_events']] as const).map(([label, key]) => <div key={key}><span>{label}</span><strong>{overview.quality[key]}</strong></div>)}</div><p className="muted small">Les compteurs de lots commencent en version 0.3. Les requêtes HTTP refusées avant ingestion (401, 413, 422) et les événements jamais transmis par le navigateur ne sont pas comptés. Les écarts d’horloge sont des indices de qualité.</p></section>
    </>}
    <section className="detail"><h2>Conservation et suppression</h2><p className="muted small">La rétention concerne événements, diagnostics de lots et avis. Elle affecte aussi les indicateurs recalculés. Les comptes restent présents jusqu’à leur suppression explicite.</p><form className="policy-form" onSubmit={e => { e.preventDefault(); void action(async () => { await api('/admin/data-policy', { method: 'PUT', body: JSON.stringify(settings) }); setPreview(null); setPurgeConfirmed(false); setNotice('Politique enregistrée. Si activée, vérification au démarrage puis toutes les heures.') }) }}><label>Durée en jours<input type="number" min="1" max="3650" required value={settings.retention_days} onChange={e => { setSettings({ ...settings, retention_days: Number(e.target.value) }); setPreview(null); setPurgeConfirmed(false) }}/></label><label><input type="checkbox" checked={settings.enabled} onChange={e => setSettings({ ...settings, enabled: e.target.checked })}/> Activer la purge automatique</label><button className="secondary" disabled={busy || loading || !policyReady}>Enregistrer la politique</button></form>
    <button className="text-button" disabled={busy || loading || !policyReady} onClick={() => void action(async () => { setPreview(await api('/admin/data-policy/preview')); setPurgeConfirmed(false) })}>Prévisualiser la purge selon la politique enregistrée →</button>
    {preview && <div className="purge-preview"><p>Données antérieures au {date(preview.cutoff)} :</p><ul>{Object.entries(preview.counts).map(([key, value]) => <li key={key}>{key} : {value}</li>)}</ul><label><input type="checkbox" checked={purgeConfirmed} onChange={e => setPurgeConfirmed(e.target.checked)}/> Supprimer les données éligibles à cette politique</label><button className="danger" disabled={!purgeConfirmed || busy} onClick={() => void action(async () => { const result = await api<Preview>('/admin/data-policy/purge', { method: 'POST' }); setNotice(`${Object.values(result.counts).reduce((a, b) => a + b, 0)} lignes supprimées.`); setPurgeConfirmed(false); setRevision(r => r + 1) })}>Exécuter la purge maintenant</button></div>}
    <hr/><h3>Supprimer un compte apprenant et ses données</h3><p className="muted small">Supprime le compte, le profil, les événements, avis et sessions. Les exports déjà téléchargés et les sauvegardes doivent être gérés séparément.</p><label>Compte<select value={deleteId} onChange={e => { setDeleteId(e.target.value); setConfirmed(false) }}><option value="">Choisir un apprenant</option>{participants.map(p => <option key={p.id} value={p.id} disabled={p.bootstrap}>{p.email} · {p.participant}{p.bootstrap ? ' · compte de démonstration configuré' : ''}</option>)}</select></label><label className="delete-confirm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/> Je confirme la suppression du compte sélectionné et de ses données.</label><button className="danger" disabled={!deleteId || !confirmed || busy} onClick={() => void action(async () => { await api(`/admin/participants/${deleteId}`, { method: 'DELETE' }); setDeleteId(''); setConfirmed(false); setNotice('Compte et données supprimés ; sessions révoquées.'); setRevision(r => r + 1) })}>Supprimer définitivement</button>
    </section>
    <p className="privacy">Les exports sont pseudonymisés, et restent des données personnelles. Ils n’incluent ni e-mail, ni mot de passe, ni URL de fichier. Ils contiennent au maximum 50 000 événements par téléchargement ; réduire la période si nécessaire.</p>
  </section>
}
