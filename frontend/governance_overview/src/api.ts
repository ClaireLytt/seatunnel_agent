export interface StatsRecord {
  timestamp?: string
  source?: string
  counts?: Record<string, number>
  [k: string]: unknown
}

export interface AgentStats {
  key: string
  records: StatsRecord[] | null // null = endpoint unreachable / no history
}

const BASES: Record<string, string> = {
  hygiene: '/api/hygiene',
  metaquality: '/api/metaquality',
  contract: '/api/contract',
  grants: '/api/grants',
  ddlguard: '/api/ddlguard',
}

export const AGENT_KEYS = Object.keys(BASES)

export async function fetchStats(key: string): Promise<AgentStats> {
  try {
    const res = await fetch(`${BASES[key]}/stats?n=30`)
    if (!res.ok) return { key, records: null }
    const data = (await res.json()) as { records?: StatsRecord[] }
    return { key, records: data.records ?? [] }
  } catch {
    return { key, records: null }
  }
}
