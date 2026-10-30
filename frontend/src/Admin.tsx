import { useEffect, useState } from 'react'
import { api } from './api'
import './admin.css'
import { Analytics } from './Analytics'
import { Algorithms } from './Algorithms'

type Course = { id: string; title: string; description: string; archived: boolean }
type Resource = { id: string; title: string; description: string; topic: string; level: string; kind: string; duration: number; tags: string[]; course_id: string; archived: boolean; ready: boolean }
const emptyResource = { title: '', description: '', topic: '', level: 'Débutant', kind: 'video', duration: 0, tags: [], course_id: '', archived: false } as Omit<Resource, 'id' | 'ready'>

export function Admin({ onChange }: { onChange: () => void }) {
  const [view, setView] = useState('content')
  const [courses, setCourses] = useState<Course[]>([]), [resources, setResources] = useState<Resource[]>([])
  const [course, setCourse] = useState({ id: '', title: '', description: '', archived: false })
  const [resource, setResource] = useState({ ...emptyResource, id: '', ready: false })
  const [file, setFile] = useState<File | null>(null), [tags, setTags] = useState('')
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [error, setError] = useState('')
  async function reload() { const [c, r] = await Promise.all([api<Course[]>('/admin/courses'), api<Resource[]>('/admin/resources')]); setCourses(c); setResources(r); onChange() }
  useEffect(() => { void reload().catch(e => setError(e.message)) }, [])
  async function run(action: () => Promise<void>) { setBusy(true); setError(''); setMessage(''); try { await action(); await reload() } catch (e) { setError((e as Error).message) } finally { setBusy(false) } }
  async function selectFile(next: File | null) {
    setFile(next)
    if (!next || resource.kind !== 'video') return
    const url = URL.createObjectURL(next), video = document.createElement('video')
    video.preload = 'metadata'
    video.onloadedmetadata = () => { if (Number.isFinite(video.duration)) setResource(r => ({ ...r, duration: video.duration })); URL.revokeObjectURL(url) }
    video.onerror = () => { URL.revokeObjectURL(url); setError('Vidéo illisible : choisissez un MP4 compatible avec le navigateur') }
    video.src = url
  }
  const menu = <nav className="admin-tabs" aria-label="Administration">{[['content', 'Contenus et comptes'], ['analytics', 'Interactions'], ['algorithms', 'Algorithmes']].map(([id, label]) => <button key={id} aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>)}</nav>
  if (view === 'analytics') return <>{menu}<Analytics /></>
  if (view === 'algorithms') return <>{menu}<Algorithms /></>
  return <section className="admin">{menu}<span className="eyebrow">GESTION DES CONTENUS</span><h1>Administration</h1>{error && <p role="alert" className="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <div className="admin-grid"><section className="detail"><h2>{course.id ? 'Modifier le cours' : 'Créer un cours'}</h2><form onSubmit={e => { e.preventDefault(); void run(async () => { await api('/admin/courses' + (course.id ? '/' + course.id : ''), { method: course.id ? 'PUT' : 'POST', body: JSON.stringify(course) }); setCourse({ id: '', title: '', description: '', archived: false }); setMessage('Cours enregistré') }) }}>
      <label>Titre<input required maxLength={200} value={course.title} onChange={e => setCourse({ ...course, title: e.target.value })}/></label><label>Description<textarea value={course.description} onChange={e => setCourse({ ...course, description: e.target.value })}/></label>
      <label><input type="checkbox" checked={course.archived} onChange={e => setCourse({ ...course, archived: e.target.checked })}/> Archiver le cours et masquer ses ressources</label><button className="primary" disabled={busy}>Enregistrer le cours</button><button type="button" className="text-button" onClick={() => setCourse({ id: '', title: '', description: '', archived: false })}>Nouveau cours</button>
    </form><h3>Cours existants</h3>{courses.map(c => <button className="admin-row" key={c.id} onClick={() => setCourse(c)}>{c.title} {c.archived ? '· Archivé' : ''} <span>Modifier →</span></button>)}</section>
    <section className="detail"><h2>{resource.id ? 'Modifier la ressource' : 'Importer une ressource'}</h2><form onSubmit={e => { e.preventDefault(); void run(async () => {
      let saved = await api<Resource>('/admin/resources' + (resource.id ? '/' + resource.id : ''), { method: resource.id ? 'PUT' : 'POST', body: JSON.stringify({ ...resource, tags: tags.split(',').map(t => t.trim()).filter(Boolean), duration: resource.kind === 'file' ? 0 : resource.duration }) })
      setResource(saved)
      if (file && !saved.ready) saved = await api<Resource>(`/admin/resources/${saved.id}/content`, { method: 'PUT', body: file, headers: { 'Content-Type': saved.kind === 'video' ? 'video/mp4' : 'application/pdf' } })
      setResource(saved); setFile(null); setMessage(saved.ready ? 'Ressource enregistrée et disponible dans le catalogue' : 'Brouillon enregistré : importez le fichier pour le publier')
    }) }}>
      <label>Cours<select required value={resource.course_id || ''} onChange={e => setResource({ ...resource, course_id: e.target.value })}><option value="">Choisir un cours</option>{courses.map(c => <option key={c.id} value={c.id}>{c.title}{c.archived ? ' (archivé)' : ''}</option>)}</select></label>
      <label>Titre<input required maxLength={200} value={resource.title} onChange={e => setResource({ ...resource, title: e.target.value })}/></label><label>Description<textarea value={resource.description} onChange={e => setResource({ ...resource, description: e.target.value })}/></label>
      <label>Thème<input required value={resource.topic} onChange={e => setResource({ ...resource, topic: e.target.value })}/></label><label>Niveau<select value={resource.level} onChange={e => setResource({ ...resource, level: e.target.value })}><option>Débutant</option><option>Intermédiaire</option><option>Avancé</option></select></label>
      <label>Format<select disabled={resource.ready} value={resource.kind} onChange={e => { setResource({ ...resource, kind: e.target.value, duration: 0 }); setFile(null) }}><option value="video">Vidéo MP4</option><option value="file">Document PDF</option></select></label>
      {resource.kind === 'video' && <label>Durée en secondes<input required type="number" min="0.01" step="any" disabled={resource.ready} value={resource.duration} onChange={e => setResource({ ...resource, duration: Number(e.target.value) })}/></label>}
      <label>Mots-clés séparés par des virgules<input value={tags} onChange={e => setTags(e.target.value)}/></label>
      {!resource.ready && <label>Fichier · 200 Mo maximum<input key={resource.id + resource.kind} type="file" accept={resource.kind === 'video' ? '.mp4,video/mp4' : '.pdf,application/pdf'} onChange={e => void selectFile(e.target.files?.[0] || null)}/></label>}
      <label><input type="checkbox" checked={resource.archived} onChange={e => setResource({ ...resource, archived: e.target.checked })}/> Archiver cette ressource</label><button className="primary" disabled={busy}>{busy ? 'Enregistrement / import…' : 'Enregistrer la ressource'}</button><button type="button" className="text-button" onClick={() => { setResource({ ...emptyResource, id: '', ready: false }); setTags(''); setFile(null) }}>Nouvelle ressource</button>
    </form></section></div>
    <section className="detail"><h2>Ressources</h2>{resources.map(r => <button key={r.id} className="admin-row" onClick={() => { setResource(r); setTags(r.tags.join(', ')); setFile(null) }}>{r.title} · {r.archived ? 'Archivée' : r.ready ? 'Disponible' : 'Brouillon'}<span>Modifier →</span></button>)}</section>
    <section className="detail"><h2>Créer un compte apprenant</h2><form onSubmit={e => { e.preventDefault(); const form = e.currentTarget, data = new FormData(form); void run(async () => { await api('/admin/learners', { method: 'POST', body: JSON.stringify(Object.fromEntries(data)) }); form.reset(); setMessage('Compte apprenant créé. Transmettez les identifiants au participant.') }) }}><label>E-mail<input name="email" type="email" required autoComplete="off"/></label><label>Mot de passe initial (12 caractères minimum)<input name="password" type="password" required minLength={12} autoComplete="new-password"/></label><button className="primary" disabled={busy}>Créer le compte</button></form></section>
  </section>
}
