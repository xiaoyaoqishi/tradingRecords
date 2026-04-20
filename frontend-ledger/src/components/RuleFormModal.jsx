import { Form, Input, InputNumber, Modal, Select, Space, Switch, Typography, message } from 'antd'
import { useEffect, useMemo } from 'react'
import RuleActionSummary from './RuleActionSummary'
import RuleMatchSummary from './RuleMatchSummary'

function splitValues(text) {
  const v = String(text || '').trim()
  if (!v) return undefined
  const parts = v.split(',').map((x) => x.trim()).filter(Boolean)
  return parts.length <= 1 ? parts[0] : parts
}

export default function RuleFormModal({ open, initialValues, onCancel, onSubmit, accounts, categories, submitting }) {
  const [form] = Form.useForm()

  useEffect(() => {
    if (!open) return
    const iv = initialValues || {}
    form.setFieldsValue({
      name: iv.name || '',
      is_active: iv.is_active !== false,
      priority: iv.priority ?? 100,
      merchant_contains: Array.isArray(iv.match_json?.merchant_contains) ? iv.match_json?.merchant_contains.join(', ') : (iv.match_json?.merchant_contains || ''),
      description_contains: Array.isArray(iv.match_json?.description_contains) ? iv.match_json?.description_contains.join(', ') : (iv.match_json?.description_contains || ''),
      note_contains: Array.isArray(iv.match_json?.note_contains) ? iv.match_json?.note_contains.join(', ') : (iv.match_json?.note_contains || ''),
      external_ref_contains: Array.isArray(iv.match_json?.external_ref_contains) ? iv.match_json?.external_ref_contains.join(', ') : (iv.match_json?.external_ref_contains || ''),
      account_id: iv.match_json?.account_id,
      transaction_type: iv.match_json?.transaction_type,
      direction: iv.match_json?.direction,
      amount_eq: iv.match_json?.amount_eq,
      amount_gte: iv.match_json?.amount_gte,
      amount_lte: iv.match_json?.amount_lte,
      source: iv.match_json?.source,
      currency: iv.match_json?.currency,
      set_category_id: iv.action_json?.set_category_id,
      set_transaction_type: iv.action_json?.set_transaction_type,
      set_direction: iv.action_json?.set_direction,
      set_merchant: iv.action_json?.set_merchant,
      append_note: iv.action_json?.append_note,
      set_is_cleared: iv.action_json?.set_is_cleared,
    })
  }, [open, initialValues, form])

  const values = Form.useWatch([], form) || {}

  const matchPreview = useMemo(() => ({
    merchant_contains: splitValues(values.merchant_contains),
    description_contains: splitValues(values.description_contains),
    note_contains: splitValues(values.note_contains),
    external_ref_contains: splitValues(values.external_ref_contains),
    account_id: values.account_id,
    transaction_type: values.transaction_type,
    direction: values.direction,
    amount_eq: values.amount_eq,
    amount_gte: values.amount_gte,
    amount_lte: values.amount_lte,
    source: values.source,
    currency: values.currency,
  }), [values])

  const actionPreview = useMemo(() => ({
    set_category_id: values.set_category_id,
    set_transaction_type: values.set_transaction_type,
    set_direction: values.set_direction,
    set_merchant: values.set_merchant,
    append_note: values.append_note,
    set_is_cleared: values.set_is_cleared,
  }), [values])

  return (
    <Modal
      title={initialValues?.id ? '编辑规则' : '新建规则'}
      open={open}
      onCancel={onCancel}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      width={980}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={(v) => {
          const match_json = {
            merchant_contains: splitValues(v.merchant_contains),
            description_contains: splitValues(v.description_contains),
            note_contains: splitValues(v.note_contains),
            external_ref_contains: splitValues(v.external_ref_contains),
            account_id: v.account_id,
            transaction_type: v.transaction_type,
            direction: v.direction,
            amount_eq: v.amount_eq,
            amount_gte: v.amount_gte,
            amount_lte: v.amount_lte,
            source: v.source,
            currency: v.currency,
          }
          const action_json = {
            set_category_id: v.set_category_id,
            set_transaction_type: v.set_transaction_type,
            set_direction: v.set_direction,
            set_merchant: v.set_merchant,
            append_note: v.append_note,
            set_is_cleared: v.set_is_cleared,
          }

          const cleanedMatch = Object.fromEntries(Object.entries(match_json).filter(([, val]) => val !== undefined && val !== null && val !== ''))
          const cleanedAction = Object.fromEntries(Object.entries(action_json).filter(([, val]) => val !== undefined && val !== null && val !== ''))

          if (!Object.keys(cleanedMatch).length) {
            message.warning('至少配置一个匹配条件')
            return
          }
          if (!Object.keys(cleanedAction).length) {
            message.warning('至少配置一个动作')
            return
          }

          onSubmit({
            name: v.name.trim(),
            is_active: v.is_active,
            priority: v.priority,
            match_json: cleanedMatch,
            action_json: cleanedAction,
          })
        }}
      >
        <Space style={{ width: '100%' }} align="start" size={12}>
          <Form.Item name="name" label="规则名称" rules={[{ required: true, message: '请输入规则名称' }]} style={{ flex: 2 }}>
            <Input maxLength={120} />
          </Form.Item>
          <Form.Item name="priority" label="优先级（越小越先）" style={{ width: 180 }}>
            <InputNumber min={0} max={9999} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked" style={{ width: 120 }}>
            <Switch />
          </Form.Item>
        </Space>

        <Typography.Title level={5}>条件区（AND）</Typography.Title>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(220px, 1fr))', gap: 12 }}>
          <Form.Item name="merchant_contains" label="商户包含"><Input placeholder="可逗号分隔" /></Form.Item>
          <Form.Item name="description_contains" label="描述包含"><Input placeholder="可逗号分隔" /></Form.Item>
          <Form.Item name="note_contains" label="备注包含"><Input placeholder="可逗号分隔" /></Form.Item>
          <Form.Item name="external_ref_contains" label="外部单号包含"><Input placeholder="可逗号分隔" /></Form.Item>
          <Form.Item name="account_id" label="账户"><Select allowClear options={(accounts || []).map((x) => ({ label: x.name, value: x.id }))} /></Form.Item>
          <Form.Item name="transaction_type" label="交易类型"><Select allowClear options={[{ label: '收入', value: 'income' }, { label: '支出', value: 'expense' }, { label: '转账', value: 'transfer' }, { label: '退款', value: 'refund' }, { label: '还款', value: 'repayment' }, { label: '手续费', value: 'fee' }, { label: '利息', value: 'interest' }, { label: '调整', value: 'adjustment' }]} /></Form.Item>
          <Form.Item name="direction" label="方向"><Select allowClear options={[{ label: '收入', value: 'income' }, { label: '支出', value: 'expense' }, { label: '中性', value: 'neutral' }]} /></Form.Item>
          <Form.Item name="amount_eq" label="金额等于"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="amount_gte" label="金额大于等于"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="amount_lte" label="金额小于等于"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="source" label="来源"><Select allowClear options={[{ label: 'manual', value: 'manual' }, { label: 'import_csv', value: 'import_csv' }]} /></Form.Item>
          <Form.Item name="currency" label="币种"><Input /></Form.Item>
        </div>

        <Typography.Title level={5}>动作区</Typography.Title>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(220px, 1fr))', gap: 12 }}>
          <Form.Item name="set_category_id" label="设置分类"><Select allowClear options={(categories || []).map((x) => ({ label: x.name, value: x.id }))} /></Form.Item>
          <Form.Item name="set_transaction_type" label="设置交易类型"><Select allowClear options={[{ label: '收入', value: 'income' }, { label: '支出', value: 'expense' }, { label: '转账', value: 'transfer' }, { label: '退款', value: 'refund' }, { label: '还款', value: 'repayment' }, { label: '手续费', value: 'fee' }, { label: '利息', value: 'interest' }, { label: '调整', value: 'adjustment' }]} /></Form.Item>
          <Form.Item name="set_direction" label="设置方向"><Select allowClear options={[{ label: '收入', value: 'income' }, { label: '支出', value: 'expense' }, { label: '中性', value: 'neutral' }]} /></Form.Item>
          <Form.Item name="set_merchant" label="标准商户名"><Input /></Form.Item>
          <Form.Item name="append_note" label="追加备注"><Input /></Form.Item>
          <Form.Item name="set_is_cleared" label="设置已清算"><Select allowClear options={[{ label: '是', value: true }, { label: '否', value: false }]} /></Form.Item>
        </div>

        <Typography.Paragraph type="secondary" style={{ marginBottom: 4 }}>
          条件摘要：<RuleMatchSummary matchJson={matchPreview} />
        </Typography.Paragraph>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          动作摘要：<RuleActionSummary actionJson={actionPreview} />
        </Typography.Paragraph>
      </Form>
    </Modal>
  )
}
