/** Fields the Data Comparison page hands over via the st_dataskew_conn
 * cookie (no password). Lives outside the component file so fast refresh
 * keeps working (react-refresh/only-export-components). */
export interface ConnHandoff {
  ds_type: string
  host: string
  port: string
  database: string
  username: string
}

export function readConnHandoff(): ConnHandoff | null {
  const m = document.cookie.match(/(?:^|;\s*)st_dataskew_conn=([^;]+)/)
  if (!m) return null
  try {
    const data = JSON.parse(decodeURIComponent(m[1])) as Record<string, unknown>
    return {
      ds_type: String(data.ds_type ?? '').toLowerCase(),
      host: String(data.host ?? ''),
      port: String(data.port ?? ''),
      database: String(data.database ?? ''),
      username: String(data.username ?? ''),
    }
  } catch {
    return null
  }
}
