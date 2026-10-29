let token = ''
export function setToken(value: string) { token = value }
export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + path, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : `Erreur ${response.status}`)
  }
  return response.status === 204 ? undefined as T : response.json()
}
export type Resource = { id: string; title: string; description: string; topic: string; level: string; kind: 'video' | 'file'; duration: number; url: string; tags: string[]; reason?: string }
export type Progress = { position_seconds: number; coverage: number; covered_seconds: number; event_count: number }
