import { useEffect, useMemo, useState } from 'react'
import { Button, Card, DatePicker, Progress, Space, Statistic, Table, Tag } from 'antd'
import dayjs from 'dayjs'
import {
  getAnalyticsCategoryBreakdown,
  getAnalyticsMonthlyTrend,
  getAnalyticsPlatformBreakdown,
  getAnalyticsSummary,
  getAnalyticsTopMerchants,
  getAnalyticsUnrecognizedBreakdown,
} from '../api/ledger'
import PageHeader from '../components/PageHeader'

const { RangePicker } = DatePicker

function moneyText(v) {
  return `¥${Number(v || 0).toFixed(2)}`
}

function percentText(v) {
  return `${(Number(v || 0) * 100).toFixed(1)}%`
}

function getDefaultCurrentMonthRange() {
  const now = dayjs()
  return [now.startOf('month'), now.endOf('day')]
}

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(false)
  const [dateRange, setDateRange] = useState(getDefaultCurrentMonthRange)
  const [summary, setSummary] = useState(null)
  const [category, setCategory] = useState([])
  const [platform, setPlatform] = useState([])
  const [topMerchants, setTopMerchants] = useState([])
  const [monthlyTrend, setMonthlyTrend] = useState([])
  const [unrecognized, setUnrecognized] = useState(null)

  const queryParams = useMemo(() => {
    if (!dateRange || dateRange.length !== 2 || !dateRange[0] || !dateRange[1]) return {}
    return {
      date_from: dateRange[0].format('YYYY-MM-DD'),
      date_to: dateRange[1].format('YYYY-MM-DD'),
    }
  }, [dateRange])

  const load = async () => {
    setLoading(true)
    try {
      const [summaryPayload, categoryPayload, platformPayload, merchantPayload, trendPayload, unrecognizedPayload] = await Promise.all([
        getAnalyticsSummary(queryParams),
        getAnalyticsCategoryBreakdown(queryParams),
        getAnalyticsPlatformBreakdown(queryParams),
        getAnalyticsTopMerchants({ ...queryParams, limit: 10 }),
        getAnalyticsMonthlyTrend(queryParams),
        getAnalyticsUnrecognizedBreakdown(queryParams),
      ])
      setSummary(summaryPayload || {})
      setCategory(Array.isArray(categoryPayload?.items) ? categoryPayload.items : [])
      setPlatform(Array.isArray(platformPayload?.items) ? platformPayload.items : [])
      setTopMerchants(Array.isArray(merchantPayload?.items) ? merchantPayload.items : [])
      setMonthlyTrend(Array.isArray(trendPayload?.items) ? trendPayload.items : [])
      setUnrecognized(unrecognizedPayload || {})
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [queryParams.date_from, queryParams.date_to])

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="基础分析"
        subtitle="基于已入账交易的稳定口径统计"
        extra={
          <Space>
            <RangePicker value={dateRange} onChange={(v) => setDateRange(v)} />
            <Button onClick={load} loading={loading}>刷新</Button>
          </Space>
        }
      />

      <div className="dashboard-grid">
        <Card className="page-card"><Statistic title="总支出" value={Number(summary?.总支出 || 0)} precision={2} prefix="¥" /></Card>
        <Card className="page-card"><Statistic title="交易数" value={Number(summary?.交易数 || 0)} /></Card>
        <Card className="page-card"><Statistic title="已识别率" value={Number(summary?.已识别率 || 0) * 100} precision={1} suffix="%" /></Card>
        <Card className="page-card"><Statistic title="未识别数 / 金额" value={`${Number(summary?.未识别数 || 0)} / ${moneyText(summary?.未识别金额)}`} /></Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Card className="page-card" title="分类占比（支出）" loading={loading}>
          <Table
            rowKey="分类名称"
            size="small"
            pagination={false}
            dataSource={category}
            columns={[
              { title: '分类名称', dataIndex: '分类名称' },
              { title: '金额', dataIndex: '金额', width: 140, render: (v) => moneyText(v) },
              {
                title: '占比',
                dataIndex: '占比',
                width: 180,
                render: (v) => <Progress percent={Number((Number(v || 0) * 100).toFixed(1))} size="small" />,
              },
            ]}
          />
        </Card>

        <Card className="page-card" title="平台占比（支出）" loading={loading}>
          <Table
            rowKey="平台名称"
            size="small"
            pagination={false}
            dataSource={platform}
            columns={[
              { title: '平台名称', dataIndex: '平台名称' },
              { title: '金额', dataIndex: '金额', width: 140, render: (v) => moneyText(v) },
              {
                title: '占比',
                dataIndex: '占比',
                width: 180,
                render: (v) => <Progress percent={Number((Number(v || 0) * 100).toFixed(1))} size="small" />,
              },
            ]}
          />
        </Card>
      </div>

      <Card className="page-card" title="高频商户 Top 10" loading={loading}>
        <Table
          rowKey="商户名称"
          size="small"
          pagination={false}
          dataSource={topMerchants}
          columns={[
            { title: '商户名称', dataIndex: '商户名称' },
            { title: '次数', dataIndex: '次数', width: 100 },
            { title: '总金额', dataIndex: '总金额', width: 160, render: (v) => moneyText(v) },
          ]}
        />
      </Card>

      <Card className="page-card" title="月度趋势（总支出 + 重点分类）" loading={loading}>
        <Table
          rowKey="月份"
          size="small"
          pagination={false}
          dataSource={monthlyTrend}
          columns={[
            { title: '月份', dataIndex: '月份', width: 100 },
            { title: '总支出', dataIndex: '总支出', width: 140, render: (v) => moneyText(v) },
            { title: '餐饮', dataIndex: '餐饮', width: 120, render: (v) => moneyText(v) },
            { title: '买菜商超', dataIndex: '买菜商超', width: 120, render: (v) => moneyText(v) },
            { title: '交通', dataIndex: '交通', width: 120, render: (v) => moneyText(v) },
            { title: '购物', dataIndex: '购物', width: 120, render: (v) => moneyText(v) },
          ]}
        />
      </Card>

      <Card className="page-card" title="未识别分析" loading={loading}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space wrap>
            <Tag color="warning">未识别条数：{Number(unrecognized?.未识别条数 || 0)}</Tag>
            <Tag color="warning">未识别金额：{moneyText(unrecognized?.未识别金额 || 0)}</Tag>
            <Tag color="warning">未识别金额占比：{percentText(unrecognized?.未识别金额占比 || 0)}</Tag>
          </Space>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Card size="small" title="未识别商户 Top">
              <Table
                rowKey="商户"
                size="small"
                pagination={false}
                dataSource={Array.isArray(unrecognized?.未识别商户Top) ? unrecognized?.未识别商户Top : []}
                columns={[
                  { title: '商户', dataIndex: '商户' },
                  { title: '次数', dataIndex: '次数', width: 90 },
                  { title: '金额', dataIndex: '金额', width: 120, render: (v) => moneyText(v) },
                ]}
              />
            </Card>
            <Card size="small" title="未识别摘要 Top">
              <Table
                rowKey="摘要"
                size="small"
                pagination={false}
                dataSource={Array.isArray(unrecognized?.未识别摘要Top) ? unrecognized?.未识别摘要Top : []}
                columns={[
                  { title: '摘要', dataIndex: '摘要', ellipsis: true },
                  { title: '次数', dataIndex: '次数', width: 90 },
                  { title: '金额', dataIndex: '金额', width: 120, render: (v) => moneyText(v) },
                ]}
              />
            </Card>
          </div>
        </Space>
      </Card>
    </Space>
  )
}
