import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, setToken, type Progress, type Resource } from './api'
import { VideoPlayer } from './VideoPlayer'
import './style.css'

type User = { email: string; interests: string[] }
type Selection = { resource: Resource; sessionId: string; progress: Progress; feedback: { favorite: boolean; useful: boolean | null } }

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [items, setItems] = useState<Resource[]>([])
  const [recommendations, setRecommendations] = useState<Resource[]>([])
  const [algorithm, setAlgorithm] = useState('content')
  const [q, setQ] = useState(''), [kind, setKind] = useState('')
  const [selection, setSelection] = useState<Selection | null>(null)
  const [interests, setInterests] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!user) return
    let active = true
    api<Resource[]>(`/resources?q=${encodeURIComponent(q)}&kind=${kind}`).then(data => { if (active) setItems(data) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [user, q, kind])
  useEffect(() => {
    if (!user) return
    let active = true
    api(`/recommendations?algorithm=${algorithm}`).then(data => { if (active) setRecommendations(data.items) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [user, algorithm])

  async function login(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const data = new FormData(event.currentTarget)
    try {
      const auth = await api('/auth/login', { method: 'POST', body: JSON.stringify(Object.fromEntries(data)) })
      setToken(auth.access_token)
      const me = await api<User>('/me'); setUser(me); setInterests(me.interests.join(', '))
    } catch (e) { setToken(''); setError((e as Error).message) }
    finally { setBusy(false) }
  }
  async function open(resource: Resource) {
    setError(''); setBusy(true)
    try {
      const [session, progress, feedback] = await Promise.all([api(`/resources/${resource.id}/sessions`, { method: 'POST' }), api<Progress>(`/resources/${resource.id}/progress`), api(`/resources/${resource.id}/feedback`)])
      setSelection({ resource, sessionId: session.session_id, progress, feedback })
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }
  async function feedback(value: Selection['feedback']) {
    if (!selection) return
    try {
      await api(`/resources/${selection.resource.id}/feedback`, { method: 'PUT', body: JSON.stringify(value) })
      setSelection(previous => previous ? { ...previous, feedback: value } : previous)
    } catch (e) { setError((e as Error).message) }
  }
  async function logout() {
    try { await api('/auth/logout', { method: 'POST' }); setSelection(null); setToken(''); setUser(null); setItems([]); setRecommendations([]); setError('') }
    catch (e) { setError((e as Error).message) }
  }
  const card = (r: Resource) => <button className="resource-card" key={r.id} onClick={() => void open(r)} disabled={busy}>
    <div className={`cover ${r.kind}`}><span>{r.kind === 'video' ? '▶' : '↗'}</span><small>{r.kind === 'video' ? `${Math.round(r.duration / 60)} min` : 'PDF'}</small></div>
    <div className="card-body"><span className="eyebrow">{r.topic}</span><h3>{r.title}</h3><p>{r.description}</p><footer>{r.level}<span>{r.kind === 'video' ? 'Vidéo' : 'Document'}</span></footer></div>
  </button>

  return <div className="app"><aside><a href="/" className="brand"><span>l.</span>learning lab</a><p className="nav-label">VOTRE ESPACE</p><a href="#catalogue" className="nav-item">▦ &nbsp; Explorer</a><div className="aside-note"><span>LE LABORATOIRE</span><p>Apprendre.<br/>Observer.<br/>Expérimenter.</p><small>Un terrain d’exploration des systèmes de recommandation.</small></div><small className="version">PILOTE · VERSION 0.1</small></aside>
    <main><header><span>Espace d’apprentissage <span className="muted">/ Explorer</span></span>{user && <button className="text-button" onClick={() => void logout()}>Déconnexion</button>}</header>
      {error && <div role="alert" className="alert">{error} <button onClick={() => setError('')} aria-label="Fermer l’erreur">×</button></div>}
      {!user ? <section className="login"><span className="eyebrow">BIENVENUE AU LAB</span><h1>Votre prochaine<br/>découverte commence ici.</h1><p>Connectez-vous pour explorer les ressources et retrouver votre progression.</p><form onSubmit={login}><label>Adresse e-mail<input name="email" type="email" autoComplete="username" required /></label><label>Mot de passe<input name="password" type="password" autoComplete="current-password" required /></label><button className="primary" disabled={busy}>{busy ? 'Connexion…' : 'Entrer dans le laboratoire →'}</button></form><p className="privacy">Pilote pédagogique : les actions de lecture, pauses, déplacements et portions visionnées sont enregistrés pour expérimenter les recommandations. Ils ne mesurent pas votre compréhension. Les identifiants du pilote sont fournis par votre enseignant.</p></section> : <>
      <section className="hero"><span className="eyebrow">LA CURIOSITÉ COMME POINT DE DÉPART</span><h1>Un peu plus loin,<br/><em>à chaque découverte.</em></h1><p>Explorez les ressources, avancez à votre rythme et construisez votre parcours.</p><div className="hero-badge">↗<span>VOTRE PARCOURS<br/><strong>À vous de l’explorer</strong></span></div></section>
      <section className="profile"><div><h2>Vos centres d’intérêt</h2><p>Quelques mots pour orienter vos recommandations.</p></div><form onSubmit={async e => { e.preventDefault(); setError(''); setNotice(''); try { const result = await api('/me/profile', { method: 'PATCH', body: JSON.stringify({ interests: interests.split(',').map(s => s.trim()).filter(Boolean) }) }); setUser({ ...user, interests: result.interests }); setNotice('Centres d’intérêt enregistrés') } catch (e) { setError((e as Error).message) } }}><input aria-label="Centres d’intérêt séparés par des virgules" placeholder="vidéo, recommandation, évaluation…" value={interests} onChange={e => setInterests(e.target.value)}/><button className="secondary">Enregistrer</button></form>{notice && <small role="status">{notice}</small>}</section>
      {selection && <section className="detail"><button className="text-button" onClick={() => setSelection(null)}>← Fermer la ressource</button><h2>{selection.resource.title}</h2><p>{selection.resource.description}</p>{selection.resource.kind === 'video' ? <VideoPlayer key={selection.sessionId} resource={selection.resource} sessionId={selection.sessionId} initial={selection.progress} onProgress={progress => setSelection(previous => previous?.sessionId === selection.sessionId ? { ...previous, progress } : previous)} /> : <a className="primary file-link" href={selection.resource.url} target="_blank" rel="noreferrer" onClick={() => { void api('/events/batch', { method: 'POST', body: JSON.stringify({ events: [{ schema_version: 1, event_id: crypto.randomUUID(), session_id: selection.sessionId, sequence: 1, resource_id: selection.resource.id, event_type: 'resource_download', occurred_at: new Date().toISOString(), position_seconds: 0, payload: {} }] }) }).catch(e => setError(e.message)) }}>Ouvrir le document ↗</a>}
      {selection.resource.kind === 'video' && <div className="progress"><progress max="1" value={selection.progress.coverage}/><span>{Math.round(selection.progress.coverage * 100)} % visionné · {selection.progress.event_count} interactions enregistrées</span></div>}
      <div className="feedback"><button aria-pressed={selection.feedback.favorite} onClick={() => void feedback({ ...selection.feedback, favorite: !selection.feedback.favorite })}>{selection.feedback.favorite ? '★ Dans mes favoris' : '☆ Ajouter aux favoris'}</button><span>Cette ressource vous aide ?</span><button aria-pressed={selection.feedback.useful === true} onClick={() => void feedback({ ...selection.feedback, useful: true })}>Oui</button><button aria-pressed={selection.feedback.useful === false} onClick={() => void feedback({ ...selection.feedback, useful: false })}>Pas encore</button></div></section>}
      <section><div className="section-heading"><div><span className="eyebrow">UNE PISTE POUR CONTINUER</span><h2>Pour vous</h2></div><label className="algorithm">Méthode <select value={algorithm} onChange={e => setAlgorithm(e.target.value)}><option value="content">Selon vos intérêts</option><option value="popular">Popularité</option></select></label></div><div className="cards">{recommendations.map(card)}</div><p className="muted small">Pilote : les vidéos sont des médias de démonstration, à remplacer par vos contenus pédagogiques.</p></section>
      <section id="catalogue"><div className="section-heading"><div><span className="eyebrow">À EXPLORER</span><h2>Le catalogue</h2></div><span className="muted">{items.length} ressources</span></div><div className="filters"><input aria-label="Rechercher une ressource" placeholder="Rechercher une ressource…" value={q} onChange={e => setQ(e.target.value)}/><select aria-label="Type de ressource" value={kind} onChange={e => setKind(e.target.value)}><option value="">Tous les formats</option><option value="video">Vidéos</option><option value="file">Documents</option></select></div><div className="cards">{items.map(card)}</div>{items.length === 0 && <p>Aucune ressource ne correspond à votre recherche.</p>}</section>
      <p className="privacy">Vos interactions servent aux expérimentations du cours. Une pause ou un retour arrière ne permet pas de conclure à une difficulté. Contactez votre enseignant pour toute demande sur vos données.</p>
      </>}
    </main></div>
}
createRoot(document.getElementById('root')!).render(<App />)
