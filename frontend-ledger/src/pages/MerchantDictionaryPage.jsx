import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Input, InputNumber, Modal, Space, Table, Tag, message } from 'antd'
import { listMerchants, updateMerchant } from '../api/ledger'
import PageHeader from '../components/PageHeader'

function toAliasText(arr) {
  if (!Array.isArray(arr)) return ''
  return arr.join('、')
}

function toAliasArray(text) {
  return String(text || '')
    .split(/[、,，\n]/)
    .map((x) => x.trim())
    .filter(Boolean)
}

export default function MerchantDictionaryPage() {
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState([])
  const [keyword, setKeyword] = useState('')
  const [editModal, setEditModal] = useState({ open: false, row: null })
  const [canonicalInput, setCanonicalInput] = useState('')
  const [aliasesInput, setAliasesInput] = useState('')
  const [defaultCategoryInput, setDefaultCategoryInput] = useState(null)
  const [defaultSubcategoryInput, setDefaultSubcategoryInput] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const payload = await listMerchants()
      setRows(Array.isArray(payload?.items) ? payload.items : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return rows
    return rows.filter((row) => {
      const aliases = Array.isArray(row.aliases) ? row.aliases.join(' ') : ''
      const samples = Array.isArray(row.recent_rows) ? row.recent_rows.map((x) => x.merchant_raw || x.raw_text || '').join(' ') : ''
      return `${row.canonical_name} ${aliases} ${samples}`.toLowerCase().includes(kw)
    })
  }, [rows, keyword])

  const openEdit = (row) => {
    setCanonicalInput(row.canonical_name || '')
    setAliasesInput(toAliasText(row.aliases || []))
    setDefaultCategoryInput(row.default_category_id || null)
    setDefaultSubcategoryInput(row.default_subcategory_id || null)
    setEditModal({ open: true, row })
  }

  const saveEdit = async () => {
    const merchantId = editModal?.row?.id
    if (!merchantId) return
    const canonicalName = canonicalInput.trim()
    if (!canonicalName) {
      message.warning('规范商户名不能为空')
      return
    }
    setLoading(true)
    try {
      await updateMerchant(merchantId, {
        canonical_name: canonicalName,
        aliases: toAliasArray(aliasesInput),
        default_category_id: defaultCategoryInput ? Number(defaultCategoryInput) : null,
        default_subcategory_id: defaultSubcategoryInput ? Number(defaultSubcategoryInput) : null,
      })
      message.success('商户词典已更新')
      setEditModal({ open: false, row: null })
      await load()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader title="商户词典" subtitle="支持规范名/别名/默认分类维护，并展示最近关联样本" />

      <Card className="page-card">
        <Input
          allowClear
          placeholder="搜索规范商户名 / 别名 / 最近样本"
          value={keyword}
          style={{ width: 360 }}
          onChange={(e) => setKeyword(e.target.value)}
        />
      </Card>

      <Card className="page-card">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={filtered}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          columns={[
            { title: '规范商户名', dataIndex: 'canonical_name', width: 200 },
            {
              title: '别名',
              dataIndex: 'aliases',
              render: (v) => {
                const arr = Array.isArray(v) ? v : []
                if (!arr.length) return '-'
                return arr.map((item) => <Tag key={item}>{item}</Tag>)
              },
            },
            { title: '默认分类编号', dataIndex: 'default_category_id', width: 120, render: (v) => (v ? `#${v}` : '-') },
            { title: '默认子分类编号', dataIndex: 'default_subcategory_id', width: 140, render: (v) => (v ? `#${v}` : '-') },
            { title: '命中次数', dataIndex: 'hit_count', width: 100 },
            {
              title: '最近关联样本',
              key: 'recent_rows',
              width: 320,
              render: (_, row) => {
                const items = Array.isArray(row.recent_rows) ? row.recent_rows : []
                if (!items.length) return '-'
                return items.map((x) => x.merchant_raw || x.raw_text || '-').filter(Boolean).slice(0, 3).join(' ｜ ')
              },
            },
            {
              title: '操作',
              key: 'op',
              width: 110,
              render: (_, row) => <Button type="link" onClick={() => openEdit(row)}>编辑</Button>,
            },
          ]}
          scroll={{ x: 1200 }}
        />
      </Card>

      <Modal
        title={editModal?.row ? `编辑商户 #${editModal.row.id}` : '编辑商户'}
        open={editModal.open}
        onCancel={() => setEditModal({ open: false, row: null })}
        onOk={saveEdit}
        confirmLoading={loading}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input value={canonicalInput} onChange={(e) => setCanonicalInput(e.target.value)} placeholder="规范商户名" />
          <Input.TextArea
            rows={3}
            value={aliasesInput}
            onChange={(e) => setAliasesInput(e.target.value)}
            placeholder="别名，使用顿号/逗号/换行分隔"
          />
          <InputNumber
            style={{ width: '100%' }}
            min={1}
            value={defaultCategoryInput}
            onChange={setDefaultCategoryInput}
            placeholder="默认分类编号（可选）"
          />
          <InputNumber
            style={{ width: '100%' }}
            min={1}
            value={defaultSubcategoryInput}
            onChange={setDefaultSubcategoryInput}
            placeholder="默认子分类编号（可选）"
          />
        </Space>
      </Modal>
    </Space>
  )
}
