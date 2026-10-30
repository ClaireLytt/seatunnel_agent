/**
 * Shared API error + fetch helper.
 *
 * The canonical shape is `{ status, detail }`, thrown by `fetchJson` below —
 * `detail` is FastAPI's error detail (falling back to statusText / HTTP code)
 * and doubles as `message`, so pages can show `e.message` directly.
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

/**
 * POST JSON to an endpoint whose errors may be structured: a non-2xx
 * `detail` that is an object with `code` throws the legacy
 * ApiError(code, path, error) the page localizes; any other detail throws
 * a plain Error("<label>: HTTP <status>" fallback). Extracted verbatim
 * from the block previously copied across 11 workspace api clients.
 */
export async function postStructured<T>(url: string, body: unknown, label = 'request'): Promise<T> {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object' && 'code' in (detail as object)) {
      const d = detail as { code: string; path?: string; error?: string }
      throw new ApiError(d.code, d.path ?? '', d.error ?? '')
    }
    throw new Error((detail as string) || `${label}: HTTP ${r.status}`)
  }
  return r.json() as Promise<T>
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
