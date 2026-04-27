import { Button, Space, Table, Tag } from 'antd'
import { formatDate } from '../utils/date'

function unresolved(text = '待识别') {
  return <Tag color="error">{text}</Tag>
}

function displayOrPending(value) {
  const text = String(value ?? '').trim()
  return text && text !== '未识别' ? text : '待识别'
}

export default function ReviewTable({
  rows,
  loading,
  selectedRowKeys,
  onSelectionChange,
  onViewDetail,
}) {
  const buildFilters = (items, getter, limit = 120) => {
    const map = new Map()
    for (const row of items || []) {
      const raw = getter(row)
      const value = String(raw == null || raw === '' ? '未识别' : raw).trim()
      if (!value) continue
      map.set(value, Number(map.get(value) || 0) + 1)
    }
    return Array.from(map.entries())
      .sort((a, b) => {
        const cnt = Number(b[1] || 0) - Number(a[1] || 0)
        if (cnt !== 0) return cnt
        return String(a[0]).localeCompare(String(b[0]), 'zh-CN')
      })
      .slice(0, limit)
      .map(([value, count]) => ({
        text: `${value.length > 24 ? `${value.slice(0, 24)}...` : value}（${count}）`,
        value,
      }))
  }

  const filterSearch = (input, option) =>
    String(option?.value || '')
      .toLowerCase()
      .includes(String(input || '').trim().toLowerCase())

  const summaryFilters = buildFilters(rows, (x) => x.raw_text || '待识别')
  const sourceFilters = buildFilters(rows, (x) => displayOrPending(x.source_channel_display))
  const platformFilters = buildFilters(rows, (x) => displayOrPending(x.platform_display))
  const merchantFilters = buildFilters(rows, (x) => displayOrPending(x.merchant_normalized))
  const categoryFilters = buildFilters(rows, (x) => displayOrPending(x.category_name))

  return (
    <Table
      rowKey="id"
      loading={loading}
      dataSource={rows}
      size="small"
      pagination={{ pageSize: 20, showSizeChanger: false }}
      rowSelection={{
        selectedRowKeys,
        onChange: onSelectionChange,
      }}
      rowClassName={(row) => {
        if (row.duplicate_type) return 'review-row-duplicate'
        if (row.review_status === 'pending') return 'review-row-pending'
        return ''
      }}
      columns={[
        { title: '日期', dataIndex: 'occurred_at', width: 120, render: (v) => (v ? formatDate(v) : '-') },
        { title: '金额', dataIndex: 'amount', width: 90, render: (v) => (v == null ? '-' : Number(v).toFixed(2)) },
        {
          title: '原始摘要',
          dataIndex: 'raw_text',
          ellipsis: true,
          render: (v) => v || '-',
          filters: summaryFilters,
          filterSearch,
          onFilter: (value, record) => String(record.raw_text || '未识别') === String(value),
        },
        {
          title: '来源渠道',
          dataIndex: 'source_channel_display',
          width: 110,
          render: (v) => (displayOrPending(v) !== '待识别' ? displayOrPending(v) : unresolved()),
          filters: sourceFilters,
          filterSearch,
          onFilter: (value, record) => displayOrPending(record.source_channel_display) === String(value),
        },
        {
          title: '平台',
          dataIndex: 'platform_display',
          width: 100,
          render: (v) => (displayOrPending(v) !== '待识别' ? displayOrPending(v) : unresolved()),
          filters: platformFilters,
          filterSearch,
          onFilter: (value, record) => displayOrPending(record.platform_display) === String(value),
        },
        {
          title: '商户归一',
          dataIndex: 'merchant_normalized',
          width: 130,
          render: (v) => (displayOrPending(v) !== '待识别' ? displayOrPending(v) : unresolved()),
          filters: merchantFilters,
          filterSearch,
          onFilter: (value, record) => displayOrPending(record.merchant_normalized) === String(value),
        },
        {
          title: '建议分类',
          dataIndex: 'category_name',
          width: 120,
          render: (v) => (displayOrPending(v) !== '待识别' ? displayOrPending(v) : unresolved()),
          filters: categoryFilters,
          filterSearch,
          onFilter: (value, record) => displayOrPending(record.category_name) === String(value),
        },
        { title: '置信度', dataIndex: 'confidence', width: 90, render: (v) => Number(v || 0).toFixed(2) },
        {
          title: '操作',
          key: 'op',
          fixed: 'right',
          width: 100,
          render: (_, row) => (
            <Space>
              <Button type="link" onClick={() => onViewDetail?.(row)}>详情</Button>
            </Space>
          ),
        },
      ]}
      scroll={{ x: 1400 }}
    />
  )
}
