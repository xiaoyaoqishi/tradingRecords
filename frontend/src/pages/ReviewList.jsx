import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined, SaveOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { reviewApi, tradeApi } from '../api';
import { formatFuturesSymbol } from '../utils/futures';
import {
  REVIEW_LINK_ROLE_ZH,
  REVIEW_SCOPE_ZH,
  REVIEW_TYPE_ZH,
  dictToOptions,
  mapLabel,
} from '../features/trading/localization';
import './ReviewList.css';

const { TextArea } = Input;

const REVIEW_TYPE_OPTIONS = dictToOptions(REVIEW_TYPE_ZH);
const REVIEW_SCOPE_OPTIONS = dictToOptions(REVIEW_SCOPE_ZH);
const REVIEW_ROLE_OPTIONS = dictToOptions(REVIEW_LINK_ROLE_ZH);

function normalizeTags(raw) {
  if (Array.isArray(raw)) return raw.map((x) => String(x || '').trim()).filter(Boolean);
  return String(raw || '')
    .split(/[,\n;|，、]+/)
    .map((x) => x.trim())
    .filter(Boolean);
}

function buildTradeOption(trade) {
  const d = trade.trade_date || (trade.open_time ? String(trade.open_time).slice(0, 10) : '-');
  const symbolLabel = formatFuturesSymbol(trade.symbol, trade.contract);
  const side = trade.direction || '-';
  const qty = trade.quantity == null ? '-' : trade.quantity;
  const pnl = trade.pnl == null ? '-' : Number(trade.pnl).toFixed(2);
  return {
    value: trade.id,
    label: `#${trade.id} | ${d} | ${symbolLabel} | ${side} | 手数 ${qty} | PnL ${pnl}`,
    summary: {
      trade_id: trade.id,
      trade_date: trade.trade_date,
      symbol: trade.symbol,
      contract: trade.contract,
      direction: trade.direction,
      quantity: trade.quantity,
      open_price: trade.open_price,
      close_price: trade.close_price,
      status: trade.status,
      pnl: trade.pnl,
      source_display: trade.source_display,
    },
  };
}

function normalizeReviewPayload(values) {
  return {
    ...values,
    tags: normalizeTags(values.tags),
    title: values.title?.trim() || null,
    review_scope: values.review_scope || 'periodic',
    focus_topic: values.focus_topic?.trim() || null,
    market_regime: values.market_regime?.trim() || null,
    best_trade: values.best_trade?.trim() || null,
    worst_trade: values.worst_trade?.trim() || null,
    tomorrow_avoid: values.tomorrow_avoid?.trim() || null,
    profit_source: values.profit_source?.trim() || null,
    loss_source: values.loss_source?.trim() || null,
    continue_trades: values.continue_trades?.trim() || null,
    reduce_trades: values.reduce_trades?.trim() || null,
    repeated_errors: values.repeated_errors?.trim() || null,
    next_focus: values.next_focus?.trim() || null,
    profit_from_skill: values.profit_from_skill?.trim() || null,
    best_strategy: values.best_strategy?.trim() || null,
    profit_eating_behavior: values.profit_eating_behavior?.trim() || null,
    adjust_symbols: values.adjust_symbols?.trim() || null,
    adjust_position: values.adjust_position?.trim() || null,
    pause_patterns: values.pause_patterns?.trim() || null,
    summary: values.summary?.trim() || null,
    action_items: values.action_items?.trim() || null,
    content: values.content?.trim() || null,
    review_date: values.review_date.format('YYYY-MM-DD'),
  };
}

function LinkedTradeCard({ item }) {
  const s = item?.trade_summary || {};
  const symbolLabel = formatFuturesSymbol(s.symbol, s.contract);
  const roleLabel = mapLabel(REVIEW_LINK_ROLE_ZH, item.role);
  return (
    <Card size="small" className="review-linked-card">
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Space wrap>
          <Tag color="blue">{roleLabel}</Tag>
          <Tag>#{s.trade_id || item.trade_id}</Tag>
          {s.direction ? <Tag color={s.direction === '做多' ? 'red' : 'green'}>{s.direction}</Tag> : null}
          {s.status ? <Tag>{s.status === 'closed' ? '已平' : '持仓'}</Tag> : null}
        </Space>
        <div>{s.trade_date || '-'} · {symbolLabel || '-'}</div>
        <div>手数 {s.quantity ?? '-'} · 开 {s.open_price ?? '-'} · 平 {s.close_price ?? '-'}</div>
        <div>PnL {s.pnl ?? '-'} · 来源 {s.source_display || '-'}</div>
        {item.notes ? <Typography.Text type="secondary">备注：{item.notes}</Typography.Text> : null}
      </Space>
    </Card>
  );
}

export default function ReviewList() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [activeType, setActiveType] = useState('daily');
  const [activeScope, setActiveScope] = useState(undefined);
  const [activeTag, setActiveTag] = useState(undefined);
  const [selectedReviewId, setSelectedReviewId] = useState(null);
  const [linkedTrades, setLinkedTrades] = useState([]);
  const [tradeOptions, setTradeOptions] = useState([]);
  const [quickTradeId, setQuickTradeId] = useState(undefined);
  const [quickRole, setQuickRole] = useState('linked_trade');
  const [form] = Form.useForm();

  const tradeOptionMap = useMemo(() => {
    const out = {};
    for (const item of tradeOptions) out[item.value] = item;
    return out;
  }, [tradeOptions]);

  const selectedReview = useMemo(
    () => reviews.find((x) => x.id === selectedReviewId) || null,
    [reviews, selectedReviewId]
  );

  const reviewTagOptions = useMemo(() => {
    const set = new Set();
    reviews.forEach((r) => normalizeTags(r.tags).forEach((t) => set.add(t)));
    return Array.from(set).map((x) => ({ value: x, label: x }));
  }, [reviews]);

  const resetFormFromReview = (review) => {
    if (!review) {
      form.resetFields();
      form.setFieldsValue({
        review_type: activeType,
        review_scope: activeScope || 'periodic',
        review_date: dayjs(),
        tags: [],
      });
      setLinkedTrades([]);
      return;
    }
    form.setFieldsValue({
      ...review,
      tags: normalizeTags(review.tags),
      review_type: review.review_type || activeType,
      review_scope: review.review_scope || 'periodic',
      review_date: review.review_date ? dayjs(review.review_date) : dayjs(),
    });
    setLinkedTrades((review.trade_links || []).map((x) => ({
      trade_id: x.trade_id,
      role: x.role || 'linked_trade',
      notes: x.notes || '',
      trade_summary: x.trade_summary || null,
    })));
  };

  const loadReviews = async (nextSelectedId = null) => {
    setLoading(true);
    try {
      const params = { review_type: activeType, size: 200 };
      if (activeScope) params.review_scope = activeScope;
      if (activeTag) params.tag = activeTag;
      const res = await reviewApi.list(params);
      const rows = res.data || [];
      setReviews(rows);
      const targetId = nextSelectedId ?? selectedReviewId;
      if (!rows.length) {
        setSelectedReviewId(null);
        resetFormFromReview(null);
        return;
      }
      if (targetId && rows.some((x) => x.id === targetId)) {
        setSelectedReviewId(targetId);
        const next = rows.find((x) => x.id === targetId);
        resetFormFromReview(next);
        return;
      }
      setSelectedReviewId(rows[0].id);
      resetFormFromReview(rows[0]);
    } catch {
      message.error('复盘列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadTradeOptions = async () => {
    try {
      const res = await tradeApi.list({ page: 1, size: 300 });
      setTradeOptions((res.data || []).map(buildTradeOption));
    } catch {
      setTradeOptions([]);
    }
  };

  useEffect(() => {
    loadReviews();
  }, [activeType, activeScope, activeTag]);

  useEffect(() => {
    loadTradeOptions();
  }, []);

  const handleSelectReview = (review) => {
    setSelectedReviewId(review.id);
    resetFormFromReview(review);
    setEditing(false);
  };

  const handleNewReview = () => {
    setSelectedReviewId(null);
    resetFormFromReview(null);
    setEditing(true);
  };

  const handleEditReview = () => {
    if (!selectedReview) return;
    resetFormFromReview(selectedReview);
    setEditing(true);
  };

  const handleCancelEdit = () => {
    resetFormFromReview(selectedReview);
    setEditing(false);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = normalizeReviewPayload(values);
      let saved;
      if (selectedReviewId) {
        const updateRes = await reviewApi.update(selectedReviewId, payload);
        saved = updateRes.data;
      } else {
        const createRes = await reviewApi.create(payload);
        saved = createRes.data;
      }
      await reviewApi.upsertTradeLinks(saved.id, {
        trade_links: linkedTrades
          .filter((x) => x.trade_id)
          .map((x) => ({
            trade_id: Number(x.trade_id),
            role: x.role || 'linked_trade',
            notes: (x.notes || '').trim() || null,
          })),
      });
      message.success(selectedReviewId ? '复盘已更新' : '复盘已创建');
      setEditing(false);
      await loadReviews(saved.id);
      setSelectedReviewId(saved.id);
    } catch (e) {
      if (!e?.errorFields) {
        message.error(e?.response?.data?.detail || '保存失败');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedReviewId) return;
    try {
      await reviewApi.delete(selectedReviewId);
      message.success('复盘已删除');
      setEditing(false);
      await loadReviews();
    } catch {
      message.error('删除失败');
    }
  };

  const addLinkedTrade = () => {
    if (!quickTradeId) {
      message.warning('请先选择交易');
      return;
    }
    setLinkedTrades((prev) => {
      const next = [...prev];
      const idx = next.findIndex((x) => Number(x.trade_id) === Number(quickTradeId));
      const tradeSummary = tradeOptionMap[Number(quickTradeId)]?.summary || null;
      if (idx >= 0) {
        next[idx] = { ...next[idx], role: quickRole || 'linked_trade', trade_summary: tradeSummary };
      } else {
        next.push({ trade_id: Number(quickTradeId), role: quickRole || 'linked_trade', notes: '', trade_summary: tradeSummary });
      }
      return next;
    });
    setQuickTradeId(undefined);
  };

  const updateLinkedTrade = (index, patch) => {
    setLinkedTrades((prev) =>
      prev.map((x, i) => {
        if (i !== index) return x;
        const next = { ...x, ...patch };
        if (patch.trade_id) {
          next.trade_summary = tradeOptionMap[Number(patch.trade_id)]?.summary || x.trade_summary || null;
        }
        return next;
      })
    );
  };

  const removeLinkedTrade = (index) => {
    setLinkedTrades((prev) => prev.filter((_, i) => i !== index));
  };

  const type = Form.useWatch('review_type', form) || activeType;
  const tagsForRead = normalizeTags(selectedReview?.tags);

  return (
    <div className="review-workspace">
      <Card className="review-toolbar" bodyStyle={{ padding: 12 }}>
        <div className="review-toolbar-inner">
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>复盘研究工作台</Typography.Title>
            <Typography.Text type="secondary">单笔复盘在交易详情完成，这里聚焦多笔/主题/周期复盘并沉淀结论。</Typography.Text>
          </div>
          <Space wrap>
            <Select value={activeType} options={REVIEW_TYPE_OPTIONS} onChange={setActiveType} style={{ width: 130 }} />
            <Select allowClear value={activeScope} options={REVIEW_SCOPE_OPTIONS} placeholder="范围" onChange={setActiveScope} style={{ width: 130 }} />
            <Select allowClear value={activeTag} options={reviewTagOptions} placeholder="标签筛选" onChange={setActiveTag} style={{ width: 140 }} />
            <Button onClick={handleNewReview} icon={<PlusOutlined />}>新建复盘</Button>
            {editing ? (
              <>
                <Button type="primary" loading={saving} icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
                <Button onClick={handleCancelEdit}>取消</Button>
              </>
            ) : (
              <Button icon={<EditOutlined />} onClick={handleEditReview} disabled={!selectedReviewId}>编辑</Button>
            )}
            <Popconfirm title="确认删除当前复盘？" onConfirm={handleDelete} disabled={!selectedReviewId}>
              <Button danger icon={<DeleteOutlined />} disabled={!selectedReviewId}>删除</Button>
            </Popconfirm>
          </Space>
        </div>
      </Card>

      <Row gutter={12}>
        <Col xs={24} xl={8}>
          <Card title="复盘列表" className="review-list-card" loading={loading}>
            <List
              dataSource={reviews}
              locale={{ emptyText: <Empty description="暂无复盘" /> }}
              renderItem={(item) => (
                <List.Item className={`review-list-item ${item.id === selectedReviewId ? 'active' : ''}`} onClick={() => handleSelectReview(item)}>
                  <div className="review-list-main">
                    <div className="review-list-title">{item.title || `${item.review_date} ${mapLabel(REVIEW_TYPE_ZH, item.review_type)}`}</div>
                    <div className="review-list-meta">
                      <Tag>{mapLabel(REVIEW_TYPE_ZH, item.review_type)}</Tag>
                      <Tag color="blue">{mapLabel(REVIEW_SCOPE_ZH, item.review_scope || 'periodic')}</Tag>
                      <Tag color="gold">关联 {item.linked_trade_ids?.length || 0}</Tag>
                    </div>
                    <Typography.Paragraph className="review-list-summary" ellipsis={{ rows: 2 }}>
                      {item.summary || item.focus_topic || item.next_focus || '无摘要'}
                    </Typography.Paragraph>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card title={selectedReviewId ? `复盘 #${selectedReviewId}` : '新建复盘'} className="review-editor-card">
            {editing ? (
              <>
                <Form form={form} layout="vertical" initialValues={{ review_type: activeType, review_scope: 'periodic', review_date: dayjs(), tags: [] }}>
                  <Row gutter={12}>
                    <Col span={10}><Form.Item name="title" label="标题"><Input placeholder="例如：本周趋势延续复盘" /></Form.Item></Col>
                    <Col span={5}><Form.Item name="review_type" label="类型" rules={[{ required: true }]}><Select options={REVIEW_TYPE_OPTIONS} /></Form.Item></Col>
                    <Col span={5}><Form.Item name="review_scope" label="范围"><Select options={REVIEW_SCOPE_OPTIONS} /></Form.Item></Col>
                    <Col span={4}><Form.Item name="review_date" label="日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
                    <Col span={8}><Form.Item name="focus_topic" label="聚焦主题"><Input placeholder="setup / 失败类型 / 环境" /></Form.Item></Col>
                    <Col span={8}><Form.Item name="market_regime" label="市场环境"><Input placeholder="高波趋势 / 低波噪声" /></Form.Item></Col>
                    <Col span={8}>
                      <Form.Item name="tags" label="标签">
                        <Select mode="tags" tokenSeparators={[',', '，']} options={reviewTagOptions} placeholder="输入标签并回车" />
                      </Form.Item>
                    </Col>

                    {type === 'daily' && (
                      <>
                        <Col span={12}><Form.Item name="best_trade" label="最佳交易"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="worst_trade" label="最差交易"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={8}><Form.Item name="discipline_violated" label="纪律违规" valuePropName="checked"><Switch /></Form.Item></Col>
                        <Col span={8}><Form.Item name="loss_acceptable" label="亏损可接受" valuePropName="checked"><Switch /></Form.Item></Col>
                        <Col span={8}><Form.Item name="execution_score" label="执行评分(1-10)"><Input type="number" /></Form.Item></Col>
                        <Col span={24}><Form.Item name="tomorrow_avoid" label="下一交易日避免"><TextArea rows={2} /></Form.Item></Col>
                      </>
                    )}

                    {type === 'weekly' && (
                      <>
                        <Col span={12}><Form.Item name="profit_source" label="主要盈利来源"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="loss_source" label="主要亏损来源"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="continue_trades" label="继续做"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="reduce_trades" label="减少做"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="repeated_errors" label="重复错误"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="next_focus" label="下周聚焦"><TextArea rows={2} /></Form.Item></Col>
                      </>
                    )}

                    {type === 'monthly' && (
                      <>
                        <Col span={12}><Form.Item name="profit_from_skill" label="盈利来自能力/运气"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="best_strategy" label="真正有优势的策略"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="profit_eating_behavior" label="吞噬利润行为"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="adjust_symbols" label="品种池调整"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="adjust_position" label="仓位体系调整"><TextArea rows={2} /></Form.Item></Col>
                        <Col span={12}><Form.Item name="pause_patterns" label="暂停模式"><TextArea rows={2} /></Form.Item></Col>
                      </>
                    )}

                    <Col span={24}><Form.Item name="summary" label="结论摘要"><TextArea rows={2} /></Form.Item></Col>
                    <Col span={24}><Form.Item name="action_items" label="后续动作"><TextArea rows={2} placeholder="可转化为执行清单/知识项" /></Form.Item></Col>
                    <Col span={24}><Form.Item name="content" label="详细复盘"><TextArea rows={4} /></Form.Item></Col>
                  </Row>
                </Form>

                <Card size="small" title="关联交易（多笔/样本）" className="review-link-card">
                  <Space wrap style={{ marginBottom: 10 }}>
                    <Select
                      showSearch
                      value={quickTradeId}
                      onChange={setQuickTradeId}
                      options={tradeOptions}
                      placeholder="选择交易"
                      style={{ width: 420 }}
                      optionFilterProp="label"
                    />
                    <Select value={quickRole} onChange={setQuickRole} options={REVIEW_ROLE_OPTIONS} style={{ width: 150 }} />
                    <Button onClick={addLinkedTrade}>添加关联</Button>
                  </Space>

                  {!linkedTrades.length ? (
                    <Empty description="尚未关联交易" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <List
                      dataSource={linkedTrades}
                      renderItem={(item, index) => (
                        <List.Item
                          actions={[
                            <Button key="delete" type="link" danger onClick={() => removeLinkedTrade(index)}>移除</Button>,
                          ]}
                        >
                          <div className="review-link-row">
                            <Select
                              size="small"
                              showSearch
                              optionFilterProp="label"
                              value={item.trade_id}
                              onChange={(v) => updateLinkedTrade(index, { trade_id: v })}
                              options={tradeOptions}
                              style={{ width: 340 }}
                            />
                            <Select
                              size="small"
                              value={item.role || 'linked_trade'}
                              options={REVIEW_ROLE_OPTIONS}
                              onChange={(v) => updateLinkedTrade(index, { role: v })}
                              style={{ width: 140 }}
                            />
                            <Input
                              size="small"
                              placeholder="样本备注"
                              value={item.notes || ''}
                              onChange={(e) => updateLinkedTrade(index, { notes: e.target.value })}
                            />
                          </div>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
              </>
            ) : !selectedReview ? (
              <Empty description="请选择左侧复盘或新建复盘" />
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Descriptions size="small" column={2}>
                  <Descriptions.Item label="标题">{selectedReview.title || '-'}</Descriptions.Item>
                  <Descriptions.Item label="日期">{selectedReview.review_date || '-'}</Descriptions.Item>
                  <Descriptions.Item label="类型">{mapLabel(REVIEW_TYPE_ZH, selectedReview.review_type)}</Descriptions.Item>
                  <Descriptions.Item label="范围">{mapLabel(REVIEW_SCOPE_ZH, selectedReview.review_scope || 'periodic')}</Descriptions.Item>
                  <Descriptions.Item label="聚焦主题">{selectedReview.focus_topic || '-'}</Descriptions.Item>
                  <Descriptions.Item label="市场环境">{selectedReview.market_regime || '-'}</Descriptions.Item>
                </Descriptions>

                {tagsForRead.length > 0 ? (
                  <div>
                    <Typography.Text type="secondary">标签</Typography.Text>
                    <div style={{ marginTop: 4 }}>{tagsForRead.map((t) => <Tag key={t}>{t}</Tag>)}</div>
                  </div>
                ) : null}

                {selectedReview.summary ? (
                  <div>
                    <Typography.Text type="secondary">结论摘要</Typography.Text>
                    <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{selectedReview.summary}</Typography.Paragraph>
                  </div>
                ) : null}
                {selectedReview.action_items ? (
                  <div>
                    <Typography.Text type="secondary">后续动作</Typography.Text>
                    <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{selectedReview.action_items}</Typography.Paragraph>
                  </div>
                ) : null}
                {selectedReview.content ? (
                  <div>
                    <Typography.Text type="secondary">详细复盘</Typography.Text>
                    <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{selectedReview.content}</Typography.Paragraph>
                  </div>
                ) : null}

                <Card size="small" title="关联交易（内容卡片）" className="review-link-card">
                  {(selectedReview.trade_links || []).length === 0 ? (
                    <Empty description="暂无关联交易" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <div className="review-linked-grid">
                      {(selectedReview.trade_links || []).map((item) => (
                        <LinkedTradeCard key={`${item.id}-${item.trade_id}`} item={item} />
                      ))}
                    </div>
                  )}
                </Card>
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
