import { Col, Input, Modal, Row, Select, Typography } from 'antd';
import { normalizeTagList } from '../display';
import { taxonomyOptionsWithZh } from '../localization';
import ResearchContentPanel from '../components/ResearchContentPanel';

const { TextArea } = Input;

export default function TradeBatchStructuredReviewModal({
  open,
  selectedCount,
  review,
  reviewTaxonomy,
  saving,
  onCancel,
  onConfirm,
  onChange,
}) {
  const tags = normalizeTagList(review?.tags);

  return (
    <Modal
      width={860}
      title={`多选结构化复盘（${selectedCount} 条）`}
      open={open}
      onCancel={onCancel}
      onOk={onConfirm}
      confirmLoading={saving}
      okText="批量保存"
      cancelText="取消"
      destroyOnClose
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        将把以下结构化复盘字段批量写入当前勾选交易，支持图文录入。
      </Typography.Paragraph>
      <Row gutter={12}>
        <Col span={12}>
          <Typography.Text type="secondary">机会结构</Typography.Text>
          <Select
            value={review.opportunity_structure || undefined}
            allowClear
            options={taxonomyOptionsWithZh('opportunity_structure', reviewTaxonomy.opportunity_structure)}
            onChange={(v) => onChange('opportunity_structure', v || '')}
            placeholder="选择机会结构"
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={12}>
          <Typography.Text type="secondary">优势来源</Typography.Text>
          <Select
            value={review.edge_source || undefined}
            allowClear
            options={taxonomyOptionsWithZh('edge_source', reviewTaxonomy.edge_source)}
            onChange={(v) => onChange('edge_source', v || '')}
            placeholder="选择优势来源"
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={12}>
          <Typography.Text type="secondary">失败类型</Typography.Text>
          <Select
            value={review.failure_type || undefined}
            allowClear
            options={taxonomyOptionsWithZh('failure_type', reviewTaxonomy.failure_type)}
            onChange={(v) => onChange('failure_type', v || '')}
            placeholder="选择失败类型"
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={12}>
          <Typography.Text type="secondary">复盘结论</Typography.Text>
          <Select
            value={review.review_conclusion || undefined}
            allowClear
            options={taxonomyOptionsWithZh('review_conclusion', reviewTaxonomy.review_conclusion)}
            onChange={(v) => onChange('review_conclusion', v || '')}
            placeholder="选择复盘结论"
            style={{ width: '100%' }}
          />
        </Col>
        <Col span={24}>
          <Typography.Text type="secondary">标签</Typography.Text>
          <Select
            mode="tags"
            tokenSeparators={[',', '，']}
            value={tags}
            onChange={(v) => onChange('tags', v || [])}
            style={{ width: '100%' }}
            placeholder="输入并回车添加标签"
          />
        </Col>
        <Col span={24}>
          <Typography.Text type="secondary">入场论点</Typography.Text>
          <TextArea rows={2} value={review.entry_thesis || ''} onChange={(e) => onChange('entry_thesis', e.target.value)} />
        </Col>
        <Col span={12}>
          <Typography.Text type="secondary">有效证据</Typography.Text>
          <TextArea rows={2} value={review.invalidation_valid_evidence || ''} onChange={(e) => onChange('invalidation_valid_evidence', e.target.value)} />
        </Col>
        <Col span={12}>
          <Typography.Text type="secondary">失效证据</Typography.Text>
          <TextArea rows={2} value={review.invalidation_trigger_evidence || ''} onChange={(e) => onChange('invalidation_trigger_evidence', e.target.value)} />
        </Col>
        <Col span={24}>
          <Typography.Text type="secondary">边界</Typography.Text>
          <TextArea rows={2} value={review.invalidation_boundary || ''} onChange={(e) => onChange('invalidation_boundary', e.target.value)} />
        </Col>
        <Col span={24}>
          <Typography.Text type="secondary">管理动作</Typography.Text>
          <TextArea rows={2} value={review.management_actions || ''} onChange={(e) => onChange('management_actions', e.target.value)} />
        </Col>
        <Col span={24}>
          <Typography.Text type="secondary">离场原因</Typography.Text>
          <TextArea rows={2} value={review.exit_reason || ''} onChange={(e) => onChange('exit_reason', e.target.value)} />
        </Col>
        <Col span={24}>
          <ResearchContentPanel
            editing
            title="多选交易图文研究"
            value={review.research_notes || ''}
            onChange={(next) => onChange('research_notes', next)}
          />
        </Col>
      </Row>
    </Modal>
  );
}
