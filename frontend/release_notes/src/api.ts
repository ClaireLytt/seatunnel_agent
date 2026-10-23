import { fetchJson } from '@shared/api'

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

export function generateNotes(
  logText: string,
  currentVersion: string,
  lang: string,
  polish: boolean,
): Promise<NotesResponse> {
  return fetchJson(`${BASE}/notes`, {
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
}

export function fetchGitLog(): Promise<GitLogResponse> {
  return fetchJson(`${BASE}/git-log`)
}
