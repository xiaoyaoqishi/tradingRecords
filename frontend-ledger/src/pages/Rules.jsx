import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Form, Input, InputNumber, Popconfirm, Select, Space, Switch, Table, Tag, message } from 'antd'
import {
  listAccounts,
  listCategories,
  createRule,
  deleteRule,
  listRules,
  previewRules,
  reapplyRules,
  updateRule,
} from '../api/ledger'
import PageHeader from '../components/PageHeader'
import RuleActionSummary from '../components/RuleActionSummary'
import RuleFormModal from '../components/RuleFormModal'
import RuleMatchSummary from '../components/RuleMatchSummary'

export default function Rules() {
  const [loading, setLoading] = useState(true)
  const [rows, setRows] = useState([])
  const [accounts, setAccounts] = useState([])
  const [categories, setCategories] = useState([])
  const [enabledFilter, setEnabledFilter] = useState('all')

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewItems, setPreviewItems] = useState([])
  const [testForm] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const [ruleRes, accountRes, categoryRes] = await Promise.all([listRules(), listAccounts(), listCategories()])
      setRows(Array.isArray(ruleRes?.items) ? ruleRes.items : [])
      setAccounts(Array.isArray(accountRes?.items) ? accountRes.items : [])
      setCategories(Array.isArray(categoryRes?.items) ? categoryRes.items : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filteredRows = useMemo(() => {
    if (enabledFilter === 'all') return rows
    const target = enabledFilter === '1'
    return rows.filter((x) => Boolean(x.is_active) === target)
  }, [rows, enabledFilter])

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="自动分类规则"
        subtitle="规则按优先级升序执行，支持导入与手动流水自动补全"
        extra={<Button type="primary" onClick={() => { setEditing(null); setFormOpen(true) }}>新增规则</Button>}
      />

      <Card className="page-card">
        <Space>
          <Select
            value={enabledFilter}
            onChange={setEnabledFilter}
            style={{ width: 160 }}
            options={[
              { label: '全部状态', value: 'all' },
              { label: '仅启用', value: '1' },
              { label: '仅停用', value: '0' },
            ]}
          />
          <Button
            onClick={async () => {
              const payload = await reapplyRules({ source: 'import_csv' })
              message.success(`重应用完成：扫描 ${payload.scanned_count}，更新 ${payload.updated_count}`)
            }}
          >
            对 CSV 导入记录重应用规则
          </Button>
        </Space>
      </Card>

      <Card className="page-card" title="规则列表">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={filteredRows}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          columns={[
            { title: '名称', dataIndex: 'name', width: 180 },
            { title: '启用', dataIndex: 'is_active', width: 100, render: (v) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '停用'}</Tag> },
            { title: '优先级', dataIndex: 'priority', width: 90 },
            { title: '条件摘要', dataIndex: 'match_json', render: (v) => <RuleMatchSummary matchJson={v} /> },
            { title: '动作摘要', dataIndex: 'action_json', render: (v) => <RuleActionSummary actionJson={v} /> },
            { title: '更新时间', dataIndex: 'updated_at', width: 190, render: (v) => (v ? String(v).replace('T', ' ').slice(0, 19) : '-') },
            {
              title: '操作',
              key: 'op',
              width: 220,
              render: (_, row) => (
                <Space>
                  <Switch
                    size="small"
                    checked={row.is_active}
                    onChange={async (checked) => {
                      await updateRule(row.id, { is_active: checked })
                      await load()
                    }}
                  />
                  <Button type="link" onClick={() => { setEditing(row); setFormOpen(true) }}>编辑</Button>
                  <Popconfirm
                    title="确认删除该规则？"
                    onConfirm={async () => {
                      await deleteRule(row.id)
                      await load()
                    }}
                  >
                    <Button type="link" danger>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Card className="page-card" title="规则测试 / 预览">
        <Form form={testForm} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(180px, 1fr))', gap: 12 }}>
            <Form.Item name="merchant" label="商户"><Input /></Form.Item>
            <Form.Item name="description" label="描述"><Input /></Form.Item>
            <Form.Item name="note" label="备注"><Input /></Form.Item>
            <Form.Item name="external_ref" label="外部单号"><Input /></Form.Item>
            <Form.Item name="account_id" label="账户"><Select allowClear options={accounts.map((x) => ({ label: x.name, value: x.id }))} /></Form.Item>
            <Form.Item name="transaction_type" label="交易类型"><Select allowClear options={[{ label: '收入', value: 'income' }, { label: '支出', value: 'expense' }, { label: '转账', value: 'transfer' }, { label: '退款', value: 'refund' }, { label: '还款', value: 'repayment' }, { label: '手续费', value: 'fee' }, { label: '利息', value: 'interest' }, { label: '调整', value: 'adjustment' }]} /></Form.Item>
            <Form.Item name="direction" label="方向"><Select allowClear options={[{ label: '收入', value: 'income' }, { label: '支出', value: 'expense' }, { label: '中性', value: 'neutral' }]} /></Form.Item>
            <Form.Item name="amount" label="金额"><InputNumber style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="source" label="来源"><Select allowClear options={[{ label: 'manual', value: 'manual' }, { label: 'import_csv', value: 'import_csv' }]} /></Form.Item>
            <Form.Item name="currency" label="币种"><Input /></Form.Item>
          </div>

          <Space>
            <Button
              type="primary"
              loading={previewLoading}
              onClick={async () => {
                const values = testForm.getFieldsValue()
                setPreviewLoading(true)
                try {
                  const payload = await previewRules({ transaction: values, limit: 10 })
                  setPreviewItems(payload.items || [])
                } finally {
                  setPreviewLoading(false)
                }
              }}
            >
              测试规则
            </Button>
            <Button
              onClick={async () => {
                setPreviewLoading(true)
                try {
                  const payload = await previewRules({ source: 'import_csv', limit: 20 })
                  setPreviewItems(payload.items || [])
                } finally {
                  setPreviewLoading(false)
                }
              }}
            >
              预览最近导入流水
            </Button>
          </Space>
        </Form>

        <Table
          style={{ marginTop: 12 }}
          rowKey={(_, idx) => idx}
          size="small"
          loading={previewLoading}
          dataSource={previewItems}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          columns={[
            { title: '交易ID', dataIndex: 'transaction_id', width: 90, render: (v) => v || '-' },
            { title: '命中规则', dataIndex: 'matched_rule_names', render: (v) => (v || []).join(' / ') || '-' },
            { title: '改动字段', dataIndex: 'patched_fields', width: 180, render: (v) => (v || []).join(', ') || '-' },
            { title: '动作摘要', dataIndex: 'applied_actions', render: (v) => (v || []).join('；') || '-' },
          ]}
        />
      </Card>

      <RuleFormModal
        open={formOpen}
        initialValues={editing}
        onCancel={() => setFormOpen(false)}
        onSubmit={async (payload) => {
          setSubmitting(true)
          try {
            if (editing?.id) {
              await updateRule(editing.id, payload)
            } else {
              await createRule(payload)
            }
            setFormOpen(false)
            await load()
            message.success('规则保存成功')
          } finally {
            setSubmitting(false)
          }
        }}
        accounts={accounts}
        categories={categories}
        submitting={submitting}
      />
    </Space>
  )
}
