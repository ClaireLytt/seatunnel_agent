import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'

interface AgentLink {
  zh: string
  en: string
  route: string
  logo: string
}

interface Suite {
  key: string
  agents: AgentLink[]
  flows: string[][]
}

const SUITES: Suite[] = [
  {
    key: 'suite_quality',
    agents: [
      { zh: '数据抽样剖析', en: 'Sample Profiler', route: '/sampleprofile/', logo: 'SA' },
      { zh: '数据分布异常', en: 'Distribution Drift', route: '/distanomaly/', logo: 'DA' },
      { zh: '数据重复检测', en: 'Duplicate Check', route: '/dupcheck/', logo: 'DK' },
      { zh: '数据波动分析', en: 'Data Volatility', route: '/datavolatility/', logo: 'VO' },
      { zh: '质量根因追踪', en: 'Quality Trace', route: '/qualitytrace/', logo: 'QT' },
      { zh: '一致性修复', en: 'Data Repair', route: '/datarepair/', logo: 'RP' },
    ],
    flows: [
      ['/datavolatility/', '/qualitytrace/'],
      ['/dupcheck/', '/datarepair/'],
    ],
  },
  {
    key: 'suite_governance',
    agents: [
      { zh: '数据资产搜索', en: 'Asset Search', route: '/assetsearch/', logo: 'AS' },
      { zh: '数据字典生成', en: 'Data Dictionary', route: '/datadict/', logo: 'DD' },
      { zh: '资产价值评估', en: 'Asset Value', route: '/assetvalue/', logo: 'AV' },
      { zh: '存储成本治理', en: 'Storage Cost', route: '/storagecost/', logo: 'SC' },
      { zh: '数据库运行诊断', en: 'DB Diagnosis', route: '/dbdiag/', logo: 'DB' },
      { zh: '权限申请审核', en: 'Grant Review', route: '/grantreview/', logo: 'GR' },
    ],
    flows: [['/assetvalue/', '/storagecost/']],
  },
  {
    key: 'suite_realtime',
    agents: [
      { zh: 'Kafka 消费积压', en: 'Kafka Lag', route: '/kafkalag/', logo: 'KL' },
      { zh: 'Flink 作业诊断', en: 'Flink Diagnosis', route: '/flinkdiag/', logo: 'FD' },
      { zh: '实时延迟分析', en: 'RT Latency', route: '/rtlatency/', logo: 'RL' },
      { zh: 'CDC 同步诊断', en: 'CDC Diagnosis', route: '/cdcdiag/', logo: 'CD' },
      { zh: '实时离线核对', en: 'RT-Offline Diff', route: '/rtoffline/', logo: 'RO' },
    ],
    flows: [['/flinkdiag/', '/kafkalag/']],
  },
  {
    key: 'suite_scheduling',
    agents: [
      { zh: '任务失败归因', en: 'Task Failure', route: '/taskfailure/', logo: 'TF' },
      { zh: '调度窗口优化', en: 'Schedule Advisor', route: '/scheduleadvisor/', logo: 'SV' },
    ],
    flows: [],
  },
]

function AgentTile({ agent, lang }: { agent: AgentLink; lang: string }) {
  return (
    <a
      href={agent.route}
      className="flex items-center gap-3 rounded border-[1.5px] border-line bg-[var(--paper)] px-3 py-2.5 transition hover:-translate-x-px hover:-translate-y-px hover:border-ink hover:shadow-hard"
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded border-[1.5px] border-ink font-mono text-[11px] font-bold">
        {agent.logo}
      </span>
      <span className="text-sm font-semibold">{lang.startsWith('zh') ? agent.zh : agent.en}</span>
    </a>
  )
}

export default function App() {
  const { t, i18n } = useTranslation()

  const nameOf = (route: string): string => {
    for (const s of SUITES) {
      const a = s.agents.find((x) => x.route === route)
      if (a) return i18n.language.startsWith('zh') ? a.zh : a.en
    }
    return route
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / suites" maxW="max-w-[620px]" />

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {SUITES.map((suite) => (
          <Card key={suite.key}>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t(suite.key)}
            </h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {suite.agents.map((a) => (
                <AgentTile key={a.route} agent={a} lang={i18n.language} />
              ))}
            </div>
            {suite.flows.length > 0 && (
              <div className="mt-3 flex flex-col gap-1">
                {suite.flows.map(([from, to]) => (
                  <span
                    key={from + to}
                    className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted"
                  >
                    {nameOf(from)} → {nameOf(to)}
                  </span>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
