import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Popconfirm, Space, Table, Tag, message } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  createTransaction,
  deleteTransaction,
  getTransaction,
  listAccounts,
  listCategories,
  listTransactions,
  reapplyRules,
  updateTransaction,
} from '../api/ledger'
import AmountText from '../components/AmountText'
import EmptyBlock from '../components/EmptyBlock'
import FilterBar from '../components/FilterBar'
import LoadingBlock from '../components/LoadingBlock'
import PageHeader from '../components/PageHeader'
import TransactionFormModal from '../components/TransactionFormModal'
import { formatDateTime } from '../utils/date'
import { directionLabel, transactionTypeLabel } from '../utils/ledger'
import { buildSearchParams, parseSearchParams, removeEmptyParams } from '../utils/query'

const QUERY_KEYS = ['transaction_type', 'account_id', 'category_id', 'keyword', 'date_from', 'date_to', 'direction', 'source']

const DEFAULT_FILTERS = {
  account_id: '',
  category_id: '',
  transaction_type: '',
  direction: '',
  source: '',
  keyword: '',
  date_from: '',
  date_to: '',
}

export default function Transactions() {
  const location = useLocation()
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')

  const [accounts, setAccounts] = useState([])
  const [categories, setCategories] = useState([])

  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState('create')
  const [editing, setEditing] = useState(null)

  const accountMap = useMemo(() => {
    const map = new Map()
    accounts.forEach((item) => map.set(item.id, item.name))
    return map
  }, [accounts])

  const categoryMap = useMemo(() => {
    const map = new Map()
    categories.forEach((item) => map.set(item.id, item.name))
    return map
  }, [categories])

  const loadMeta = async () => {
    const [accountRes, categoryRes] = await Promise.all([listAccounts(), listCategories()])
    setAccounts(Array.isArray(accountRes?.items) ? accountRes.items : [])
    setCategories(Array.isArray(categoryRes?.items) ? categoryRes.items : [])
  }

  const loadTransactions = async (nextFilters) => {
    setLoading(true)
    setErrorMessage('')
    try {
      const payload = await listTransactions(removeEmptyParams(nextFilters))
      setRows(Array.isArray(payload?.items) ? payload.items : [])
      setTotal(Number(payload?.total || 0))
    } catch (error) {
      setErrorMessage(error?.userMessage || '加载流水失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMeta()
  }, [])

  useEffect(() => {
    const parsed = parseSearchParams(location.search)
    const merged = {
      ...DEFAULT_FILTERS,
      ...QUERY_KEYS.reduce((acc, key) => {
        acc[key] = parsed[key] || ''
        return acc
      }, {}),
    }
    setFilters(merged)
    loadTransactions(merged)
  }, [location.search])

  const applyQueryFilters = (nextFilters) => {
    const queryPayload = QUERY_KEYS.reduce((acc, key) => {
      acc[key] = nextFilters[key]
      return acc
    }, {})
    const queryString = buildSearchParams(queryPayload)
    navigate(`/transactions${queryString ? `?${queryString}` : ''}`)
  }

  const initialLoading = loading && !rows.length

  if (initialLoading) {
    return <LoadingBlock />
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="流水记录"
        subtitle={`共 ${total} 条流水，默认按发生时间倒序`}
        extra={
          <Button
            type="primary"
            onClick={() => {
              setFormMode('create')
              setEditing(null)
              setFormOpen(true)
            }}
          >
            新增流水
          </Button>
        }
      />

      <FilterBar
        filters={filters}
        onChange={(patch) => setFilters((prev) => ({ ...prev, ...patch }))}
        onSearch={() => applyQueryFilters(filters)}
        onReset={() => {
          setFilters(DEFAULT_FILTERS)
          navigate('/transactions')
        }}
        accounts={accounts}
        categories={categories}
        loading={loading}
      />

      {errorMessage ? <Alert type="error" showIcon message={errorMessage} /> : null}

      <Card className="page-card">
        {!rows.length ? (
          <EmptyBlock description="暂无流水数据" />
        ) : (
          <Table
            rowKey="id"
            loading={loading}
            dataSource={rows}
            pagination={{ pageSize: 20, showSizeChanger: false }}
            columns={[
              { title: '发生时间', dataIndex: 'occurred_at', width: 170, render: (value) => formatDateTime(value) },
              { title: '账户', key: 'account', width: 120, render: (_, row) => accountMap.get(row.account_id) || row.account_id },
              { title: '分类', key: 'category', width: 130, render: (_, row) => (row.category_id ? categoryMap.get(row.category_id) || row.category_id : '-') },
              { title: '类型', dataIndex: 'transaction_type', width: 110, render: (value) => <Tag>{transactionTypeLabel(value)}</Tag> },
              { title: '方向', dataIndex: 'direction', width: 90, render: (value) => directionLabel(value) },
              { title: '来源', dataIndex: 'source', width: 110, render: (value) => (value === 'import_csv' ? 'CSV 导入' : value || '-') },
              {
                title: '金额',
                key: 'amount',
                width: 150,
                render: (_, row) => (
                  <AmountText
                    value={row.amount}
                    currency={row.currency}
                    direction={row.direction}
                    transactionType={row.transaction_type}
                    signed
                  />
                ),
              },
              { title: '商户', dataIndex: 'merchant', width: 140, render: (value) => value || '-' },
              { title: '描述', dataIndex: 'description', render: (value) => value || '-' },
              { title: '备注', dataIndex: 'note', render: (value) => value || '-' },
              {
                title: '操作',
                key: 'op',
                fixed: 'right',
                width: 240,
                render: (_, row) => (
                  <Space>
                    <Button
                      type="link"
                      onClick={async () => {
                        const detail = await getTransaction(row.id)
                        setEditing(detail)
                        setFormMode('edit')
                        setFormOpen(true)
                      }}
                    >
                      编辑
                    </Button>
                    <Button
                      type="link"
                      onClick={async () => {
                        const result = await reapplyRules({ transaction_ids: [row.id] })
                        if (result.updated_count > 0) {
                          message.success('已重应用规则并更新该流水')
                          await loadTransactions(filters)
                        } else {
                          message.info('未发生字段变化')
                        }
                      }}
                    >
                      重应用规则
                    </Button>
                    <Popconfirm
                      title="确认删除该流水？"
                      onConfirm={async () => {
                        await deleteTransaction(row.id)
                        await loadTransactions(filters)
                      }}
                    >
                      <Button type="link" danger>
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
            scroll={{ x: 1600 }}
          />
        )}
      </Card>

      <TransactionFormModal
        open={formOpen}
        mode={formMode}
        initialValues={editing}
        accounts={accounts}
        categories={categories}
        onCancel={() => setFormOpen(false)}
        onSubmit={async (payload, { saveMode }) => {
          const applyRules = payload.apply_rules !== false
          const submitPayload = { ...payload }
          delete submitPayload.apply_rules

          if (formMode === 'edit' && editing?.id) {
            await updateTransaction(editing.id, submitPayload, { applyRules })
            setFormOpen(false)
            await loadTransactions(filters)
            return
          }

          await createTransaction(submitPayload, { applyRules })
          await loadTransactions(filters)
          if (saveMode === 'close') {
            setFormOpen(false)
          }
        }}
      />
    </Space>
  )
}
