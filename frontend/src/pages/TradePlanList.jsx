import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, DatePicker, Descriptions, Empty, Form, Input, List, Popconfirm, Row, Select, Space, Tag, Typography, message } from 'antd';
import dayjs from 'dayjs';
import { reviewSessionApi, tradeApi, tradePlanApi } from '../api';
import ReadEditActions from '../features/trading/components/ReadEditActions';
import ResearchContentPanel from '../features/trading/components/ResearchContentPanel';
import { buildTradeSearchOption, formatInstrumentDisplay, normalizeTagList } from '../features/trading/display';

const { TextArea } = Input;

const STATUS_OPTIONS = [
  { value: 'draft', label: '草稿' },
  { value: 'active', label: '进行中' },
  { value: 'triggered', label: '已触发' },
  { value: 'executed', label: '已执行' },
  { value: 'cancelled', label: '已取消' },
  { value: 'expired', label: '已过期' },
  { value: 'reviewed', label: '已复盘' },
];
const PRIORITY_OPTIONS = [
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
];

function statusLabel(status) {
  return STATUS_OPTIONS.find((x) => x.value === status)?.label || status || '-';
}

function normalizePayload(v) {
  return {
    title: v.title?.trim() || null,
    plan_date: (v.plan_date || dayjs()).format('YYYY-MM-DD'),
    status: v.status || 'draft',
    symbol: v.symbol?.trim() || null,
    contract: v.contract?.trim() || null,
    direction_bias: v.direction_bias?.trim() || null,
    setup_type: v.setup_type?.trim() || null,
    market_regime: v.market_regime?.trim() || null,
    entry_zone: v.entry_zone?.trim() || null,
    stop_loss_plan: v.stop_loss_plan?.trim() || null,
    target_plan: v.target_plan?.trim() || null,
    invalid_condition: v.invalid_condition?.trim() || null,
    thesis: v.thesis?.trim() || null,
    risk_notes: v.risk_notes?.trim() || null,
    execution_checklist: v.execution_checklist?.trim() || null,
    priority: v.priority?.trim() || 'medium',
    tags: normalizeTagList(v.tags),
    source_ref: v.source_ref?.trim() || null,
    post_result_summary: v.post_result_summary?.trim() || null,
    research_notes: v.research_notes || null,
  };
}

export default function TradePlanList() {
  const [rows, setRows] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [tradeSearchOptions, setTradeSearchOptions] = useState([]);
  const [linkedTrades, setLinkedTrades] = useState([]);
  const [quickTradeId, setQuickTradeId] = useState(undefined);
  const [form] = Form.useForm();

  const selected = useMemo(() => rows.find((x) => x.id === selectedId) || null, [rows, selectedId]);

  const resetForm = (row) => {
    if (!row) {
      form.resetFields();
      form.setFieldsValue({ status: 'draft', plan_date: dayjs(), tags: [] });
      setLinkedTrades([]);
      return;
    }
    form.setFieldsValue({ ...row, tags: normalizeTagList(row.tags), plan_date: row.plan_date ? dayjs(row.plan_date) : dayjs() });
    setLinkedTrades((row.trade_links || []).map((x) => ({
      trade_id: x.trade_id,
      note: x.note || '',
      sort_order: x.sort_order || 0,
      trade_summary: x.trade_summary || null,
    })));
  };

  const loadRows = async (nextSelectedId = null) => {
    setLoading(true);
    try {
      const res = await tradePlanApi.list({ size: 200 });
      const list = res.data || [];
      setRows(list);
      const target = nextSelectedId ?? selectedId;
      if (!list.length) {
        setSelectedId(null);
        resetForm(null);
        return;
      }
      if (target && list.some((x) => x.id === target)) {
        setSelectedId(target);
        resetForm(list.find((x) => x.id === target));
      } else {
        setSelectedId(list[0].id);
        resetForm(list[0]);
      }
    } catch {
      message.error('交易计划加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRows();
  }, []);

  const searchTradeOptions = async (keyword = '') => {
    const res = await tradeApi.searchOptions({ q: keyword, limit: 50, include_ids: linkedTrades.map((x) => x.trade_id).join(',') });
    setTradeSearchOptions((res.data?.items || []).map(buildTradeSearchOption));
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = normalizePayload(values);
      let saved;
      if (selectedId) saved = (await tradePlanApi.update(selectedId, payload)).data;
      else saved = (await tradePlanApi.create(payload)).data;

      await tradePlanApi.upsertTradeLinks(saved.id, {
        trade_links: linkedTrades.map((x, idx) => ({ trade_id: Number(x.trade_id), note: x.note || null, sort_order: idx })),
      });
      message.success(selectedId ? '交易计划已更新' : '交易计划已创建');
      setEditing(false);
      await loadRows(saved.id);
      setSelectedId(saved.id);
    } catch (e) {
      if (!e?.errorFields) message.error(e.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) return;
    await tradePlanApi.delete(selectedId);
    message.success('交易计划已删除');
    setEditing(false);
    await loadRows();
  };

  const addTradeLink = () => {
    if (!quickTradeId) return;
    setLinkedTrades((prev) => {
      if (prev.some((x) => Number(x.trade_id) === Number(quickTradeId))) return prev;
      const option = tradeSearchOptions.find((x) => Number(x.value) === Number(quickTradeId));
      return [...prev, { trade_id: Number(quickTradeId), note: '', trade_summary: option?.summary || null }];
    });
    setQuickTradeId(undefined);
  };

  const createFollowupSession = async () => {
    if (!selectedId) return;
    try {
      const session = (await tradePlanApi.createFollowupReviewSession(selectedId)).data;
      await tradePlanApi.upsertReviewSessionLinks(selectedId, { review_session_links: [{ review_session_id: session.id, note: '手动创建跟进复盘' }] });
      message.success(`已创建跟进复盘会话 #${session.id}`);
      await loadRows(selectedId);
    } catch (e) {
      message.error(e.response?.data?.detail || '创建跟进复盘失败');
    }
  };

  return (
    <div className="review-workspace">
      <Card className="review-toolbar" bodyStyle={{ padding: 12 }}>
        <div className="review-toolbar-inner">
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>交易计划工作台</Typography.Title>
            <Typography.Text type="secondary">计划是第一类对象，可关联交易并生成跟进复盘会话</Typography.Text>
          </div>
          <Space>
            <Button onClick={() => { setSelectedId(null); resetForm(null); setEditing(true); }}>新建交易计划</Button>
            <ReadEditActions editing={editing} saving={saving} onEdit={() => { if (selected) { resetForm(selected); setEditing(true); } }} onSave={handleSave} onCancel={() => { resetForm(selected); setEditing(false); }} editDisabled={!selectedId} />
            <Button onClick={createFollowupSession} disabled={!selectedId}>创建跟进复盘会话</Button>
            <Popconfirm title="确认删除当前交易计划？" onConfirm={handleDelete} disabled={!selectedId}><Button danger disabled={!selectedId}>删除</Button></Popconfirm>
          </Space>
        </div>
      </Card>

      <Row gutter={12}>
        <Col xs={24} xl={8}>
          <Card title="交易计划列表" className="review-list-card" loading={loading}>
            <List
              dataSource={rows}
              locale={{ emptyText: <Empty description="暂无交易计划" /> }}
              renderItem={(item) => (
                <List.Item className={`review-list-item ${item.id === selectedId ? 'active' : ''}`} onClick={() => { setSelectedId(item.id); resetForm(item); setEditing(false); }}>
                  <div className="review-list-main">
                    <div className="review-list-title">{item.title || `交易计划 #${item.id}`}</div>
                    <div className="review-list-meta">
                      <Tag>{statusLabel(item.status)}</Tag>
                      <Tag color="blue">{item.plan_date || '-'}</Tag>
                      <Tag color="gold">关联 {item.linked_trade_ids?.length || 0}</Tag>
                    </div>
                    <Typography.Paragraph className="review-list-summary" ellipsis={{ rows: 2 }}>
                      {item.thesis || item.setup_type || item.market_regime || '无摘要'}
                    </Typography.Paragraph>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card title={selectedId ? `交易计划 #${selectedId}` : '新建交易计划'} className="review-editor-card">
            {editing ? (
              <>
                <Form form={form} layout="vertical" initialValues={{ status: 'draft', plan_date: dayjs(), tags: [] }}>
                  <Row gutter={12}>
                    <Col span={10}><Form.Item name="title" label="标题" rules={[{ required: true }]}><Input /></Form.Item></Col>
                    <Col span={7}><Form.Item name="plan_date" label="计划日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
                    <Col span={7}><Form.Item name="status" label="状态"><Select options={STATUS_OPTIONS} /></Form.Item></Col>
                    <Col span={8}><Form.Item name="symbol" label="品种"><Input /></Form.Item></Col>
                    <Col span={8}><Form.Item name="contract" label="合约"><Input /></Form.Item></Col>
                    <Col span={8}><Form.Item name="direction_bias" label="方向偏好"><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="setup_type" label="形态"><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="market_regime" label="市场环境"><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="entry_zone" label="入场区"><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="invalid_condition" label="失效条件"><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="stop_loss_plan" label="止损计划"><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="target_plan" label="目标计划"><Input /></Form.Item></Col>
                    <Col span={24}><Form.Item name="thesis" label="交易论点"><TextArea rows={2} /></Form.Item></Col>
                    <Col span={12}><Form.Item name="risk_notes" label="风险备注"><TextArea rows={2} /></Form.Item></Col>
                    <Col span={12}><Form.Item name="execution_checklist" label="执行清单"><TextArea rows={2} /></Form.Item></Col>
                    <Col span={12}><Form.Item name="priority" label="优先级"><Select options={PRIORITY_OPTIONS} /></Form.Item></Col>
                    <Col span={12}><Form.Item name="tags" label="标签"><Select mode="tags" tokenSeparators={[',', '，']} /></Form.Item></Col>
                    <Col span={12}><Form.Item name="source_ref" label="来源引用"><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="post_result_summary" label="结果摘要"><Input /></Form.Item></Col>
                    <Form.Item name="research_notes" hidden><Input /></Form.Item>
                    <Col span={24}>
                      <Form.Item shouldUpdate noStyle>
                        {() => (
                          <ResearchContentPanel
                            editing
                            title="计划图文研究"
                            value={form.getFieldValue('research_notes')}
                            onChange={(next) => form.setFieldValue('research_notes', next)}
                          />
                        )}
                      </Form.Item>
                    </Col>
                  </Row>
                </Form>

                <Card size="small" title="关联交易" className="review-link-card">
                  <Space wrap style={{ marginBottom: 10 }}>
                    <Select showSearch filterOption={false} value={quickTradeId} onSearch={searchTradeOptions} onFocus={() => searchTradeOptions('')} onChange={setQuickTradeId} options={tradeSearchOptions} style={{ width: 520, maxWidth: '100%' }} />
                    <Button onClick={addTradeLink}>添加关联</Button>
                  </Space>
                  {!linkedTrades.length ? <Empty description="尚未关联交易" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : (
                    <List
                      dataSource={linkedTrades}
                      renderItem={(item, idx) => (
                        <List.Item actions={[<Button key="del" type="link" danger onClick={() => setLinkedTrades((prev) => prev.filter((_, i) => i !== idx))}>移除</Button>]}> 
                          <Space direction="vertical" size={2} style={{ width: '100%' }}>
                            <Typography.Text>{item.trade_summary?.trade_date || '-'} / {formatInstrumentDisplay(item.trade_summary?.symbol, item.trade_summary?.contract)}</Typography.Text>
                            <Input size="small" placeholder="备注" value={item.note || ''} onChange={(e) => setLinkedTrades((prev) => prev.map((x, i) => i === idx ? { ...x, note: e.target.value } : x))} />
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
              </>
            ) : !selected ? (
              <Empty description="请选择左侧交易计划或新建" />
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Card size="small" title="计划概览" className="review-read-card">
                  <Descriptions size="small" column={2}>
                    <Descriptions.Item label="标题">{selected.title || '-'}</Descriptions.Item>
                    <Descriptions.Item label="日期">{selected.plan_date || '-'}</Descriptions.Item>
                    <Descriptions.Item label="状态">{statusLabel(selected.status)}</Descriptions.Item>
                    <Descriptions.Item label="品种">{formatInstrumentDisplay(selected.symbol, selected.contract)}</Descriptions.Item>
                    <Descriptions.Item label="形态">{selected.setup_type || '-'}</Descriptions.Item>
                    <Descriptions.Item label="市场环境">{selected.market_regime || '-'}</Descriptions.Item>
                    <Descriptions.Item label="交易论点">{selected.thesis || '-'}</Descriptions.Item>
                    <Descriptions.Item label="执行清单">{selected.execution_checklist || '-'}</Descriptions.Item>
                  </Descriptions>
                </Card>
                <Card size="small" title="计划图文研究" className="review-read-card">
                  <ResearchContentPanel value={selected.research_notes} title="计划图文研究" />
                </Card>
                <Card size="small" title="关联交易（内容卡片）" className="review-link-card">
                  {(selected.trade_links || []).length === 0 ? <Empty description="暂无关联交易" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : (
                    <div className="review-linked-grid">
                      {(selected.trade_links || []).map((item) => (
                        <Card key={`${item.id}-${item.trade_id}`} size="small" className="review-linked-card">
                          <Typography.Text strong>{item.trade_summary?.trade_date || '-'} / {formatInstrumentDisplay(item.trade_summary?.symbol, item.trade_summary?.contract)}</Typography.Text>
                          <br />
                          <Typography.Text type="secondary">{item.trade_summary?.direction || '-'} / 手数 {item.trade_summary?.quantity ?? '-'} / 价格 {item.trade_summary?.open_price ?? '-'} {'->'} {item.trade_summary?.close_price ?? '-'} / PnL {item.trade_summary?.pnl ?? '-'} / 来源 {item.trade_summary?.source_display || '-'}</Typography.Text>
                        </Card>
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


