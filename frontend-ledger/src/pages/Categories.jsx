import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Popconfirm, Select, Space, Table, Tag } from 'antd'
import { createCategory, deleteCategory, listCategories, updateCategory } from '../api/ledger'
import CategoryFormModal from '../components/CategoryFormModal'
import EmptyBlock from '../components/EmptyBlock'
import LoadingBlock from '../components/LoadingBlock'
import PageHeader from '../components/PageHeader'
import { CATEGORY_TYPE_OPTIONS } from '../utils/enums'

const CATEGORY_FILTER_OPTIONS = [
  { label: '全部分类类型', value: 'all' },
  ...CATEGORY_TYPE_OPTIONS,
]

const sortCategoryTree = (rows) => {
  const parents = rows.filter((x) => x.parent_id === null)
  const children = rows.filter((x) => x.parent_id !== null)

  const ordered = []
  parents.forEach((parent) => {
    ordered.push({ ...parent, _level: 0 })
    children
      .filter((child) => child.parent_id === parent.id)
      .forEach((child) => {
        ordered.push({ ...child, _level: 1 })
      })
  })
  return ordered
}

export default function Categories() {
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [rows, setRows] = useState([])
  const [categoryType, setCategoryType] = useState('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const loadCategories = async (type = categoryType) => {
    setLoading(true)
    try {
      const params = type === 'all' ? {} : { category_type: type }
      const res = await listCategories(params)
      setRows(Array.isArray(res?.items) ? res.items : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCategories(categoryType)
  }, [categoryType])

  const sortedRows = useMemo(() => sortCategoryTree(rows), [rows])

  if (loading && !rows.length) {
    return <LoadingBlock />
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="分类管理"
        subtitle="分类管理（两层结构）"
        extra={<Button type="primary" onClick={() => { setEditing(null); setFormOpen(true) }}>新增分类</Button>}
      />

      <Card className="page-card">
        <Select
          value={categoryType}
          onChange={setCategoryType}
          style={{ width: 190 }}
          options={CATEGORY_FILTER_OPTIONS}
        />
      </Card>

      <Card className="page-card">
        {!sortedRows.length ? (
          <EmptyBlock description="暂无分类" />
        ) : (
          <Table
            rowKey="id"
            loading={loading}
            dataSource={sortedRows}
            rowClassName={(row) => (row.is_active ? '' : 'table-muted')}
            columns={[
              {
                title: '名称',
                dataIndex: 'name',
                render: (value, row) => (
                  <span className={row._level === 1 ? 'category-indent' : ''}>
                    {row._level === 1 ? '└ ' : ''}
                    {value}
                  </span>
                ),
              },
              { title: '父级 ID', dataIndex: 'parent_id', width: 90, render: (value) => value || '-' },
              {
                title: '分类类型',
                dataIndex: 'category_type',
                width: 120,
                render: (value) => {
                  const option = CATEGORY_TYPE_OPTIONS.find((x) => x.value === value)
                  const color = value === 'income' ? 'green' : value === 'expense' ? 'red' : 'blue'
                  return <Tag color={color}>{option?.label || value}</Tag>
                },
              },
              { title: '排序', dataIndex: 'sort_order', width: 80 },
              {
                title: '状态',
                dataIndex: 'is_active',
                width: 90,
                render: (value) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag>,
              },
              {
                title: '操作',
                key: 'op',
                width: 170,
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
                      title="确认删除该分类？"
                      onConfirm={async () => {
                        await deleteCategory(row.id)
                        await loadCategories()
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

      <CategoryFormModal
        open={formOpen}
        initialValues={editing}
        categories={rows}
        submitting={submitting}
        onCancel={() => setFormOpen(false)}
        onSubmit={async (payload) => {
          setSubmitting(true)
          try {
            if (editing?.id) {
              await updateCategory(editing.id, payload)
            } else {
              await createCategory(payload)
            }
            setFormOpen(false)
            await loadCategories()
          } finally {
            setSubmitting(false)
          }
        }}
      />
    </Space>
  )
}
