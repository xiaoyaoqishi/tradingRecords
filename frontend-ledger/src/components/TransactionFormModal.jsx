import { Button, Checkbox, DatePicker, Form, Input, InputNumber, Modal, Select, Space } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useMemo, useState } from 'react'
import { CURRENCY_OPTIONS, DIRECTION_OPTIONS, TRANSACTION_TYPE_OPTIONS } from '../utils/enums'
import { inferDirectionByTransactionType } from '../utils/ledger'

export default function TransactionFormModal({
  open,
  mode,
  initialValues,
  accounts,
  categories,
  onCancel,
  onSubmit,
}) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const txType = Form.useWatch('transaction_type', form)

  const categoryOptions = useMemo(() => {
    if (txType === 'income') {
      return (categories || []).filter((x) => x.category_type === 'income' || x.category_type === 'both')
    }
    if (txType === 'expense' || txType === 'fee' || txType === 'repayment') {
      return (categories || []).filter((x) => x.category_type === 'expense' || x.category_type === 'both')
    }
    return categories || []
  }, [categories, txType])

  useEffect(() => {
    if (!open) return
    const defaults = {
      occurred_at: dayjs(),
      posted_date: dayjs(),
      account_id: undefined,
      counterparty_account_id: undefined,
      category_id: undefined,
      direction: 'expense',
      transaction_type: 'expense',
      amount: undefined,
      currency: 'CNY',
      merchant: '',
      description: '',
      note: '',
      external_ref: '',
      is_cleared: false,
      apply_rules: true,
    }
    const merged = {
      ...defaults,
      ...initialValues,
      occurred_at: initialValues?.occurred_at ? dayjs(initialValues.occurred_at) : defaults.occurred_at,
      posted_date: initialValues?.posted_date ? dayjs(initialValues.posted_date) : defaults.posted_date,
    }
    form.setFieldsValue(merged)
  }, [open, initialValues, form])

  useEffect(() => {
    if (!open) return
    if (!txType) return
    if (txType === 'transfer') {
      form.setFieldValue('direction', 'neutral')
      form.setFieldValue('category_id', undefined)
      return
    }
    if (txType === 'refund') {
      form.setFieldValue('direction', 'income')
      return
    }
    const inferred = inferDirectionByTransactionType(txType)
    if (inferred) {
      form.setFieldValue('direction', inferred)
    }
  }, [txType, form, open])

  const submitWithMode = async (saveMode) => {
    try {
      const values = await form.validateFields()
      const payload = {
        ...values,
        occurred_at: values.occurred_at?.format('YYYY-MM-DDTHH:mm:ss'),
        posted_date: values.posted_date?.format('YYYY-MM-DD') || null,
        account_id: Number(values.account_id),
        counterparty_account_id: values.counterparty_account_id ? Number(values.counterparty_account_id) : null,
        category_id: values.category_id ? Number(values.category_id) : null,
        merchant: values.merchant?.trim() || null,
        description: values.description?.trim() || null,
        note: values.note?.trim() || null,
          external_ref: values.external_ref?.trim() || null,
        }
      setSubmitting(true)
      await onSubmit(payload, { saveMode })
      if (saveMode === 'continue') {
        form.setFieldsValue({
          occurred_at: dayjs(),
          posted_date: dayjs(),
          amount: undefined,
          merchant: '',
          description: '',
          note: '',
          external_ref: '',
          category_id: undefined,
          counterparty_account_id: undefined,
          apply_rules: true,
        })
      }
    } finally {
      setSubmitting(false)
    }
  }

  const isTransfer = txType === 'transfer'
  const directionDisabled = isTransfer || txType === 'refund'

  return (
    <Modal
      title={mode === 'edit' ? '编辑流水' : '新增流水'}
      open={open}
      onCancel={onCancel}
      footer={null}
      width={920}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Space size={12} style={{ width: '100%' }} align="start">
          <Form.Item
            name="occurred_at"
            label="发生时间"
            rules={[{ required: true, message: '请选择发生时间' }]}
            style={{ width: '100%' }}
          >
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="posted_date" label="入账日期" style={{ width: '100%' }}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Space>

        <Space size={12} style={{ width: '100%' }} align="start">
          <Form.Item
            name="transaction_type"
            label="流水类型"
            rules={[{ required: true, message: '请选择流水类型' }]}
            style={{ width: '100%' }}
          >
            <Select options={TRANSACTION_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item
            name="direction"
            label="方向"
            rules={[{ required: true, message: '请选择方向' }]}
            style={{ width: '100%' }}
          >
            <Select options={DIRECTION_OPTIONS} disabled={directionDisabled} />
          </Form.Item>
        </Space>

        <Space size={12} style={{ width: '100%' }} align="start">
          <Form.Item
            name="account_id"
            label="账户"
            rules={[{ required: true, message: '请选择账户' }]}
            style={{ width: 420 }}
          >
            <Select
              showSearch
              optionFilterProp="label"
              options={(accounts || []).map((x) => ({ label: x.name, value: x.id }))}
            />
          </Form.Item>
          <Form.Item
            name="counterparty_account_id"
            label="对方账户"
            rules={[
              {
                validator: async (_, value) => {
                  const accountId = form.getFieldValue('account_id')
                  if (isTransfer && !value) throw new Error('转账必须选择对方账户')
                  if (isTransfer && accountId && Number(accountId) === Number(value)) {
                    throw new Error('转出和转入账户不能相同')
                  }
                },
              },
            ]}
            style={{ width: 420 }}
          >
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder={isTransfer ? '转账必填' : '可选'}
              options={(accounts || []).map((x) => ({ label: x.name, value: x.id }))}
            />
          </Form.Item>
        </Space>

        <Space size={12} style={{ width: '100%' }} align="start">
          <Form.Item
            name="category_id"
            label="分类"
            rules={[
              {
                validator: async (_, value) => {
                  if (isTransfer) return
                  if (txType === 'expense' && !value) throw new Error('支出流水必须选择分类')
                },
              },
            ]}
            style={{ width: 420 }}
          >
            <Select
              allowClear
              disabled={isTransfer}
              options={categoryOptions.map((x) => ({ label: x.name, value: x.id }))}
              placeholder={isTransfer ? '转账无需分类' : '可选'}
            />
          </Form.Item>
          <Form.Item
            name="amount"
            label="金额"
            rules={[{ required: true, message: '请输入金额' }, { type: 'number', min: 0.01, message: '金额必须大于 0' }]}
            style={{ width: '100%' }}
          >
            <InputNumber min={0.01} precision={2} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="currency"
            label="币种"
            rules={[{ required: true, message: '请选择币种' }]}
            style={{ width: '100%' }}
          >
            <Select options={CURRENCY_OPTIONS} />
          </Form.Item>
        </Space>

        <Space size={12} style={{ width: '100%' }} align="start">
          <Form.Item name="merchant" label="商户" style={{ width: '100%' }}>
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="external_ref" label="外部单号" style={{ width: '100%' }}>
            <Input maxLength={120} />
          </Form.Item>
        </Space>

        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="note" label="备注">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="is_cleared" valuePropName="checked">
          <Checkbox>已清算</Checkbox>
        </Form.Item>
        <Form.Item name="apply_rules" valuePropName="checked">
          <Checkbox>保存时应用规则</Checkbox>
        </Form.Item>

        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onCancel}>取消</Button>
          {mode === 'create' ? (
            <Button loading={submitting} onClick={() => submitWithMode('continue')}>
              保存并继续新增
            </Button>
          ) : null}
          <Button type="primary" loading={submitting} onClick={() => submitWithMode('close')}>
            保存
          </Button>
        </Space>
      </Form>
    </Modal>
  )
}
