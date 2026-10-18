import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'
import { exportUrl, standaloneReportUrl } from '@/api'

const linkCls =
  'rounded border-[1.5px] border-ink px-3 py-1 font-mono text-[12px] text-ink ' +
  'transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard'

// Results-panel toolbar (legacy csv_btn / excel_btn DownloadButtons +
// view_btn window.open hack): plain links to GET endpoints — exports
// download, standalone report opens in a new tab.
export function ResultsToolbar({ sessionId }: { sessionId: string }) {
  const { t } = useTranslation()
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'

  return (
    <div data-testid="results-toolbar" className="flex items-center gap-2">
      <a className={linkCls} href={exportUrl('csv', sessionId, lang)} download>
        {t('exportCsv')}
      </a>
      <a className={linkCls} href={exportUrl('xlsx', sessionId, lang)} download>
        {t('exportExcel')}
      </a>
      <a
        className={linkCls}
        href={standaloneReportUrl(sessionId, lang)}
        target="_blank"
        rel="noopener noreferrer"
      >
        {t('viewReport')}
      </a>
    </div>
  )
}
