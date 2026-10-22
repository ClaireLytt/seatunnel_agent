const BASE = '/api/release'

export interface NotesResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export interface GitLogResponse {
  log_text: string
  elapsed_ms: number
}

export async function generateNotes(
  logText: string,
  currentVersion: string,
  lang: string,
  polish: boolean,
): Promise<NotesResponse> {
  const r = await fetch(`${BASE}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      log_text: logText,
      current_version: currentVersion,
      lang,
      report: true,
      polish,
    }),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as string)
      .catch(() => `HTTP ${r.status}`)
    throw new Error(detail)
  }
  return r.json()
}

export async function fetchGitLog(): Promise<GitLogResponse> {
  const r = await fetch(`${BASE}/git-log`)
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as string)
      .catch(() => `HTTP ${r.status}`)
    throw new Error(detail)
  }
  return r.json()
}
