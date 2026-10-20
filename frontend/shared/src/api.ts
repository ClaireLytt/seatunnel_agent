/**
 * Shared API error class.
 *
 * Covers the two dominant patterns across workspaces:
 *  - code + path + error  (pii_scan, schema_drift, metric_diff, etc.)
 *  - status + detail      (sql_review)
 *
 * Workspaces that need extra fields (e.g. data_lineage's `suggestions`)
 * can extend this class locally.
 */
export class ApiError extends Error {
  code: string
  path: string
  error: string
  constructor(code: string, path: string, error = '') {
    super(`${code}: ${path || error}`)
    this.code = code
    this.path = path
    this.error = error
  }
}
