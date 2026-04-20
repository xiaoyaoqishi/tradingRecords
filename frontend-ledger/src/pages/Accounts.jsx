import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Popconfirm, Select, Space, Table, Tag } from 'antd'
import { createAccount, deleteAccount, listAccounts, updateAccount } from '../api/ledger'
import AccountFormModal from '../components/AccountFormModal'
import AmountText from '../components/AmountText'
import EmptyBlock from '../components/EmptyBlock'
import LoadingBlock from '../components/LoadingBlock'
import PageHeader from '../components/PageHeader'
import { ACCOUNT_TYPE_OPTIONS } from '../utils/enums'
import { accountTypeLabel } from '../utils/ledger'

const ACTIVE_OPTIONS = [
  { label: '全部状态', value: 'all' },
  { label: '启用', value: '1' },
  { label: '停用', value: '0' },
]

export default function Accounts() {
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [rows, setRows] = useState([])
  const [accountType, setAccountType] = useState('all')
  const [active, setActive] = useState('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const loadAccounts = async () => {
    setLoading(true)
    try {
      const res = await listAccounts()
      setRows(Array.isArray(res?.items) ? res.items : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAccounts()
  }, [])

  const filteredRows = useMemo(() => {
    return rows.filter((item) => {
      if (accountType !== 'all' && item.account_type !== accountType) return false
      if (active !== 'all' && String(Number(Boolean(item.is_active))) !== active) return false
      return true
    })
  }, [rows, accountType, active])

  if (loading && !rows.length) {
    return <LoadingBlock />
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="账户管理"
        subtitle="账户管理与余额查看"
        extra={<Button type="primary" onClick={() => { setEditing(null); setFormOpen(true) }}>新增账户</Button>}
      />

      <Card className="page-card">
        <Space>
          <Select
            value={accountType}
            onChange={setAccountType}
            style={{ width: 160 }}
            options={[{ label: '全部类型', value: 'all' }, ...ACCOUNT_TYPE_OPTIONS]}
          />
          <Select value={active} onChange={setActive} style={{ width: 140 }} options={ACTIVE_OPTIONS} />
        </Space>
      </Card>

      <Card className="page-card">
        {!filteredRows.length ? (
          <EmptyBlock description="暂无账户" />
        ) : (
          <Table
            rowKey="id"
            loading={loading}
            dataSource={filteredRows}
            rowClassName={(row) => (row.is_active ? '' : 'table-muted')}
            columns={[
              { title: '名称', dataIndex: 'name', width: 160 },
              { title: '类型', dataIndex: 'account_type', width: 110, render: (value) => accountTypeLabel(value) },
              { title: '币种', dataIndex: 'currency', width: 90 },
              { title: '初始余额', key: 'initial_balance', width: 140, render: (_, row) => <AmountText value={row.initial_balance} currency={row.currency} /> },
              { title: '当前余额', key: 'current_balance', width: 150, render: (_, row) => <AmountText value={row.current_balance} currency={row.currency} direction={Number(row.current_balance) >= 0 ? 'income' : 'expense'} /> },
              {
                title: '状态',
                dataIndex: 'is_active',
                width: 100,
                render: (value) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag>,
              },
              { title: '备注', dataIndex: 'notes', render: (value) => value || '-' },
              {
                title: '操作',
                key: 'op',
                width: 160,
                render: (_, row) => (
                  <Space>
                    <Button
                      type="link"
                      onClick={() => {
                        setEditing(row)
                        setFormOpen(true)
                      }}
                    >
                      编辑
                    </Button>
                    <Popconfirm
                      title="确认删除该账户？"
                      onConfirm={async () => {
                        await deleteAccount(row.id)
                        await loadAccounts()
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
          />
        )}
      </Card>

      <AccountFormModal
        open={formOpen}
        initialValues={editing}
        submitting={submitting}
        onCancel={() => setFormOpen(false)}
        onSubmit={async (payload) => {
          setSubmitting(true)
          try {
            if (editing?.id) {
              await updateAccount(editing.id, payload)
            } else {
              await createAccount(payload)
            }
            setFormOpen(false)
            await loadAccounts()
          } finally {
            setSubmitting(false)
          }
        }}
      />
    </Space>
  )
}
