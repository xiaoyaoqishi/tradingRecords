import { Card, Checkbox, Form, Input, Select, Space, Typography } from 'antd'

const DEFAULT_FIELD_OPTIONS = [
  { key: 'occurred_at', label: '发生时间 occurred_at' },
  { key: 'posted_date', label: '入账日期 posted_date' },
  { key: 'amount', label: '金额 amount' },
  { key: 'transaction_type', label: '交易类型 transaction_type' },
  { key: 'direction', label: '方向 direction' },
  { key: 'account_name', label: '账户名称 account_name' },
  { key: 'category_name', label: '分类名称 category_name' },
  { key: 'merchant', label: '商户 merchant' },
  { key: 'description', label: '描述 description' },
  { key: 'note', label: '备注 note' },
  { key: 'external_ref', label: '外部单号 external_ref' },
]

export default function ImportMappingTable({
  mapping,
  onMappingChange,
  columns,
  defaults,
  onDefaultsChange,
  accounts,
  applyRules,
  onApplyRulesChange,
}) {
  const columnOptions = (columns || []).map((x) => ({ label: x, value: x }))

  return (
    <Card className="page-card" title="2. 字段映射与默认值">
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Typography.Text type="secondary">将 CSV 列映射到系统字段，未映射字段可使用默认值。</Typography.Text>
        <Form layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(260px, 1fr))', gap: 12 }}>
            {DEFAULT_FIELD_OPTIONS.map((item) => (
              <Form.Item key={item.key} label={item.label} style={{ marginBottom: 8 }}>
                <Select
                  allowClear
                  placeholder="选择 CSV 列"
                  value={mapping[item.key] || undefined}
                  options={columnOptions}
                  onChange={(value) => onMappingChange({ ...mapping, [item.key]: value || '' })}
                />
              </Form.Item>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(260px, 1fr))', gap: 12 }}>
            <Form.Item label="默认账户" style={{ marginBottom: 8 }}>
              <Select
                allowClear
                placeholder="当 CSV 没有账户字段时使用"
                value={defaults.default_account_id || undefined}
                options={(accounts || []).map((x) => ({ label: x.name, value: x.id }))}
                onChange={(value) => onDefaultsChange({ ...defaults, default_account_id: value || null })}
              />
            </Form.Item>
            <Form.Item label="默认币种" style={{ marginBottom: 8 }}>
              <Input
                value={defaults.default_currency}
                onChange={(e) => onDefaultsChange({ ...defaults, default_currency: e.target.value || 'CNY' })}
              />
            </Form.Item>
            <Form.Item label="默认交易类型" style={{ marginBottom: 8 }}>
              <Select
                allowClear
                value={defaults.default_transaction_type || undefined}
                options={[
                  { label: '收入', value: 'income' },
                  { label: '支出', value: 'expense' },
                  { label: '转账', value: 'transfer' },
                  { label: '退款', value: 'refund' },
                  { label: '还款', value: 'repayment' },
                  { label: '手续费', value: 'fee' },
                  { label: '利息', value: 'interest' },
                  { label: '调整', value: 'adjustment' },
                ]}
                onChange={(value) => onDefaultsChange({ ...defaults, default_transaction_type: value || null })}
              />
            </Form.Item>
            <Form.Item label="默认方向" style={{ marginBottom: 8 }}>
              <Select
                allowClear
                value={defaults.default_direction || undefined}
                options={[
                  { label: '收入', value: 'income' },
                  { label: '支出', value: 'expense' },
                  { label: '中性', value: 'neutral' },
                ]}
                onChange={(value) => onDefaultsChange({ ...defaults, default_direction: value || null })}
              />
            </Form.Item>
            <Form.Item label="规则执行" style={{ marginBottom: 8 }}>
              <Checkbox checked={applyRules} onChange={(e) => onApplyRulesChange(e.target.checked)}>
                预览与提交时应用自动分类规则
              </Checkbox>
            </Form.Item>
          </div>
        </Form>
      </Space>
    </Card>
  )
}
