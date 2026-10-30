import { ScanPage } from '@shared/components/ScanPage'
import { scan } from '@/api'

export default function App() {
  return (
    <ScanPage
      cfg={{
        badge: 'data / ddlguard',
        titlePrefix: '🛡️',
        errorCode: 'ddlguard_failed',
        reportClass: 'ddlguard-report',
        scan,
        detailsOpen: true,
        sqlRows: 10,
      }}
    />
  )
}
