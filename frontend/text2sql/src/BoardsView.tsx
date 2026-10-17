import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import {
  createBoard,
  deleteBoard,
  fetchBoards,
  renderBoard,
  type Board,
  type SessionMeta,
} from '@/api'

export function BoardsView({ session }: { session: SessionMeta | null }) {
  const { t } = useTranslation()
  const [boards, setBoards] = useState<Board[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [rendered, setRendered] = useState<Record<string, any[]>>({})
  const [err, setErr] = useState('')

  const refresh = () => {
    fetchBoards().then((r) => setBoards(r.boards))
  }
  useEffect(refresh, [])

  const doCreate = async () => {
    if (!newName.trim()) return
    try {
      await createBoard(newName.trim())
      setNewName('')
      refresh()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const doRender = async (id: string) => {
    if (!session) {
      setErr(t('renderNeedsConnect'))
      return
    }
    try {
      const r = await renderBoard(id, session.session_id)
      setRendered((prev) => ({ ...prev, [id]: r.results }))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="st-boards-view space-y-4">
      <Card>
        <div className="mb-2 flex items-center gap-3 font-mono text-[12px]">
          <span className="uppercase tracking-[0.18em] text-ink-soft">{t('boardsTitle')}</span>
          <button onClick={refresh} className="rounded border border-line px-2 text-muted">
            ⟳
          </button>
        </div>
        <div className="mb-3 flex gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doCreate()}
            placeholder={t('newBoardName')}
            className="flex-1 rounded border border-line bg-paper px-2 py-1 font-mono text-[13px] text-fg outline-none focus:border-ink"
          />
          <button
            onClick={doCreate}
            className="rounded border border-ink px-3 font-mono text-[12px] text-ink hover:bg-ink hover:text-paper"
          >
            {t('createBoard')}
          </button>
        </div>
        {boards.map((b) => (
          <div key={b.id} className="mb-2 rounded border border-line">
            <div
              onClick={() => setExpanded(expanded === b.id ? null : b.id)}
              className="flex cursor-pointer items-center gap-3 px-3 py-2 font-mono text-[13px]"
            >
              <span className="text-fg">{b.name}</span>
              <span className="text-muted">{b.items.length} items</span>
              <div className="ml-auto flex gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    doRender(b.id)
                  }}
                  disabled={!session}
                  className="rounded border border-ink px-2 text-ink disabled:opacity-40"
                >
                  {t('renderBoard')}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteBoard(b.id).then(refresh)
                  }}
                  className="rounded border border-line px-1.5 text-muted hover:text-accent"
                >
                  ✕
                </button>
              </div>
            </div>
            {expanded === b.id && (
              <div className="border-t border-line bg-paper px-3 py-2 font-mono text-[12px]">
                {b.items.length === 0 && <span className="text-muted">—</span>}
                {b.items.map((item) => (
                  <div key={item.id} className="mb-1">
                    <span className="text-fg">{item.title}</span>
                    <pre className="mt-0.5 overflow-x-auto text-[11px] text-muted">{item.sql}</pre>
                  </div>
                ))}
                {rendered[b.id] && (
                  <div className="mt-2 space-y-2 border-t border-line pt-2">
                    {rendered[b.id].map((r: any, i: number) => (
                      <div key={i}>
                        <div className="text-fg">{r.title}</div>
                        {r.error ? (
                          <div className="text-accent">{r.error}</div>
                        ) : (
                          <table className="w-full text-[11px]">
                            <thead>
                              <tr className="border-b border-line">
                                {r.columns?.map((c: string) => (
                                  <th key={c} className="px-1 text-left text-ink">{c}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {r.rows?.map((row: any[], ri: number) => (
                                <tr key={ri} className="border-b border-line last:border-b-0">
                                  {row.map((v: any, ci: number) => (
                                    <td key={ci} className="px-1 text-fg">{String(v ?? '')}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {boards.length === 0 && (
          <div className="py-4 text-center font-mono text-[13px] text-muted">—</div>
        )}
        {err && <div className="mt-2 font-mono text-[12px] text-accent">{err}</div>}
      </Card>
    </div>
  )
}
