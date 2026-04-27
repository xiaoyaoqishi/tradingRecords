import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Popconfirm, Space, Table, Tag, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  classifyImportBatch,
  commitImportBatch,
  createImportBatch,
  deleteImportBatch,
  dedupeImportBatch,
  listImportBatches,
  listImportReviewRows,
  parseImportBatch,
  reprocessImportBatch,
} from '../api/ledger'
import BatchToolbar from '../components/BatchToolbar'
import PageHeader from '../components/PageHeader'
import { formatDateTime } from '../utils/date'

export default function ImportBatchesPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState([])
  const [errorMessage, setErrorMessage] = useState('')
  const [statsMap, setStatsMap] = useState({})

  const load = useCallback(async () => {
    setLoading(true)
    setErrorMessage('')
    try {
      const payload = await listImportBatches()
      const items = Array.isArray(payload?.items) ? payload.items : []
      setRows(items)

      const pair = await Promise.all(
        items.slice(0, 30).map(async (item) => {
          const review = await listImportReviewRows(item.id)
          const reviewRows = Array.isArray(review?.items) ? review.items : []
          const confirmedCount = reviewRows.filter((x) => x.review_status === 'confirmed').length
          const pendingCount = reviewRows.filter((x) => x.review_status === 'pending').length
          const duplicateCount = reviewRows.filter((x) => x.review_status === 'duplicate').length
          return [item.id, { confirmedCount, pendingCount, duplicateCount }]
        }),
      )
      setStatsMap(Object.fromEntries(pair))
    } catch (error) {
      setErrorMessage(error?.userMessage || '加载导入批次失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const triggerStep = async (batchId, fn, stepName) => {
    setLoading(true)
    try {
      await fn(batchId)
      message.success(`${stepName} 完成`)
      await load()
    } finally {
      setLoading(false)
    }
  }

  const parseAndRecognize = async (batchId) => {
    setLoading(true)
    try {
      await parseImportBatch(batchId)
      await reprocessImportBatch(batchId)
      message.success('解析并识别完成')
      await load()
    } finally {
      setLoading(false)
    }
  }

  const canCommit = (row) => Number(statsMap[row.id]?.confirmedCount || 0) > 0

  const statusColor = useMemo(
    () => ({
      uploaded: 'default',
      parsed: 'processing',
      classified: 'blue',
      deduped: 'orange',
      committed: 'green',
    }),
    [],
  )
  const statusLabel = {
    uploaded: '已上传',
    parsed: '已解析',
    classified: '已分类',
    deduped: '已去重',
    committed: '已提交',
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title="导入中心"
        subtitle="以批次推进：上传 -> 解析 -> 分类 -> 去重 -> 校对确认 -> 提交入账"
        extra={<BatchToolbar loading={loading} onRefresh={load} onUpload={async (file) => {
          setLoading(true)
          try {
            await createImportBatch(file)
            message.success('批次创建成功')
            await load()
          } finally {
            setLoading(false)
          }
        }} />}
      />

      <Alert type="info" showIcon message="提交入账仅导入已确认行，请先进入校对台完成确认。" />

      {errorMessage ? <Alert type="error" showIcon message={errorMessage} /> : null}

      <Card className="page-card">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={rows}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          columns={[
            { title: '文件名', dataIndex: 'file_name', ellipsis: true },
            { title: '来源类型', dataIndex: 'source_type_display', width: 120, render: (v, row) => v || row.source_type || '-' },
            {
              title: '状态',
              dataIndex: 'status',
              width: 120,
              render: (v) => <Tag color={statusColor[v] || 'default'}>{statusLabel[v] || v}</Tag>,
            },
            { title: '总条数', dataIndex: 'total_rows', width: 90 },
            { title: '待确认', key: 'pending', width: 90, render: (_, row) => statsMap[row.id]?.pendingCount ?? row.review_rows ?? 0 },
            { title: '重复数', key: 'dup', width: 90, render: (_, row) => statsMap[row.id]?.duplicateCount ?? row.duplicate_rows ?? 0 },
            { title: '已确认/可提交', key: 'confirmed', width: 120, render: (_, row) => statsMap[row.id]?.confirmedCount ?? 0 },
            { title: '创建时间', dataIndex: 'created_at', width: 170, render: (v) => (v ? formatDateTime(v) : '-') },
            {
              title: '操作',
              key: 'op',
              fixed: 'right',
              width: 560,
              render: (_, row) => (
                <Space>
                  <Button type="link" onClick={() => navigate(`/imports/${row.id}/review`)}>进入校对台</Button>
                  <Button type="link" onClick={() => parseAndRecognize(row.id)}>解析并识别</Button>
                  <Button type="link" onClick={() => triggerStep(row.id, classifyImportBatch, '分类')}>分类</Button>
                  <Button type="link" onClick={() => triggerStep(row.id, dedupeImportBatch, '去重')}>去重</Button>
                  <Button type="link" onClick={() => triggerStep(row.id, reprocessImportBatch, '重算识别')}>重算识别</Button>
                  <Button
                    type="link"
                    disabled={!canCommit(row)}
                    onClick={() => triggerStep(row.id, commitImportBatch, '提交')}
                  >
                    提交
                  </Button>
                  <Popconfirm
                    title="删除导入批次"
                    description="将删除该批次、导入行和关联导入交易，且不可恢复。确认继续吗？"
                    okText="删除"
                    cancelText="取消"
                    onConfirm={() => triggerStep(row.id, deleteImportBatch, '删除')}
                  >
                    <Button type="link" danger>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
          scroll={{ x: 1500 }}
        />
      </Card>
    </Space>
  )
}
