import { Form, Input, InputNumber, Modal, Select, Switch } from 'antd'
import { useEffect, useMemo } from 'react'
import { CATEGORY_TYPE_OPTIONS } from '../utils/enums'

export default function CategoryFormModal({
  open,
  initialValues,
  categories,
  onCancel,
  onSubmit,
  submitting,
}) {
  const [form] = Form.useForm()

  const parentOptions = useMemo(() => {
    const selfId = initialValues?.id
    return (categories || [])
      .filter((x) => x.parent_id === null && (!selfId || x.id !== selfId))
      .map((x) => ({ label: x.name, value: x.id }))
  }, [categories, initialValues])

  useEffect(() => {
    if (!open) return
    form.setFieldsValue({
      name: '',
      parent_id: null,
      category_type: 'expense',
      sort_order: 0,
      is_active: true,
      ...initialValues,
    })
  }, [open, initialValues, form])

  return (
    <Modal
      title={initialValues?.id ? '编辑分类' : '新建分类'}
      open={open}
      onCancel={onCancel}
      onOk={() => form.submit()}
      confirmLoading={submitting}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => {
          onSubmit({
            ...values,
            parent_id: values.parent_id || null,
            name: values.name?.trim(),
          })
        }}
      >
        <Form.Item name="name" label="分类名称" rules={[{ required: true, message: '请输入分类名称' }]}>
          <Input maxLength={120} />
        </Form.Item>
        <Form.Item name="parent_id" label="父分类">
          <Select allowClear options={parentOptions} placeholder="无（作为一级分类）" />
        </Form.Item>
        <Form.Item name="category_type" label="分类类型" rules={[{ required: true, message: '请选择分类类型' }]}>
          <Select options={CATEGORY_TYPE_OPTIONS} />
        </Form.Item>
        <Form.Item name="sort_order" label="排序">
          <InputNumber style={{ width: '100%' }} precision={0} />
        </Form.Item>
        <Form.Item name="is_active" label="启用" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}
