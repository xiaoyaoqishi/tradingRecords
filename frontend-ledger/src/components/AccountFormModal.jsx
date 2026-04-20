import { Form, Input, InputNumber, Modal, Select, Switch } from 'antd'
import { useEffect } from 'react'
import { ACCOUNT_TYPE_OPTIONS, CURRENCY_OPTIONS } from '../utils/enums'

export default function AccountFormModal({ open, initialValues, onCancel, onSubmit, submitting }) {
  const [form] = Form.useForm()

  useEffect(() => {
    if (!open) return
    form.setFieldsValue({
      name: '',
      account_type: 'cash',
      currency: 'CNY',
      initial_balance: 0,
      is_active: true,
      notes: '',
      ...initialValues,
    })
  }, [open, initialValues, form])

  return (
    <Modal
      title={initialValues?.id ? '编辑账户' : '新建账户'}
      open={open}
      onCancel={onCancel}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      destroyOnHidden
    >
      <Form
        layout="vertical"
        form={form}
        onFinish={(values) => {
          onSubmit({
            ...values,
            name: values.name?.trim(),
            notes: values.notes?.trim() || null,
          })
        }}
      >
        <Form.Item name="name" label="账户名称" rules={[{ required: true, message: '请输入账户名称' }]}>
          <Input maxLength={120} />
        </Form.Item>
        <Form.Item name="account_type" label="账户类型" rules={[{ required: true, message: '请选择账户类型' }]}>
          <Select options={ACCOUNT_TYPE_OPTIONS} />
        </Form.Item>
        <Form.Item name="currency" label="币种" rules={[{ required: true, message: '请选择币种' }]}>
          <Select options={CURRENCY_OPTIONS} />
        </Form.Item>
        <Form.Item name="initial_balance" label="初始余额" rules={[{ required: true, message: '请输入初始余额' }]}>
          <InputNumber style={{ width: '100%' }} precision={2} />
        </Form.Item>
        <Form.Item name="is_active" label="启用" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="notes" label="备注">
          <Input.TextArea rows={3} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
