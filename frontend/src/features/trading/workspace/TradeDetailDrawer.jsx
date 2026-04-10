import {
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Drawer,
  Input,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  Select,
} from 'antd';
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import { formatFuturesSymbol } from '../../../utils/futures';
import { taxonomyOptionsWithZh } from '../localization';

const { TextArea } = Input;

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
  return (
    <Drawer
      title={tradeId ? `交易详情 #${tradeId}` : '交易详情'}
      width={700}
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
          <Card size="small" title="成交信息">
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
            </Descriptions>
          </Card>

          <Card size="small" title="结构化复盘（主工作流）">
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
                <Typography.Text type="secondary">入场论点</Typography.Text>
                <TextArea rows={2} value={review.entry_thesis} onChange={(e) => onChangeReview('entry_thesis', e.target.value)} />
              </Col>
              <Col span={12}>
                <Typography.Text type="secondary">有效证据</Typography.Text>
                <TextArea
                  rows={2}
                  value={review.invalidation_valid_evidence}
                  onChange={(e) => onChangeReview('invalidation_valid_evidence', e.target.value)}
                />
              </Col>
              <Col span={12}>
                <Typography.Text type="secondary">失效证据</Typography.Text>
                <TextArea
                  rows={2}
                  value={review.invalidation_trigger_evidence}
                  onChange={(e) => onChangeReview('invalidation_trigger_evidence', e.target.value)}
                />
              </Col>
              <Col span={24}>
                <Typography.Text type="secondary">边界</Typography.Text>
                <TextArea
                  rows={2}
                  value={review.invalidation_boundary}
                  onChange={(e) => onChangeReview('invalidation_boundary', e.target.value)}
                />
              </Col>
              <Col span={24}>
                <Typography.Text type="secondary">管理动作</Typography.Text>
                <TextArea
                  rows={2}
                  value={review.management_actions}
                  onChange={(e) => onChangeReview('management_actions', e.target.value)}
                />
              </Col>
              <Col span={24}>
                <Typography.Text type="secondary">离场原因</Typography.Text>
                <TextArea rows={2} value={review.exit_reason} onChange={(e) => onChangeReview('exit_reason', e.target.value)} />
              </Col>
              <Col span={24}>
                <Typography.Text type="secondary">复盘标签</Typography.Text>
                <Input value={review.review_tags} onChange={(e) => onChangeReview('review_tags', e.target.value)} />
              </Col>
              <Col span={24}>
                <Typography.Text type="secondary">研究记录</Typography.Text>
                <TextArea rows={3} value={review.research_notes} onChange={(e) => onChangeReview('research_notes', e.target.value)} />
              </Col>
            </Row>
            <div className="trade-drawer-actions">
              <Space>
                <Button type="primary" icon={<SaveOutlined />} loading={savingReview} onClick={onSaveReview}>
                  保存结构化复盘
                </Button>
                <Typography.Text type="secondary">{reviewExists ? '已存在 TradeReview' : '尚未创建 TradeReview'}</Typography.Text>
              </Space>
            </div>
          </Card>

          <Card size="small" title="来源元数据（主工作流）">
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
                <TextArea
                  value={source.source_note_snapshot}
                  onChange={(e) => onChangeSource('source_note_snapshot', e.target.value)}
                  rows={2}
                  placeholder="可选：保存来源快照"
                />
              </Col>
            </Row>
            <div className="trade-drawer-actions">
              <Space>
                <Button type="primary" icon={<SaveOutlined />} loading={savingSource} onClick={onSaveSource}>
                  保存来源元数据
                </Button>
                <Typography.Text type="secondary">
                  {source.exists_in_db ? '读取显式 metadata' : '当前为兼容回退视图，保存后写入 metadata'}
                </Typography.Text>
              </Space>
            </div>
          </Card>

          <Card size="small" title="兼容字段（次级）">
            <Typography.Text type="secondary">legacy review_note</Typography.Text>
            <TextArea rows={2} value={legacy.review_note} onChange={(e) => onChangeLegacy('review_note', e.target.value)} />
            <Divider style={{ margin: '12px 0' }} />
            <Typography.Text type="secondary">legacy notes</Typography.Text>
            <TextArea rows={3} value={legacy.notes} onChange={(e) => onChangeLegacy('notes', e.target.value)} />
            <div className="trade-drawer-actions">
              <Button type="default" icon={<SaveOutlined />} loading={savingLegacy} onClick={onSaveLegacy}>
                保存兼容字段
              </Button>
            </div>
          </Card>
        </Space>
      )}
    </Drawer>
  );
}
