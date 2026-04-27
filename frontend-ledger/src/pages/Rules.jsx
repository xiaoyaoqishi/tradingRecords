import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from 'antd'
import { createRule, deleteRule, listRules, updateRule } from '../api/ledger'
import PageHeader from '../components/PageHeader'

const RULE_TYPE_OPTIONS = [
  { label: '来源识别', value: 'source' },
  { label: '商户归一', value: 'merchant' },
  { label: '分类', value: 'category' },
]

const MATCH_MODE_OPTIONS = [
  { label: '包含', value: 'contains' },
  { label: '前缀', value: 'prefix' },
  { label: '完全匹配', value: 'exact' },
  { label: '正则', value: 'regex' },
]

const RULE_FORM_HELP = [
  { key: '规则类型', text: '决定规则作用：来源识别用于补全来源信息，商户归一用于统一商户名，分类用于自动落分类。通常先建商户归一，再建分类。' },
  { key: '优先级', text: '数字越小越先执行。建议：通用规则用 100+，强约束规则用 1-50。' },
  { key: '启用', text: '关闭后规则保留但不生效。建议先关闭调试，再开启上线。' },
  { key: '置信度', text: '表示该规则结果可信度，范围 0-1。建议常规填 0.7-0.95。' },
  { key: '匹配方式', text: '包含适合关键词；前缀适合固定开头；完全匹配最严格；正则适合复杂模式。' },
  { key: '匹配文本', text: '要匹配的关键内容。建议先用短关键词验证，再逐步加长。' },
  { key: '来源条件', text: '限制来源渠道（如微信、支付宝）。留空表示不限。' },
  { key: '平台条件', text: '限制交易平台（如美团、拼多多）。留空表示不限。' },
  { key: '方向条件', text: '限制收入/支出方向。留空表示不限制。' },
  { key: '金额下限', text: '匹配金额最小值。可用于屏蔽小额噪声。' },
  { key: '金额上限', text: '匹配金额最大值。与金额下限组合形成区间。' },
  { key: '目标平台', text: '规则命中后回填的平台名称。通常用于来源识别规则。' },
  { key: '目标商户', text: '规则命中后统一成的商户名。通常用于商户归一规则。' },
  { key: '目标交易类型', text: '规则命中后设置的交易类型（例如支出、转账）。留空则不改。' },
  { key: '目标场景', text: '规则命中后设置的消费场景（如餐饮、购物）。' },
  { key: '目标分类编号', text: '规则命中后写入的分类编号。建议与分类管理中的编号保持一致。' },
  { key: '目标子分类编号', text: '可选。用于更细颗粒度分类。' },
  { key: '说明', text: '给规则写备注，建议写“规则目的 + 适用范围”。' },
]

function ruleTypeText(v) {
  if (v === 'source') return '来源识别'
  if (v === 'merchant') return '商户归一'
  if (v === 'category') return '分类'
  return v || '-'
}

function matchModeText(v) {
  if (v === 'contains') return '包含'
  if (v === 'prefix') return '前缀'
  if (v === 'exact') return '完全匹配'
  if (v === 'regex') return '正则'
  return v || '-'
}

function buildTargetSummary(row) {
  if (row.rule_type === 'source') {
    return [row.target_platform, row.target_txn_kind, row.target_scene].filter(Boolean).join(' / ') || '-'
  }
  if (row.rule_type === 'merchant') {
    return row.target_merchant || '-'
  }
  return [row.target_scene, row.target_category_id ? `分类#${row.target_category_id}` : null].filter(Boolean).join(' / ') || '-'
}

function formatTime(v) {
  if (!v) return '-'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleString('zh-CN', { hour12: false })
}

export default function Rules() {
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState([])
  const [keyword, setKeyword] = useState('')
  const [ruleTypeFilter, setRuleTypeFilter] = useState('all')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const payload = await listRules()
      setRows(Array.isArray(payload?.items) ? payload.items : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filteredRows = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    return rows.filter((x) => {
      if (ruleTypeFilter !== 'all' && x.rule_type !== ruleTypeFilter) return false
      if (!kw) return true
      const text = [x.pattern, x.explain_text, x.target_merchant, x.target_scene].filter(Boolean).join(' ').toLowerCase()
      return text.includes(kw)
    })
  }, [rows, keyword, ruleTypeFilter])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({
      rule_type: 'category',
      priority: 100,
      enabled: true,
      match_mode: 'contains',
      confidence_score: 0.7,
    })
    setModalOpen(true)
  }

  const openEdit = (row) => {
    setEditing(row)
    form.setFieldsValue({
      rule_type: row.rule_type,
      priority: row.priority,
      enabled: row.enabled,
      match_mode: row.match_mode,
      pattern: row.pattern,
      source_channel_condition: row.source_channel_condition,
      platform_condition: row.platform_condition,
      direction_condition: row.direction_condition,
      amount_min: row.amount_min,
      amount_max: row.amount_max,
      target_platform: row.target_platform,
      target_merchant: row.target_merchant,
      target_txn_kind: row.target_txn_kind,
      target_scene: row.target_scene,
      target_category_id: row.target_category_id,
      target_subcategory_id: row.target_subcategory_id,
      explain_text: row.explain_text,
      confidence_score: row.confidence_score,
    })
    setModalOpen(true)
  }

  const submit = async () => {
    const v = await form.validateFields()
    setSubmitting(true)
    try {
      if (editing?.id) {
        await updateRule(editing.id, v)
        message.success('规则已更新')
      } else {
        await createRule(v)
        message.success('规则已新增')
      }
      setModalOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="规则管理"
        subtitle="管理来源识别、商户归一、分类规则（支持新增/编辑/删除）"
        extra={<Button type="primary" onClick={openCreate}>新增规则</Button>}
      />

      <div className="filter-bar">
        <Space wrap>
          <Input
            allowClear
            placeholder="搜索匹配文本 / 说明 / 目标"
            style={{ width: 280 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <Select
            style={{ width: 170 }}
            value={ruleTypeFilter}
            onChange={setRuleTypeFilter}
            options={[{ label: '全部类型', value: 'all' }, ...RULE_TYPE_OPTIONS]}
          />
          <Button onClick={load} loading={loading}>刷新</Button>
        </Space>
      </div>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={filteredRows}
        pagination={{ pageSize: 20, showSizeChanger: false }}
        columns={[
          { title: '编号', dataIndex: 'id', width: 70 },
          {
            title: '规则类型',
            dataIndex: 'rule_type',
            width: 110,
            render: (v) => <Tag color={v === 'source' ? 'blue' : v === 'merchant' ? 'green' : 'purple'}>{ruleTypeText(v)}</Tag>,
          },
          { title: '优先级', dataIndex: 'priority', width: 90 },
          { title: '是否启用', dataIndex: 'enabled', width: 90, render: (v) => (v ? '是' : '否') },
          { title: '匹配方式', dataIndex: 'match_mode', width: 100, render: (v) => matchModeText(v) },
          { title: '匹配文本', dataIndex: 'pattern', ellipsis: true },
          { title: '目标结果', key: 'target', width: 220, render: (_, row) => buildTargetSummary(row) },
          { title: '命中次数', dataIndex: 'hit_count', width: 95, render: (v) => Number(v || 0) },
          { title: '最近命中时间', dataIndex: 'last_hit_at', width: 170, render: (v) => formatTime(v) },
          { title: '说明', dataIndex: 'explain_text', ellipsis: true },
          {
            title: '操作',
            key: 'op',
            width: 180,
            render: (_, row) => (
              <Space>
                <Button type="link" onClick={() => openEdit(row)}>编辑</Button>
                <Popconfirm
                  title="确认删除该规则？"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={async () => {
                    await deleteRule(row.id)
                    message.success('规则已删除')
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

      <Modal
        title={editing ? `编辑规则 #${editing.id}` : '新增规则'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={submit}
        confirmLoading={submitting}
        width={880}
        destroyOnClose
      >
        <Alert
          style={{ marginBottom: 12 }}
          type="info"
          showIcon
          message="填写建议"
          description={
            <div>
              {RULE_FORM_HELP.map((item) => (
                <div key={item.key}><strong>{item.key}：</strong>{item.text}</div>
              ))}
            </div>
          }
        />
        <Form form={form} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(160px, 1fr))', gap: 12 }}>
            <Form.Item label="规则类型" name="rule_type" rules={[{ required: true, message: '请选择规则类型' }]}> 
              <Select options={RULE_TYPE_OPTIONS} />
            </Form.Item>
            <Form.Item label="优先级" name="priority" rules={[{ required: true, message: '请输入优先级' }]}> 
              <InputNumber min={0} max={9999} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="启用" name="enabled" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="置信度" name="confidence_score">
              <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item label="匹配方式" name="match_mode" rules={[{ required: true, message: '请选择匹配方式' }]}> 
              <Select options={MATCH_MODE_OPTIONS} />
            </Form.Item>
            <Form.Item label="匹配文本" name="pattern" rules={[{ required: true, message: '请输入匹配文本' }]}> 
              <Input />
            </Form.Item>
            <Form.Item label="来源条件" name="source_channel_condition">
              <Input placeholder="例如：微信" />
            </Form.Item>
            <Form.Item label="平台条件" name="platform_condition">
              <Input placeholder="例如：美团" />
            </Form.Item>

            <Form.Item label="方向条件" name="direction_condition">
              <Input placeholder="收入 或 支出" />
            </Form.Item>
            <Form.Item label="金额下限" name="amount_min">
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="金额上限" name="amount_max">
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="目标平台" name="target_platform">
              <Input placeholder="例如：微信" />
            </Form.Item>

            <Form.Item label="目标商户" name="target_merchant">
              <Input />
            </Form.Item>
            <Form.Item label="目标交易类型" name="target_txn_kind">
              <Input placeholder="例如：支出" />
            </Form.Item>
            <Form.Item label="目标场景" name="target_scene">
              <Input placeholder="例如：餐饮" />
            </Form.Item>
            <Form.Item label="目标分类编号" name="target_category_id">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item label="目标子分类编号" name="target_subcategory_id">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item label="说明" name="explain_text">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  )
}
