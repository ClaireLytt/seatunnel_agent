import { ScanPage } from '@shared/components/ScanPage'
import { scan } from '@/api'

export default function App() {
  return (
    <ScanPage
      cfg={{
        badge: 'data / ddlguard',
        errorCode: 'ddlguard_failed',
        reportClass: 'ddlguard-report',
        scan,
        defaultDir: 'examples/governance_demo',
        detailsOpen: true,
        sqlRows: 10,
      }}
    />
  )
}
