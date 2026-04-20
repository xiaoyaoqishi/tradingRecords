import { Card, Table, Tag } from 'antd'
import { formatDateTime } from '../utils/date'

const statusColor = {
  valid: 'green',
  duplicate: 'gold',
  invalid: 'red',
}

const statusText = {
  valid: '有效',
  duplicate: '重复',
  invalid: '无效',
}

export default function ImportPreviewTable({ rows, loading }) {
  return (
    <Card className="page-card" title="3. 预览结果">
      <Table
        rowKey={(row) => row.row_no}
        loading={loading}
        size="small"
        scroll={{ x: 1280 }}
        dataSource={rows || []}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        columns={[
          { title: '行号', dataIndex: 'row_no', width: 80 },
          {
            title: '状态',
            dataIndex: 'status',
            width: 100,
            render: (value) => <Tag color={statusColor[value] || 'default'}>{statusText[value] || value}</Tag>,
          },
          {
            title: '发生时间',
            key: 'occurred_at',
            width: 180,
            render: (_, row) => formatDateTime(row?.record?.occurred_at),
          },
          { title: '账户ID', key: 'account_id', width: 90, render: (_, row) => row?.record?.account_id || '-' },
          { title: '分类ID', key: 'category_id', width: 90, render: (_, row) => row?.record?.category_id || '-' },
          { title: '类型', key: 'transaction_type', width: 120, render: (_, row) => row?.record?.transaction_type || '-' },
          { title: '方向', key: 'direction', width: 90, render: (_, row) => row?.record?.direction || '-' },
          { title: '金额', key: 'amount', width: 120, render: (_, row) => row?.record?.amount || '-' },
          { title: '商户', key: 'merchant', width: 140, render: (_, row) => row?.record?.merchant || '-' },
          {
            title: '规则命中',
            key: 'matched_rules',
            width: 240,
            render: (_, row) => {
              const names = row?.matched_rules?.names || []
              const fields = row?.patched_fields || []
              if (!names.length && !fields.length) return '-'
              const text = names.join(' / ')
              return fields.length ? `${text || '命中'}（改动: ${fields.join(', ')}）` : text
            },
          },
          {
            title: '错误/告警',
            key: 'errors',
            render: (_, row) => {
              const issues = [...(row.errors || []), ...(row.warnings || []).map((x) => `⚠ ${x}`)]
              return issues.length ? issues.join('；') : '-'
            },
          },
        ]}
      />
    </Card>
  )
}
