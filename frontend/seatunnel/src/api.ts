export interface Mode {
  key: string
  en: string
  zh: string
}

export interface TemplateMeta {
  name: string
  description: string
  category: string
  parameters: { name: string; default: string; description: string }[]
}

export interface Meta {
  modes: Mode[]
  templates: TemplateMeta[]
  config_placeholder: string
}

export async function fetchMeta(): Promise<Meta> {
  const resp = await fetch('/api/seatunnel/meta')
  if (!resp.ok) throw new Error(`meta: HTTP ${resp.status}`)
  return resp.json()
}
