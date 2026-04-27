import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Select,
  Space,
  Statistic,
  Tag,
  message,
} from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import {
  commitImportBatch,
  getImportBatch,
  listCategories,
  listImportReviewRows,
  reprocessImportBatch,
  reviewBulkConfirm,
  reviewGenerateRule,
  reviewReclassifyPending,
} from '../api/ledger'
import PageHeader from '../components/PageHeader'
import ReviewDetailPanel from '../components/ReviewDetailPanel'
import ReviewTable from '../components/ReviewTable'

export default function ImportReviewPage() {
  const navigate = useNavigate()
  const { batchId } = useParams()
  const [loading, setLoading] = useState(false)
  const [batch, setBatch] = useState(null)
  const [allRows, setAllRows] = useState([])
  const [selectedRowKeys, setSelectedRowKeys] = useState([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [detailRow, setDetailRow] = useState(null)
  const [ruleModalOpen, setRuleModalOpen] = useState(false)
  const [ruleTargetRowIds, setRuleTargetRowIds] = useState([])
  const [ruleKind, setRuleKind] = useState('merchant')
  const [ruleScope, setRuleScope] = useState('profile')
  const [ruleReprocessScope, setRuleReprocessScope] = useState('unconfirmed')
  const [rulePriority, setRulePriority] = useState(40)
  const [ruleMatchText, setRuleMatchText] = useState('')
  const [ruleTargetMerchantName, setRuleTargetMerchantName] = useState('')
  const [ruleTargetCategoryName, setRuleTargetCategoryName] = useState(null)
  const [ruleTargetSubcategoryName, setRuleTargetSubcategoryName] = useState(null)
  const [ruleTargetSourceChannel, setRuleTargetSourceChannel] = useState(null)
  const [ruleTargetPlatform, setRuleTargetPlatform] = useState(null)
  const [categories, setCategories] = useState([])
  const [rulePreviewRows, setRulePreviewRows] = useState(null)
  const [ruleSubmitting, setRuleSubmitting] = useState(false)
  const [highConfidenceThreshold, setHighConfidenceThreshold] = useState(0.8)

  const statusLabel = {
    uploaded: '已上传',
    parsed: '已解析',
    classified: '已分类',
    deduped: '已清理重复标记',
    committed: '已提交',
  }

  const load = async () => {
    if (!batchId) return
    setLoading(true)
    try {
      const [batchPayload, rowPayload] = await Promise.all([
        getImportBatch(batchId),
        listImportReviewRows(batchId),
      ])
      setBatch(batchPayload)
      setAllRows(Array.isArray(rowPayload?.items) ? rowPayload.items : [])
      const categoriesPayload = await listCategories()
      setCategories(Array.isArray(categoriesPayload?.items) ? categoriesPayload.items : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [batchId])

  const isRowPendingRecognition = (row) => !row?.source_channel || !row?.merchant_normalized || !row?.category_id

  const filteredRows = useMemo(() => {
    return allRows.filter((row) => {
      if (statusFilter === 'all') return true
      if (statusFilter === 'unrecognized') return isRowPendingRecognition(row)
      return row.review_status === statusFilter
    })
  }, [allRows, statusFilter])

  const counts = useMemo(() => {
    const confirmed = allRows.filter((x) => x.review_status === 'confirmed').length
    const pending = allRows.filter((x) => x.review_status === 'pending').length
    const duplicate = allRows.filter((x) => x.review_status === 'duplicate').length
    const identified = allRows.filter((x) => !isRowPendingRecognition(x)).length
    const unrecognized = allRows.filter((x) => isRowPendingRecognition(x)).length
    const highConfidenceReady = allRows.filter(
      (x) =>
        Number(x.confidence || 0) >= Number(highConfidenceThreshold || 0) &&
        x.review_status === 'pending' &&
        !x.duplicate_type,
    ).length
    return { confirmed, pending, duplicate, identified, unrecognized, highConfidenceReady }
  }, [allRows, highConfidenceThreshold])

  const parseOnlyRows = useMemo(
    () =>
      allRows.filter((x) => {
        const trace = x.execution_trace_json || {}
        const keys = Object.keys(trace)
        return keys.length === 1 && keys[0] === 'parse'
      }).length,
    [allRows],
  )

  const selectedEditableCount = useMemo(() => {
    const selected = new Set(selectedRowKeys)
    return allRows.filter((x) => selected.has(x.id) && x.review_status !== 'duplicate').length
  }, [allRows, selectedRowKeys])
  const highConfidenceRowIds = useMemo(() => {
    return allRows
      .filter(
        (x) =>
          x.review_status === 'pending' &&
          !x.duplicate_type &&
          Number(x.confidence || 0) >= Number(highConfidenceThreshold || 0),
      )
      .map((x) => x.id)
  }, [allRows, highConfidenceThreshold])

  const inferRuleDefaults = (targetRows = []) => {
    const merchantStats = new Map()
    const matchStats = new Map()
    const categoryStats = new Map()
    for (const row of targetRows) {
      const merchantRaw = String(row?.merchant_raw || '').trim()
      const merchantNorm = String(row?.merchant_normalized || '').trim()
      const fallbackTail = String(row?.raw_text || '').split('-').slice(-1)[0]?.split(' ')[0]?.trim()
      const matchText = merchantRaw || merchantNorm || fallbackTail || ''
      if (matchText) matchStats.set(matchText, Number(matchStats.get(matchText) || 0) + 1)
      if (merchantNorm || merchantRaw) {
        const merchant = merchantNorm || merchantRaw
        merchantStats.set(merchant, Number(merchantStats.get(merchant) || 0) + 1)
      }
      if (row?.category_name) {
        categoryStats.set(row.category_name, Number(categoryStats.get(row.category_name) || 0) + 1)
      }
    }
    const best = (stats) =>
      Array.from(stats.entries())
        .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0) || String(a[0]).localeCompare(String(b[0]), 'zh-CN'))[0]?.[0] || ''
    return {
      matchText: best(matchStats),
      merchantName: best(merchantStats),
      categoryName: best(categoryStats) || null,
      sourceChannel: targetRows.find((x) => x?.source_channel)?.source_channel || null,
      platform: targetRows.find((x) => x?.platform)?.platform || null,
    }
  }

  const openRuleModal = () => {
    const rowIds = selectedRowKeys
    if (!rowIds.length) {
      message.warning('请先勾选记录，再生成规则')
      return
    }
    const selectedRows = allRows.filter((x) => rowIds.includes(x.id))
    const defaults = inferRuleDefaults(selectedRows)
    setRuleKind('merchant')
    setRuleScope('profile')
    setRuleReprocessScope('unconfirmed')
    setRulePriority(40)
    setRuleMatchText(defaults.matchText || '')
    setRuleTargetMerchantName(defaults.merchantName || defaults.matchText || '')
    setRuleTargetCategoryName(defaults.categoryName || null)
    setRuleTargetSubcategoryName(null)
    setRuleTargetSourceChannel(defaults.sourceChannel || null)
    setRuleTargetPlatform(defaults.platform || defaults.sourceChannel || null)
    setRuleTargetRowIds(rowIds)
    setRulePreviewRows(null)
    setRuleModalOpen(true)
  }

  const handlePreviewRules = async () => {
    if (!ruleTargetRowIds.length) return
    if (ruleKind === 'category' || ruleKind === 'merchant_and_category') {
      if (!ruleTargetCategoryName) {
        message.warning('分类规则请先选择目标分类')
        return
      }
    }
    if (ruleKind === 'source' && !ruleTargetPlatform && !ruleTargetSourceChannel) {
      message.warning('来源/平台规则请先选择来源渠道或平台')
      return
    }
    if (!ruleMatchText) {
      message.warning('请先确认匹配关键词')
      return
    }
    setRuleSubmitting(true)
    try {
      const payload = await reviewGenerateRule(batchId, {
        row_ids: ruleTargetRowIds,
        rule_kind: ruleKind,
        match_text: ruleMatchText,
        target_merchant_name: ruleTargetMerchantName || null,
        target_category_name: ruleTargetCategoryName || null,
        target_subcategory_name: ruleTargetSubcategoryName || null,
        target_source_channel: ruleTargetSourceChannel || null,
        target_platform: ruleTargetPlatform || null,
        priority: Number(rulePriority || 40),
        apply_scope: ruleScope,
        preview_only: true,
        reprocess_after_create: true,
        reprocess_scope: ruleReprocessScope,
      })
      setRulePreviewRows(payload || {})
      message.success('规则预览完成')
    } finally {
      setRuleSubmitting(false)
    }
  }

  const handleCreateRules = async () => {
    if (!ruleTargetRowIds.length) return
    if (ruleKind === 'category' || ruleKind === 'merchant_and_category') {
      if (!ruleTargetCategoryName) {
        message.warning('分类规则请先选择目标分类')
        return
      }
    }
    if (ruleKind === 'source' && !ruleTargetPlatform && !ruleTargetSourceChannel) {
      message.warning('来源/平台规则请先选择来源渠道或平台')
      return
    }
    if (!ruleMatchText) {
      message.warning('请先确认匹配关键词')
      return
    }
    setRuleSubmitting(true)
    try {
      const payload = await reviewGenerateRule(batchId, {
        row_ids: ruleTargetRowIds,
        rule_kind: ruleKind,
        match_text: ruleMatchText,
        target_merchant_name: ruleTargetMerchantName || null,
        target_category_name: ruleTargetCategoryName || null,
        target_subcategory_name: ruleTargetSubcategoryName || null,
        target_source_channel: ruleTargetSourceChannel || null,
        target_platform: ruleTargetPlatform || null,
        priority: Number(rulePriority || 40),
        apply_scope: ruleScope,
        preview_only: false,
        reprocess_after_create: true,
        reprocess_scope: ruleReprocessScope,
      })
      const createdCount = Array.isArray(payload?.created_rule_ids) ? payload.created_rule_ids.length : 0
      const skippedCount = Number(payload?.skipped_existing_count || 0)
      message.success(`规则生成完成：新增 ${createdCount}，跳过重复 ${skippedCount}`)
      if (payload?.reprocess_result?.reprocessed_rows) {
        const before = Number(payload?.reprocess_result?.unrecognized_before || 0)
        const after = Number(payload?.reprocess_result?.unrecognized_after || 0)
        const scopeText = payload?.reprocess_result?.reprocess_scope === 'all' ? '全部记录' : '未确认记录'
        message.success(`已自动重识别${scopeText}，未识别：${before} -> ${after}`)
      }
      setRuleModalOpen(false)
      setSelectedRowKeys([])
      await load()
    } finally {
      setRuleSubmitting(false)
    }
  }

  const categoryOptions = useMemo(() => {
    const options = categories.map((item) => ({ label: item.name, value: item.name }))
    if (!options.find((x) => x.value === '其他')) options.push({ label: '其他', value: '其他' })
    return options
  }, [categories])

  const sourceChannelOptions = [
    { label: '微信', value: 'wechat' },
    { label: '支付宝', value: 'alipay' },
    { label: '美团', value: 'meituan' },
    { label: '京东', value: 'jd' },
    { label: '拼多多', value: 'pinduoduo' },
    { label: '银行卡', value: 'bank_card' },
    { label: '其他', value: 'other' },
  ]

  const platformOptions = [
    { label: '微信', value: 'wechat' },
    { label: '支付宝', value: 'alipay' },
    { label: '美团', value: 'meituan' },
    { label: '京东', value: 'jd' },
    { label: '拼多多', value: 'pinduoduo' },
    { label: '银行卡', value: 'bank_card' },
    { label: '其他', value: 'other' },
  ]

  const currentCategoryChildren = useMemo(() => {
    return categories.find((x) => x.name === ruleTargetCategoryName)?.children || []
  }, [categories, ruleTargetCategoryName])

  const ruleSamples = useMemo(() => {
    const selected = new Set(ruleTargetRowIds)
    return allRows.filter((x) => selected.has(x.id)).slice(0, 5)
  }, [allRows, ruleTargetRowIds])

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <PageHeader
        title={`导入校对台 #${batchId}`}
        subtitle={`文件：${batch?.file_name || '-'} | 状态：${statusLabel[batch?.status] || batch?.status || '-'}`}
        extra={
          <Space>
            <Button onClick={() => navigate('/imports')}>返回导入中心</Button>
          </Space>
        }
      />

      <Alert
        type="warning"
        showIcon
        message="校对台只会在提交时导入已确认行。请先批量或单条确认。"
      />
      {parseOnlyRows > 0 ? (
        <Alert
          type="error"
          showIcon
          message={`检测到 ${parseOnlyRows} 条记录仅有 parse 轨迹，尚未执行完整识别链路。请点击“对当前批次重放规则”。`}
        />
      ) : null}

      <Card className="page-card">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div><strong>解析来源类型：</strong>{batch?.source_type_display || '未识别'}</div>
          <div><strong>关键列映射：</strong>{JSON.stringify(batch?.parse_diagnostics?.selected_columns || {}, null, 0)}</div>
          <div><strong>摘要示例：</strong>{(batch?.parse_diagnostics?.raw_text_examples || []).join(' ｜ ') || '暂无'}</div>
        </Space>
      </Card>

      <Card className="page-card">
        <Space wrap size={16}>
          <Statistic title="待确认" value={counts.pending} />
          <Statistic title="重复标记" value={counts.duplicate} />
          <Statistic title="已确认" value={counts.confirmed} />
          <Statistic title="已完成识别" value={counts.identified} />
          <Statistic title="待识别" value={counts.unrecognized} />
          <Statistic title="高置信可确认" value={counts.highConfidenceReady} />
          <InputNumber
            min={0}
            max={1}
            step={0.01}
            value={highConfidenceThreshold}
            onChange={(v) => setHighConfidenceThreshold(Number(v ?? 0.8))}
            addonBefore="高置信阈值"
          />
          <Button
            disabled={!highConfidenceRowIds.length}
            onClick={async () => {
              setLoading(true)
              try {
                const payload = await reviewBulkConfirm(batchId, { row_ids: highConfidenceRowIds })
                message.success(`高阈值确认完成：${payload.updated_count || 0} 条`)
                await load()
              } finally {
                setLoading(false)
              }
            }}
          >
            一键确认高阈值
          </Button>
          <Segmented
            value={statusFilter}
            options={[
              { label: '全部', value: 'all' },
              { label: '待确认', value: 'pending' },
              { label: '待识别', value: 'unrecognized' },
              { label: '已确认', value: 'confirmed' },
            ]}
            onChange={setStatusFilter}
          />
          <Button
            disabled={!filteredRows.length}
            onClick={() => setSelectedRowKeys(filteredRows.map((x) => x.id))}
          >
            一键全选当前列表
          </Button>
          <Button
            disabled={!selectedRowKeys.length}
            onClick={() => setSelectedRowKeys([])}
          >
            一键取消勾选
          </Button>
          <Tag color="processing">当前已选可操作 {selectedEditableCount} 条</Tag>
          <Button
            disabled={!selectedRowKeys.length}
            onClick={openRuleModal}
          >
            从勾选记录生成规则
          </Button>
        </Space>
      </Card>

      <Card className="page-card">
        <Space wrap size={12} style={{ marginBottom: 12 }}>
          <Button onClick={load} loading={loading}>刷新</Button>
          <Button
            onClick={async () => {
              setLoading(true)
              try {
                await reprocessImportBatch(batchId)
                message.success('重算识别完成')
                await load()
              } finally {
                setLoading(false)
              }
            }}
          >
            对当前批次重放规则
          </Button>
          <Button
            onClick={async () => {
              setLoading(true)
              try {
                const payload = await reviewReclassifyPending(batchId)
                message.success(`待确认重识别完成：处理 ${payload.reclassified_count || 0} 条`)
                await load()
              } finally {
                setLoading(false)
              }
            }}
          >
            对待确认重新识别
          </Button>
          <Button
            type="primary"
            disabled={counts.confirmed <= 0}
            onClick={async () => {
              setLoading(true)
              try {
                const payload = await commitImportBatch(batchId)
                message.success(`提交完成：入账 ${payload.committed_count ?? payload.created_count ?? 0}，跳过 ${payload.skipped_count ?? 0}，失败 ${payload.failed_count ?? 0}`)
                await load()
              } finally {
                setLoading(false)
              }
            }}
          >
            提交入账（仅已确认）
          </Button>
        </Space>
        <ReviewTable
          rows={filteredRows}
          loading={loading}
          selectedRowKeys={selectedRowKeys}
          onSelectionChange={setSelectedRowKeys}
          onViewDetail={setDetailRow}
        />
      </Card>

      <ReviewDetailPanel open={!!detailRow} row={detailRow} onClose={() => setDetailRow(null)} />
      <Modal
        title="导入中心直接建立规则"
        open={ruleModalOpen}
        onCancel={() => setRuleModalOpen(false)}
        width={920}
        footer={[
          <Button key="preview" onClick={handlePreviewRules} loading={ruleSubmitting}>预览命中范围</Button>,
          <Button key="create" type="primary" onClick={handleCreateRules} loading={ruleSubmitting}>确认创建并重识别未确认</Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <Segmented
              value={ruleKind}
              onChange={setRuleKind}
              options={[
                { label: '商户归一规则', value: 'merchant' },
                { label: '分类规则', value: 'category' },
                { label: '商户归一 + 分类规则', value: 'merchant_and_category' },
                { label: '来源/平台规则', value: 'source' },
              ]}
            />
            <Segmented
              value={ruleScope}
              onChange={setRuleScope}
              options={[
                { label: '仅当前来源范围生效', value: 'profile' },
                { label: '全局生效', value: 'global' },
              ]}
            />
            <Segmented
              value={ruleReprocessScope}
              onChange={setRuleReprocessScope}
              options={[
                { label: '重识别未确认', value: 'unconfirmed' },
                { label: '重识别全部记录', value: 'all' },
              ]}
            />
            <InputNumber
              min={0}
              max={9999}
              value={rulePriority}
              onChange={(v) => setRulePriority(Number(v ?? 40))}
              addonBefore="优先级"
            />
            <Tag color="processing">样本行 {ruleTargetRowIds.length} 条</Tag>
          </Space>
          <Input
            value={ruleMatchText}
            onChange={(e) => setRuleMatchText(e.target.value)}
            placeholder="匹配关键词（自动提取，可修改）"
            addonBefore="匹配关键词"
          />
          {ruleKind === 'merchant' || ruleKind === 'merchant_and_category' ? (
            <Input
              value={ruleTargetMerchantName}
              onChange={(e) => setRuleTargetMerchantName(e.target.value)}
              placeholder="目标商户名"
              addonBefore="目标商户"
            />
          ) : null}
          {ruleKind === 'category' || ruleKind === 'merchant_and_category' ? (
            <Space wrap style={{ width: '100%' }}>
              <Select
                style={{ minWidth: 260 }}
                placeholder="选择目标分类"
                value={ruleTargetCategoryName}
                options={categoryOptions}
                onChange={(v) => {
                  setRuleTargetCategoryName(v)
                  setRuleTargetSubcategoryName(null)
                }}
                showSearch
                optionFilterProp="label"
              />
              {currentCategoryChildren.length ? (
                <Select
                  style={{ minWidth: 260 }}
                  placeholder="选择目标子分类（可选）"
                  value={ruleTargetSubcategoryName}
                  options={currentCategoryChildren.map((x) => ({ label: x.name, value: x.name }))}
                  onChange={setRuleTargetSubcategoryName}
                  allowClear
                  showSearch
                  optionFilterProp="label"
                />
              ) : null}
            </Space>
          ) : null}
          {ruleKind === 'source' ? (
            <Space wrap style={{ width: '100%' }}>
              <Select
                style={{ minWidth: 260 }}
                placeholder="选择来源渠道"
                value={ruleTargetSourceChannel}
                options={sourceChannelOptions}
                onChange={setRuleTargetSourceChannel}
                allowClear
              />
              <Select
                style={{ minWidth: 260 }}
                placeholder="选择平台"
                value={ruleTargetPlatform}
                options={platformOptions}
                onChange={setRuleTargetPlatform}
                allowClear
              />
            </Space>
          ) : null}
          <Alert
            type="info"
            showIcon
            message="先预览命中范围，再确认创建。创建成功后会自动重识别未确认记录。"
          />
          {ruleSamples.length ? (
            <Card size="small" title="样本与提取条件">
              <Space direction="vertical" style={{ width: '100%' }}>
                {ruleSamples.map((x) => (
                  <div key={x.id}>
                    <strong>样本：</strong>{x.raw_text || '-'} ｜ <strong>来源：</strong>{x.source_channel_display || '未识别'} ｜ <strong>平台：</strong>{x.platform_display || '未识别'} ｜ <strong>商户原始名：</strong>{x.merchant_raw || '未识别'}
                  </div>
                ))}
              </Space>
            </Card>
          ) : null}
          {rulePreviewRows?.preview?.length ? (
            <Card size="small" title="预览结果">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Tag color="blue">预计命中 {Number(rulePreviewRows?.estimated_hit_rows || 0)} 条</Tag>
                {rulePreviewRows.preview.map((item, idx) => (
                  <Space key={`${item.row_id}-${idx}`} style={{ width: '100%', justifyContent: 'space-between' }}>
                    <span style={{ maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.pattern}</span>
                    <Space size={8}>
                      <Tag>预计影响 {item.expected_hit_rows} 条</Tag>
                      {item.skipped_existing ? <Tag color="warning">重复规则将跳过</Tag> : <Tag color="success">可创建</Tag>}
                    </Space>
                  </Space>
                ))}
                {(rulePreviewRows?.matched_samples || []).map((item) => (
                  <Tag key={item.row_id}>{item.raw_text || item.merchant_raw || `样本#${item.row_id}`}</Tag>
                ))}
              </Space>
            </Card>
          ) : null}
        </Space>
      </Modal>
    </Space>
  )
}
