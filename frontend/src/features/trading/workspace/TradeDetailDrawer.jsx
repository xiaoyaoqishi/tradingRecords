import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Drawer,
  Empty,
  Input,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  Select,
} from 'antd';
import { EditOutlined, ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import { formatFuturesSymbol } from '../../../utils/futures';
import { getTaxonomyLabel, taxonomyOptionsWithZh } from '../localization';

const { TextArea } = Input;

function ReadonlyParagraph({ label, value }) {
  const v = String(value || '').trim();
  if (!v) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <Typography.Text type="secondary">{label}</Typography.Text>
      <Typography.Paragraph style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>{v}</Typography.Paragraph>
    </div>
  );
}

export default function TradeDetailDrawer({
  open,
  tradeId,
  loading,
  trade,
  review,
  reviewExists,
  source,
  legacy,
  reviewTaxonomy,
  savingReview,
  savingSource,
  savingLegacy,
  onClose,
  onReload,
  onOpenEdit,
  onChangeReview,
  onChangeSource,
  onChangeLegacy,
  onSaveReview,
  onSaveSource,
  onSaveLegacy,
}) {
  const [reviewEditing, setReviewEditing] = useState(false);
  const [sourceEditing, setSourceEditing] = useState(false);
  const [legacyEditing, setLegacyEditing] = useState(false);

  useEffect(() => {
    setReviewEditing(false);
    setSourceEditing(false);
    setLegacyEditing(false);
  }, [tradeId, open]);

  const reviewTags = useMemo(
    () => (Array.isArray(review?.tags) ? review.tags.filter(Boolean) : []),
    [review?.tags]
  );

  const hasReviewContent = useMemo(() => {
    if (reviewTags.length > 0) return true;
    return [
      review?.opportunity_structure,
      review?.edge_source,
      review?.failure_type,
      review?.review_conclusion,
      review?.entry_thesis,
      review?.invalidation_valid_evidence,
      review?.invalidation_trigger_evidence,
      review?.invalidation_boundary,
      review?.management_actions,
      review?.exit_reason,
      review?.research_notes,
    ].some((x) => String(x || '').trim());
  }, [review, reviewTags]);

  const saveReview = async () => {
    await onSaveReview();
    setReviewEditing(false);
  };

  const saveSource = async () => {
    await onSaveSource();
    setSourceEditing(false);
  };

  const saveLegacy = async () => {
    await onSaveLegacy();
    setLegacyEditing(false);
  };

  const cancelSectionEdit = async (setter) => {
    await onReload();
    setter(false);
  };

  return (
    <Drawer
      title={tradeId ? `交易详情 #${tradeId}` : '交易详情'}
      width={760}
      open={open}
      onClose={onClose}
      destroyOnClose={false}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={onReload} disabled={!tradeId}>
            刷新
          </Button>
          {tradeId ? (
            <Button type="primary" onClick={onOpenEdit}>
              打开完整编辑
            </Button>
          ) : null}
        </Space>
      }
    >
      {loading ? (
        <div className="trade-drawer-loading">
          <Spin />
        </div>
      ) : !trade ? (
        <Typography.Text type="secondary">未找到交易详情</Typography.Text>
      ) : (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card size="small" title="成交流水信息">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="交易日期">{trade.trade_date || '-'}</Descriptions.Item>
              <Descriptions.Item label="品种">{formatFuturesSymbol(trade.symbol, trade.contract)}</Descriptions.Item>
              <Descriptions.Item label="方向">
                <Tag color={trade.direction === '做多' ? 'red' : 'green'}>{trade.direction || '-'}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={trade.status === 'closed' ? 'default' : 'processing'}>
                  {trade.status === 'closed' ? '已平' : '持仓'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="开仓价">{trade.open_price ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="平仓价">{trade.close_price ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="手数">{trade.quantity ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="盈亏">{trade.pnl ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="来源">{trade.source_display || '-'}</Descriptions.Item>
              <Descriptions.Item label="结构化复盘">
                {reviewExists ? <Tag color="green">已建立</Tag> : <Tag>未建立</Tag>}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card
            size="small"
            title="结构化复盘（主工作流）"
            extra={
              reviewEditing ? (
                <Space>
                  <Button loading={savingReview} type="primary" icon={<SaveOutlined />} onClick={saveReview}>保存</Button>
                  <Button onClick={() => cancelSectionEdit(setReviewEditing)}>取消</Button>
                </Space>
              ) : (
                <Button icon={<EditOutlined />} onClick={() => setReviewEditing(true)}>编辑</Button>
              )
            }
          >
            {reviewEditing ? (
              <Row gutter={12}>
                <Col span={12}>
                  <Typography.Text type="secondary">机会结构</Typography.Text>
                  <Select
                    value={review.opportunity_structure || undefined}
                    allowClear
                    options={taxonomyOptionsWithZh('opportunity_structure', reviewTaxonomy.opportunity_structure)}
                    onChange={(v) => onChangeReview('opportunity_structure', v || '')}
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
                    onChange={(v) => onChangeReview('edge_source', v || '')}
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
                    onChange={(v) => onChangeReview('failure_type', v || '')}
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
                    onChange={(v) => onChangeReview('review_conclusion', v || '')}
                    placeholder="选择复盘结论"
                    style={{ width: '100%' }}
                  />
                </Col>
                <Col span={24}>
                  <Typography.Text type="secondary">标签</Typography.Text>
                  <Select
                    mode="tags"
                    tokenSeparators={[',', '，']}
                    value={review.tags || []}
                    onChange={(v) => onChangeReview('tags', v || [])}
                    style={{ width: '100%' }}
                    placeholder="输入并回车添加标签"
                  />
                </Col>
                <Col span={24}>
                  <Typography.Text type="secondary">入场论点</Typography.Text>
                  <TextArea rows={2} value={review.entry_thesis} onChange={(e) => onChangeReview('entry_thesis', e.target.value)} />
                </Col>
                <Col span={12}>
                  <Typography.Text type="secondary">有效证据</Typography.Text>
                  <TextArea rows={2} value={review.invalidation_valid_evidence} onChange={(e) => onChangeReview('invalidation_valid_evidence', e.target.value)} />
                </Col>
                <Col span={12}>
                  <Typography.Text type="secondary">失效证据</Typography.Text>
                  <TextArea rows={2} value={review.invalidation_trigger_evidence} onChange={(e) => onChangeReview('invalidation_trigger_evidence', e.target.value)} />
                </Col>
                <Col span={24}>
                  <Typography.Text type="secondary">边界</Typography.Text>
                  <TextArea rows={2} value={review.invalidation_boundary} onChange={(e) => onChangeReview('invalidation_boundary', e.target.value)} />
                </Col>
                <Col span={24}>
                  <Typography.Text type="secondary">管理动作</Typography.Text>
                  <TextArea rows={2} value={review.management_actions} onChange={(e) => onChangeReview('management_actions', e.target.value)} />
                </Col>
                <Col span={24}>
                  <Typography.Text type="secondary">离场原因</Typography.Text>
                  <TextArea rows={2} value={review.exit_reason} onChange={(e) => onChangeReview('exit_reason', e.target.value)} />
                </Col>
                <Col span={24}>
                  <Typography.Text type="secondary">研究记录</Typography.Text>
                  <TextArea rows={3} value={review.research_notes} onChange={(e) => onChangeReview('research_notes', e.target.value)} />
                </Col>
              </Row>
            ) : !hasReviewContent ? (
              <Empty description="暂无结构化复盘内容" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <div>
                <Space wrap style={{ marginBottom: 8 }}>
                  {review.opportunity_structure ? <Tag color="blue">机会结构：{getTaxonomyLabel('opportunity_structure', review.opportunity_structure)}</Tag> : null}
                  {review.edge_source ? <Tag color="cyan">优势来源：{getTaxonomyLabel('edge_source', review.edge_source)}</Tag> : null}
                  {review.failure_type ? <Tag color="red">失败类型：{getTaxonomyLabel('failure_type', review.failure_type)}</Tag> : null}
                  {review.review_conclusion ? <Tag color="green">结论：{getTaxonomyLabel('review_conclusion', review.review_conclusion)}</Tag> : null}
                </Space>
                {reviewTags.length > 0 ? (
                  <div style={{ marginBottom: 10 }}>
                    <Typography.Text type="secondary">标签</Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      {reviewTags.map((t) => <Tag key={t}>{t}</Tag>)}
                    </div>
                  </div>
                ) : null}
                <ReadonlyParagraph label="入场论点" value={review.entry_thesis} />
                <ReadonlyParagraph label="有效证据" value={review.invalidation_valid_evidence} />
                <ReadonlyParagraph label="失效证据" value={review.invalidation_trigger_evidence} />
                <ReadonlyParagraph label="边界" value={review.invalidation_boundary} />
                <ReadonlyParagraph label="管理动作" value={review.management_actions} />
                <ReadonlyParagraph label="离场原因" value={review.exit_reason} />
                <ReadonlyParagraph label="研究记录" value={review.research_notes} />
              </div>
            )}
          </Card>

          <Card
            size="small"
            title="来源元数据（主工作流）"
            extra={
              sourceEditing ? (
                <Space>
                  <Button loading={savingSource} type="primary" icon={<SaveOutlined />} onClick={saveSource}>保存</Button>
                  <Button onClick={() => cancelSectionEdit(setSourceEditing)}>取消</Button>
                </Space>
              ) : (
                <Button icon={<EditOutlined />} onClick={() => setSourceEditing(true)}>编辑</Button>
              )
            }
          >
            {sourceEditing ? (
              <Row gutter={12}>
                <Col span={12}>
                  <Typography.Text type="secondary">券商</Typography.Text>
                  <Input value={source.broker_name} onChange={(e) => onChangeSource('broker_name', e.target.value)} placeholder="例如：宏源期货" />
                </Col>
                <Col span={12}>
                  <Typography.Text type="secondary">来源标签</Typography.Text>
                  <Input value={source.source_label} onChange={(e) => onChangeSource('source_label', e.target.value)} placeholder="例如：日结单粘贴导入" />
                </Col>
                <Col span={12}>
                  <Typography.Text type="secondary">导入通道</Typography.Text>
                  <Input value={source.import_channel} onChange={(e) => onChangeSource('import_channel', e.target.value)} placeholder="例如：paste_import" />
                </Col>
                <Col span={12}>
                  <Typography.Text type="secondary">解析版本</Typography.Text>
                  <Input value={source.parser_version} onChange={(e) => onChangeSource('parser_version', e.target.value)} placeholder="例如：paste_v1" />
                </Col>
                <Col span={24}>
                  <Typography.Text type="secondary">来源快照</Typography.Text>
                  <TextArea value={source.source_note_snapshot} onChange={(e) => onChangeSource('source_note_snapshot', e.target.value)} rows={2} />
                </Col>
              </Row>
            ) : (
              <Descriptions size="small" column={2}>
                <Descriptions.Item label="券商">{source.broker_name || '-'}</Descriptions.Item>
                <Descriptions.Item label="来源标签">{source.source_label || '-'}</Descriptions.Item>
                <Descriptions.Item label="导入通道">{source.import_channel || '-'}</Descriptions.Item>
                <Descriptions.Item label="解析版本">{source.parser_version || '-'}</Descriptions.Item>
                <Descriptions.Item label="元数据状态" span={2}>
                  {source.exists_in_db ? <Tag color="blue">显式 metadata</Tag> : <Tag>兼容回退（notes）</Tag>}
                </Descriptions.Item>
                <Descriptions.Item label="来源快照" span={2}>{source.source_note_snapshot || '-'}</Descriptions.Item>
              </Descriptions>
            )}
          </Card>

          <Card
            size="small"
            title="兼容字段（次级）"
            extra={
              legacyEditing ? (
                <Space>
                  <Button loading={savingLegacy} type="primary" icon={<SaveOutlined />} onClick={saveLegacy}>保存</Button>
                  <Button onClick={() => cancelSectionEdit(setLegacyEditing)}>取消</Button>
                </Space>
              ) : (
                <Button icon={<EditOutlined />} onClick={() => setLegacyEditing(true)}>编辑</Button>
              )
            }
          >
            {legacyEditing ? (
              <>
                <Typography.Text type="secondary">legacy review_note</Typography.Text>
                <TextArea rows={2} value={legacy.review_note} onChange={(e) => onChangeLegacy('review_note', e.target.value)} />
                <Divider style={{ margin: '12px 0' }} />
                <Typography.Text type="secondary">legacy notes</Typography.Text>
                <TextArea rows={3} value={legacy.notes} onChange={(e) => onChangeLegacy('notes', e.target.value)} />
              </>
            ) : (
              <>
                <ReadonlyParagraph label="legacy review_note" value={legacy.review_note} />
                <ReadonlyParagraph label="legacy notes" value={legacy.notes} />
              </>
            )}
          </Card>
        </Space>
      )}
    </Drawer>
  );
}
