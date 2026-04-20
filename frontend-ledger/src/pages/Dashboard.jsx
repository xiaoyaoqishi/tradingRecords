import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Button, Card, DatePicker, Space, Table, Tag } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { getDashboard } from '../api/ledger'
import AmountText from '../components/AmountText'
import EmptyBlock from '../components/EmptyBlock'
import LoadingBlock from '../components/LoadingBlock'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import { formatDateTime, getDefaultLast30DaysRange } from '../utils/date'
import { transactionTypeLabel } from '../utils/ledger'
import { buildSearchParams } from '../utils/query'

const { RangePicker } = DatePicker
const DashboardExpenseChart = lazy(() => import('../components/DashboardExpenseChart'))

export default function Dashboard() {
  const navigate = useNavigate()
  const [dateRange, setDateRange] = useState(getDefaultLast30DaysRange)
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const payload = await getDashboard({
        date_from: dateRange[0].format('YYYY-MM-DD'),
        date_to: dateRange[1].format('YYYY-MM-DD'),
      })
      setData(payload)
    } finally {
      setLoading(false)
    }
  }, [dateRange])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const accounts = useMemo(() => {
    const rows = data?.accounts_summary || []
    return [...rows].sort((a, b) => Number(b.current_balance || 0) - Number(a.current_balance || 0))
  }, [data])

  const recentColumns = [
    {
      title: '发生时间',
      dataIndex: 'occurred_at',
      render: (value) => formatDateTime(value),
      width: 170,
    },
    {
      title: '类型',
      dataIndex: 'transaction_type',
      render: (value) => <Tag>{transactionTypeLabel(value)}</Tag>,
      width: 100,
    },
    {
      title: '金额',
      key: 'amount',
      render: (_, row) => (
        <AmountText
          value={row.amount}
          currency={row.currency}
          direction={row.direction}
          transactionType={row.transaction_type}
          signed
        />
      ),
      width: 150,
    },
    {
      title: '商户',
      dataIndex: 'merchant',
      render: (value) => value || '-',
    },
    {
      title: '操作',
      key: 'op',
      width: 120,
      render: (_, row) => (
        <Button
          type="link"
          onClick={() => {
            const query = buildSearchParams({
              transaction_type: row.transaction_type,
              account_id: row.account_id,
              category_id: row.category_id,
              date_from: dateRange[0].format('YYYY-MM-DD'),
              date_to: dateRange[1].format('YYYY-MM-DD'),
            })
            navigate(`/transactions?${query}`)
          }}
        >
          查看流水
        </Button>
      ),
    },
  ]

  if (loading && !data) {
    return <LoadingBlock />
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="仪表盘"
        subtitle="最近 30 天账本汇总"
        extra={[
          <RangePicker
            key="range"
            value={dateRange}
            onChange={(values) => {
              if (!values || values.length !== 2) return
              setDateRange(values)
            }}
          />,
          <Button key="refresh" icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
            刷新
          </Button>,
        ]}
      />

      <div className="dashboard-grid">
        <StatCard
          title="总收入"
          value={<AmountText value={data?.income_total} direction="income" currency="CNY" />}
          loading={loading}
        />
        <StatCard
          title="总支出"
          value={<AmountText value={data?.expense_total} direction="expense" currency="CNY" />}
          loading={loading}
        />
        <StatCard
          title="净现金流"
          value={<AmountText value={data?.net_cashflow} direction={data?.net_cashflow >= 0 ? 'income' : 'expense'} currency="CNY" />}
          loading={loading}
        />
        <StatCard title="流水笔数" value={data?.transaction_count ?? 0} loading={loading} />
      </div>

      <div className="dashboard-panels">
        <Card className="page-card" title="账户余额" loading={loading}>
          {!accounts.length ? (
            <EmptyBlock description="暂无账户数据" />
          ) : (
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={accounts}
              columns={[
                { title: '账户', dataIndex: 'name' },
                { title: '币种', dataIndex: 'currency', width: 90 },
                {
                  title: '当前余额',
                  key: 'current_balance',
                  width: 160,
                  render: (_, row) => (
                    <AmountText
                      value={row.current_balance}
                      currency={row.currency}
                      direction={Number(row.current_balance) >= 0 ? 'income' : 'expense'}
                    />
                  ),
                },
              ]}
            />
          )}
        </Card>

        <Card className="page-card" title="支出分类 Top5" loading={loading}>
          {!data?.top_expense_categories?.length ? (
            <EmptyBlock description="暂无支出分类数据" />
          ) : (
            <Suspense fallback={<LoadingBlock text="图表加载中..." />}>
              <DashboardExpenseChart data={data.top_expense_categories} />
            </Suspense>
          )}
        </Card>
      </div>

      <Card className="page-card" title="最近 10 条流水" loading={loading}>
        {!data?.recent_transactions?.length ? (
          <EmptyBlock description="暂无最近流水" />
        ) : (
          <Table rowKey="id" size="small" dataSource={data.recent_transactions} columns={recentColumns} pagination={false} />
        )}
      </Card>
    </Space>
  )
}
