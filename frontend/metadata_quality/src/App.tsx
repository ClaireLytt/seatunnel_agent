import { ScanPage } from '@shared/components/ScanPage'
import { scan } from '@/api'

export default function App() {
  return (
    <ScanPage
      cfg={{
        badge: 'data / metaquality',
        errorCode: 'metaquality_failed',
        reportClass: 'metaquality-report',
        scan,
        defaultDir: 'examples/governance_demo',
      }}
    />
  )
}
