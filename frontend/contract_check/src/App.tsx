import { ScanPage } from '@shared/components/ScanPage'
import { scan } from '@/api'

export default function App() {
  return (
    <ScanPage
      cfg={{
        badge: 'data / contract',
        titlePrefix: '📜',
        errorCode: 'contract_failed',
        reportClass: 'contract-report',
        scan: (body) => scan({ ...body, contract: String(body.contract ?? '') }),
        extra: { bodyKey: 'contract', required: true, mono: true },
        defaultDir: 'examples/governance_demo',
      }}
    />
  )
}
