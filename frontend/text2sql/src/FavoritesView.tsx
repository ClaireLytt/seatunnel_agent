import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import {
  deleteFavorite,
  fetchFavorites,
  renameFavorite,
  type Favorite,
} from '@/api'

/** The #favorites view: list / search / rename / delete saved SQL queries. */
export function FavoritesView() {
  const { t } = useTranslation()
  const [favs, setFavs] = useState<Favorite[]>([])
  const [search, setSearch] = useState('')
  const [sel, setSel] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [renameVal, setRenameVal] = useState('')

  const refresh = () => {
    fetchFavorites().then((r) => {
      setFavs(r.favorites)
      setSel(null)
      setRenaming(null)
    })
  }
  useEffect(refresh, [])

  const filtered = search
    ? favs.filter(
        (f) =>
          f.name.toLowerCase().includes(search.toLowerCase()) ||
          f.sql.toLowerCase().includes(search.toLowerCase()),
      )
    : favs

  const doRename = async (id: string) => {
    if (!renameVal.trim()) return
    await renameFavorite(id, renameVal.trim())
    refresh()
  }

  const doDelete = async (id: string) => {
    await deleteFavorite(id)
    refresh()
  }

  return (
    <div className="st-favorites-view space-y-4">
      <Card>
        <div className="mb-2 flex items-center gap-3 font-mono text-[12px]">
          <span className="uppercase tracking-[0.18em] text-ink-soft">{t('favorites')}</span>
          <button onClick={refresh} className="rounded border border-line px-2 text-muted">
            ⟳
          </button>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('searchFavorites')}
          className="mb-3 w-full rounded border border-line bg-paper px-2 py-1 font-mono text-[13px] text-fg outline-none focus:border-ink"
        />
        <table className="w-full font-mono text-[13px]">
          <thead>
            <tr className="border-b-2 border-ink text-left">
              <th className="px-2 py-1 text-ink">{t('favName')}</th>
              <th className="px-2 py-1 text-ink">SQL</th>
              <th className="px-2 py-1 text-ink">{t('time')}</th>
              <th className="px-2 py-1 text-ink" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((f) => (
              <tr
                key={f.id}
                onClick={() => setSel(sel === f.id ? null : f.id)}
                className={
                  'cursor-pointer border-b border-line last:border-b-0 ' +
                  (sel === f.id ? 'bg-paper' : '')
                }
              >
                <td className="px-2 py-1 text-fg">
                  {renaming === f.id ? (
                    <input
                      value={renameVal}
                      onChange={(e) => setRenameVal(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && doRename(f.id)}
                      onBlur={() => setRenaming(null)}
                      autoFocus
                      className="w-full border-b border-ink bg-transparent outline-none"
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    f.name
                  )}
                </td>
                <td className="max-w-[320px] truncate px-2 py-1 text-muted">{f.sql}</td>
                <td className="px-2 py-1 text-muted">{f.created_at?.slice(0, 10)}</td>
                <td className="px-2 py-1">
                  <div className="flex gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setRenaming(f.id)
                        setRenameVal(f.name)
                      }}
                      className="rounded border border-line px-1.5 text-muted hover:text-ink"
                      title={t('rename')}
                    >
                      ✎
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        doDelete(f.id)
                      }}
                      className="rounded border border-line px-1.5 text-muted hover:text-accent"
                      title={t('deleteSel')}
                    >
                      ✕
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-4 text-center font-mono text-[13px] text-muted">—</div>
        )}
        {sel && (() => {
          const f = favs.find((x) => x.id === sel)
          return f ? (
            <pre className="mt-2 overflow-x-auto rounded border border-line bg-paper px-2 py-1 font-mono text-[12px] text-fg">
              {f.sql}
            </pre>
          ) : null
        })()}
      </Card>
    </div>
  )
}
