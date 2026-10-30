import { useEffect, useState } from 'react'
import { api } from './api'
import './algorithms.css'

type Model = { state: string; model: string; requested_revision: string; resolved_revision: string | null; device: string; error: string | null }
type Parameter = { default: number; min: number; max: number; label: string; help: string }
type Algorithm = { id: string; name: string; family: string; version: string; summary: string; steps: string[]; formula: string; limitations: string[]; parameters: Record<string, Parameter>; semantic: boolean; available: boolean; model_status: Model | null; sources?: { path: string; content: string }[] }
type Catalogue = { families: { id: string; name: string; description: string }[]; algorithms: Algorithm[] }
type Result = { algorithm: string; effective_algorithm: string; fallback: boolean; version: string; elapsed_ms: number; reason: string; parameters: Record<string, number>; metadata: Record<string, unknown>; items: { id: string; title: string; score: number; kind: string }[] }

export function Algorithms() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null)
  const [family, setFamily] = useState('content'), [id, setId] = useState('tfidf')
  const [algorithm, setAlgorithm] = useState<Algorithm | null>(null)
  const [source, setSource] = useState(0), [model, setModel] = useState<Model | null>(null)
  const [interests, setInterests] = useState('recommandation, apprentissage'), [limit, setLimit] = useState(6)
  const [parameters, setParameters] = useState<Record<string, number>>({})
  const [result, setResult] = useState<Result | null>(null), [busy, setBusy] = useState(false)
  const [error, setError] = useState(''), [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    api<Catalogue>('/admin/algorithms').then(data => { if (active) setCatalogue(data) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [revision])
  useEffect(() => {
    let active = true
    setAlgorithm(null); setResult(null); setSource(0); setError('')
    if (id) api<Algorithm>(`/admin/algorithms/${id}`).then(data => {
      if (!active) return
      setAlgorithm(data); setParameters(Object.fromEntries(Object.entries(data.parameters).map(([key, value]) => [key, value.default])))
      if (data.model_status) setModel(data.model_status)
    }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [id])
  useEffect(() => {
    if (model?.state !== 'loading') return
    let active = true
    const timer = window.setInterval(() => {
      api<Model>('/admin/semantic-model').then(data => {
        if (!active) return
        setModel(data)
        if (data.state !== 'loading') setRevision(r => r + 1)
      }).catch(e => { if (active) setError(e.message) })
    }, 3000)
    return () => { active = false; clearInterval(timer) }
  }, [model?.state])
  function chooseFamily(value: string) {
    setFamily(value); setId(catalogue?.algorithms.find(a => a.family === value)?.id || '')
  }
  async function prepare() {
    setError(''); setBusy(true)
    try { setModel(await api<Model>('/admin/semantic-model/prepare', { method: 'POST' })) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  async function preview(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setResult(null)
    try { setResult(await api<Result>(`/admin/algorithms/${id}/preview`, { method: 'POST', body: JSON.stringify({ interests: interests.split(',').map(v => v.trim()).filter(Boolean), limit, parameters }) })) }
    catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const selectedFamily = catalogue?.families.find(f => f.id === family)
  const stateLabel: Record<string, string> = { not_prepared: 'À préparer', not_installed: 'Dépendances à installer', loading: 'Préparation en cours…', ready: 'Prêt', error: 'Préparation échouée' }
  return <section className="algorithm-lab"><span className="eyebrow">COMPRENDRE · LIRE LE CODE · EXPÉRIMENTER</span><h1>Les algorithmes de recommandation</h1><p className="muted">Chaque méthode possède son module et utilise la même interface de classement.</p>
    {error && <p className="alert" role="alert">{error}</p>}
    <div className="algorithm-layout"><nav className="algorithm-menu" aria-label="Familles d’algorithmes">{catalogue?.families.map(f => <div key={f.id}><button className={family === f.id ? 'active' : ''} aria-pressed={family === f.id} onClick={() => chooseFamily(f.id)}>{f.name}<small>{catalogue.algorithms.filter(a => a.family === f.id).length}</small></button>{family === f.id && catalogue.algorithms.filter(a => a.family === f.id).map(a => <button className={`algorithm-child ${id === a.id ? 'selected' : ''}`} key={a.id} aria-pressed={id === a.id} onClick={() => setId(a.id)}>{a.name}</button>)}</div>)}</nav>
    <div className="algorithm-content">{!id ? <section className="detail"><h2>{selectedFamily?.name}</h2><p>{selectedFamily?.description}</p><p className="muted">Aucun algorithme implémenté dans cette famille pour le moment.</p></section> : algorithm ? <>
      <section className="detail"><span className="eyebrow">{selectedFamily?.name} · V{algorithm.version}</span><h2>{algorithm.name}</h2><p>{algorithm.summary}</p><div className="formula">{algorithm.formula}</div><ol>{algorithm.steps.map(step => <li key={step}>{step}</li>)}</ol><h3>Entrées et limites</h3><p className="small">Profil : intérêts déclarés. Ressources : titre, thème, mots-clés et description. Les fichiers PDF et vidéos ne sont pas analysés automatiquement.</p><ul>{algorithm.limitations.map(l => <li key={l}>{l}</li>)}</ul>
      </section>
      {algorithm.semantic && <section className="detail"><h3>Modèle sémantique local</h3><p><strong role="status">{stateLabel[model?.state || 'not_prepared']}</strong></p><code className="model-name">{model?.model}</code><p className="small">Révision : {model?.resolved_revision || model?.requested_revision} · CPU</p><p className="muted small">La première préparation télécharge le modèle. Les encodages suivants sont exécutés localement ; les intérêts et ressources ne sont pas envoyés au service de téléchargement.</p>{model?.error && <p role="alert">{model.error}</p>}<button className="secondary" disabled={busy || model?.state === 'loading' || model?.state === 'ready'} onClick={() => void prepare()}>{model?.state === 'ready' ? 'Modèle prêt' : 'Préparer le modèle'}</button></section>}
      <section className="detail"><h3>Essayer sur le catalogue actif</h3><p className="small muted">Ce profil de test ne modifie aucun compte. Les brouillons et archives sont exclus.</p><form className="algorithm-form" onSubmit={preview}><label>Centres d’intérêt séparés par des virgules<input value={interests} onChange={e => setInterests(e.target.value)}/></label><div className="algorithm-parameters"><label>K · nombre de résultats<input type="number" min="1" max="20" required value={limit} onChange={e => setLimit(Number(e.target.value))}/></label>{Object.entries(algorithm.parameters).map(([key, spec]) => <label key={key}>{spec.label}<input type="number" min={spec.min} max={spec.max} step={key === 'candidate_pool' ? '1' : '.05'} required value={parameters[key] ?? spec.default} onChange={e => setParameters({ ...parameters, [key]: Number(e.target.value) })}/><small>{spec.help}</small></label>)}</div><button className="primary" disabled={busy}>{busy ? 'Calcul en cours…' : 'Calculer les recommandations'}</button></form>
      {result && <div className="algorithm-results"><p role="status">{result.fallback ? `Repli explicite : ${result.effective_algorithm}. ` : ''}{result.reason} · {result.elapsed_ms} ms</p>{result.items.length ? <ol>{result.items.map(item => <li key={item.id}><span>{item.title}<small>{item.kind === 'video' ? 'Vidéo' : 'Document'}</small></span><code>{item.score.toFixed(4)}</code></li>)}</ol> : <p>Aucun contenu actif dans le catalogue.</p>}<p className="small muted">Les scores affichés mesurent la pertinence. MMR détermine leur ordre final ; ses scores de sélection figurent dans les détails.</p><details><summary>Détails de l’exécution</summary><pre>{JSON.stringify({ algorithm: result.algorithm, effective_algorithm: result.effective_algorithm, version: result.version, parameters: result.parameters, metadata: result.metadata }, null, 2)}</pre></details></div>}
      </section>
      <section className="detail"><h3>Implémentation utilisée par l’application</h3><p className="small muted">Le module de l’algorithme et ses fonctions partagées sont lus depuis le code du serveur. Cette vue est en lecture seule.</p><label>Fichier<select value={source} onChange={e => setSource(Number(e.target.value))}>{algorithm.sources?.map((s, i) => <option key={s.path} value={i}>{s.path}</option>)}</select></label><pre className="implementation"><code>{algorithm.sources?.[source]?.content}</code></pre></section>
    </> : <p role="status">Chargement de l’algorithme…</p>}</div></div>
  </section>
}
