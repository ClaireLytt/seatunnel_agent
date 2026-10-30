import { ScanPage } from '@shared/components/ScanPage'
import { scan } from '@/api'

export default function App() {
  return (
    <ScanPage
      cfg={{
        badge: 'data / grants',
        titlePrefix: '🗝️',
        errorCode: 'grants_failed',
        reportClass: 'grants-report',
        scan,
        defaultDir: 'examples/governance_demo',
      }}
    />
  )
}
