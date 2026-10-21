/**
 * Shared API error + fetch helper.
 *
 * The canonical shape is `{ status, detail }`, thrown by `fetchJson` below —
 * `detail` is FastAPI's error detail (falling back to statusText / HTTP code)
 * and doubles as `message`, so pages can show `⚠️ e.message` directly.
 *
 * The legacy `(code, path, error)` constructor is kept for workspaces that
 * still build errors from `{ code, path, error }` payloads; new code should
 * use the single `{ status, detail }` shape.
 */
export class ApiError extends Error {
  status: number
  detail: string
  code: string
  path: string
  error: string

  constructor(status: number, detail: string)
  constructor(code: string, path: string, error?: string)
  constructor(statusOrCode: number | string, detailOrPath: string, error = '') {
    if (typeof statusOrCode === 'number') {
      super(detailOrPath)
      this.status = statusOrCode
      this.detail = detailOrPath
      this.code = ''
      this.path = ''
      this.error = ''
    } else {
      super(`${statusOrCode}: ${detailOrPath || error}`)
      this.status = 0
      this.detail = detailOrPath || error
      this.code = statusOrCode
      this.path = detailOrPath
      this.error = error
    }
  }
}

/** fetch + JSON decode; non-2xx responses throw ApiError{status, detail}. */
export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    const data = (await r.json().catch(() => ({}))) as { detail?: unknown }
    const detail =
      typeof data.detail === 'string' && data.detail
        ? data.detail
        : r.statusText || `HTTP ${r.status}`
    throw new ApiError(r.status, detail)
  }
  return r.json() as Promise<T>
}
