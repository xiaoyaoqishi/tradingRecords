import { Descriptions, Divider, Drawer, Tag, Typography } from 'antd'

function displayOrPending(value) {
  const text = String(value ?? '').trim()
  return text && text !== '未识别' ? text : '待识别'
}

export default function ReviewDetailPanel({ open, row, onClose }) {
  const statusLabel = {
    pending: '待确认',
    confirmed: '已确认',
    duplicate: '重复',
    invalid: '无效',
    committed: '已入账',
  }
  const duplicateLabel = {
    exact_duplicate: '完全重复',
    probable_duplicate: '高疑似重复',
    review_duplicate: '待复核重复',
  }
  return (
    <Drawer
      title={row ? `校对详情 #${row.id}` : '校对详情'}
      open={open}
      width={520}
      onClose={onClose}
      destroyOnClose
    >
      {!row ? null : (
        <>
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="校对状态">
              <Tag color={row.review_status === 'confirmed' ? 'green' : row.review_status === 'duplicate' ? 'orange' : 'blue'}>
                {statusLabel[row.review_status] || row.review_status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="重复类型">{duplicateLabel[row.duplicate_type] || row.duplicate_type || '-'}</Descriptions.Item>
            <Descriptions.Item label="来源渠道">{displayOrPending(row.source_channel_display)}</Descriptions.Item>
            <Descriptions.Item label="平台">{displayOrPending(row.platform_display)}</Descriptions.Item>
            <Descriptions.Item label="商户归一">{displayOrPending(row.merchant_normalized)}</Descriptions.Item>
            <Descriptions.Item label="建议分类">{displayOrPending(row.category_name)}</Descriptions.Item>
            <Descriptions.Item label="来源识别 explain">{row.source_explain || '-'}</Descriptions.Item>
            <Descriptions.Item label="商户归一 explain">{row.merchant_explain || '-'}</Descriptions.Item>
            <Descriptions.Item label="分类 explain">{row.category_explain || '-'}</Descriptions.Item>
            <Descriptions.Item label="fallback/low confidence">{row.low_confidence_reason || '-'}</Descriptions.Item>
          </Descriptions>

          <Divider orientation="left">重复判定依据</Divider>
          <Typography.Paragraph className="review-json-block">
            <pre>{JSON.stringify(row.duplicate_basis_json || {}, null, 2)}</pre>
          </Typography.Paragraph>

          <Divider orientation="left">规则执行轨迹</Divider>
          <Typography.Paragraph className="review-json-block">
            <pre>{JSON.stringify(row.execution_trace_json || {}, null, 2)}</pre>
          </Typography.Paragraph>
        </>
      )}
    </Drawer>
  )
}
