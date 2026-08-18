import { useState, useEffect } from 'react';
import {
  Form, Input, InputNumber, Select, DatePicker, Button,
  Tabs, message, Space, Row, Col, Divider, Collapse, Timeline, Typography,
} from 'antd';
import { SaveOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router';
import { instrumentApi, tradeApi, tradeReviewApi } from '../api';
import { taxonomyCanonicalValues, taxonomyOptionsWithZh } from '../features/trading/localization';
import { formatChinaDateTime, normalizeTagList } from '../features/trading/display';
import ResearchContentPanel from '../features/trading/components/ResearchContentPanel';
import dayjs from 'dayjs';

const { TextArea } = Input;
const { Panel } = Collapse;

const TRADE_REVIEW_FIELDS = [
  'opportunity_structure',
  'edge_source',
  'failure_type',
  'review_conclusion',
  'entry_thesis',
  'invalidation_valid_evidence',
  'invalidation_trigger_evidence',
  'invalidation_boundary',
  'management_actions',
  'exit_reason',
  'tags',
  'research_notes',
];

const EMPTY_REVIEW_TAXONOMY = {
  opportunity_structure: [],
  edge_source: [],
  failure_type: [],
  review_conclusion: [],
};

const opt = (arr) => arr.map(v => ({ label: v, value: v }));

export default function TradeForm() {
  const [form] = Form.useForm();
  const instrumentType = Form.useWatch('instrument_type', form);
  const commissionUsdt = Form.useWatch('commission_usdt', form);
  const pnlUsdt = Form.useWatch('pnl_usdt', form);
  const usdCnyRate = Form.useWatch('usd_cny_rate', form);
  const closeTime = Form.useWatch('close_time', form);
  const closePrice = Form.useWatch('close_price', form);
  const [loading, setLoading] = useState(false);
  const [exchangeRateMeta, setExchangeRateMeta] = useState(null);
  const [reviewExists, setReviewExists] = useState(false);
  const [reviewTaxonomy, setReviewTaxonomy] = useState(EMPTY_REVIEW_TAXONOMY);
  const [riskPointHistory, setRiskPointHistory] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = !!id;
  const isClosed = Boolean(closeTime && closePrice != null);

  const instrumentOptions = instruments
    .filter((item) => item.instrument_type === instrumentType)
    .map((item) => ({
      label: `${item.name}（${item.code}）`,
      value: item.code,
      searchText: [item.name, item.code, item.category].filter(Boolean).join(' ').toLowerCase(),
    }));

  const handleInstrumentTypeChange = (nextType) => {
    const currentSymbol = form.getFieldValue('symbol');
    const currentInstrument = instruments.find((item) => item.code === currentSymbol);
    if (currentInstrument?.instrument_type !== nextType) {
      form.setFieldsValue({ symbol: undefined, category: undefined });
    }
  };

  const instrumentSelect = (
    <Select
      showSearch
      allowClear
      disabled={!instrumentType}
      placeholder={instrumentType ? `搜索${instrumentType}品种` : '请先选择交易类型'}
      options={instrumentOptions}
      filterOption={(input, option) => option.searchText.includes(input.trim().toLowerCase())}
      onChange={(code) => {
        const selected = instruments.find((item) => item.code === code);
        form.setFieldValue('category', selected?.category || undefined);
      }}
    />
  );

  useEffect(() => {
    if (instrumentType !== '加密货币' || form.getFieldValue('usd_cny_rate')) return undefined;
    let alive = true;
    tradeApi.usdCnyRate()
      .then((res) => {
        if (!alive || form.getFieldValue('usd_cny_rate')) return;
        form.setFieldValue('usd_cny_rate', res.data?.rate);
        setExchangeRateMeta(res.data || null);
      })
      .catch(() => {
        if (alive) message.warning('自动获取美元人民币汇率失败，请手动填写汇率');
      });
    return () => { alive = false; };
  }, [form, instrumentType]);

  useEffect(() => {
    let alive = true;
    instrumentApi.list()
      .then((res) => {
        if (alive) setInstruments(Array.isArray(res.data) ? res.data : []);
      })
      .catch(() => {
        if (alive) message.error('品种列表加载失败');
      });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    let alive = true;
    tradeReviewApi.taxonomy()
      .then((res) => {
        if (!alive) return;
        setReviewTaxonomy({
          opportunity_structure: res.data?.opportunity_structure || [],
          edge_source: res.data?.edge_source || [],
          failure_type: res.data?.failure_type || [],
          review_conclusion: res.data?.review_conclusion || [],
        });
      })
      .catch(() => {
        if (alive) {
          setReviewTaxonomy({
            ...EMPTY_REVIEW_TAXONOMY,
            opportunity_structure: taxonomyCanonicalValues('opportunity_structure'),
            edge_source: taxonomyCanonicalValues('edge_source'),
            failure_type: taxonomyCanonicalValues('failure_type'),
            review_conclusion: taxonomyCanonicalValues('review_conclusion'),
          });
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    const reviewInitFields = Object.fromEntries(TRADE_REVIEW_FIELDS.map((f) => [f, undefined]));

    const loadData = async () => {
      if (!isEdit) {
        setReviewExists(false);
        setRiskPointHistory([]);
        form.setFieldsValue(reviewInitFields);
        return;
      }
      try {
        const tradeRes = await tradeApi.get(id);
        if (!alive) return;
        const d = { ...tradeRes.data };
        if (d.open_time) d.open_time = dayjs(d.open_time);
        if (d.close_time) d.close_time = dayjs(d.close_time);
        form.setFieldsValue(d);

        try {
          const historyRes = await tradeApi.riskPointHistory(id);
          if (!alive) return;
          setRiskPointHistory(Array.isArray(historyRes.data) ? historyRes.data : []);
        } catch {
          if (!alive) return;
          setRiskPointHistory([]);
        }

        try {
          const reviewRes = await tradeReviewApi.get(id);
          if (!alive) return;
          form.setFieldsValue(reviewRes.data || {});
          setReviewExists(true);
        } catch (e) {
          if (!alive) return;
          if (e.response?.status === 404) {
            setReviewExists(false);
            form.setFieldsValue(reviewInitFields);
          } else {
            message.error('结构化复盘加载失败');
          }
        }
      } catch {
        if (alive) message.error('加载失败');
      }
    };
    loadData();
    return () => {
      alive = false;
    };
  }, [id, isEdit, form]);

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const data = { ...values };
      const reviewData = {};
      TRADE_REVIEW_FIELDS.forEach((field) => {
        reviewData[field] = data[field];
        delete data[field];
      });
      if (data.open_time) data.open_time = data.open_time.format('YYYY-MM-DDTHH:mm:ss');
      if (data.close_time) data.close_time = data.close_time.format('YYYY-MM-DDTHH:mm:ss');
      let tradeId = id;
      if (isEdit) {
        delete data.category;
        await tradeApi.update(id, data);
      } else {
        const createRes = await tradeApi.create(data);
        tradeId = createRes.data?.id;
      }

      if (isEdit) {
        const normalizedReview = {};
        Object.entries(reviewData).forEach(([k, v]) => {
          if (k === 'tags') {
            normalizedReview[k] = normalizeTagList(v);
          } else {
            normalizedReview[k] = typeof v === 'string' ? v.trim() : v;
          }
        });
        const hasReviewData = Object.values(normalizedReview).some((v) => {
          if (Array.isArray(v)) return v.length > 0;
          return v !== null && v !== undefined && v !== '';
        });

        if (tradeId && hasReviewData) {
          await tradeReviewApi.upsert(tradeId, normalizedReview);
          setReviewExists(true);
        } else if (tradeId && reviewExists) {
          await tradeReviewApi.delete(tradeId);
          setReviewExists(false);
        }
      }

      message.success(isEdit ? '更新成功' : '创建成功');
      navigate('/trades');
    } catch (e) {
      message.error('保存失败: ' + (e.response?.data?.error?.message || e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const renderCurrencyFields = () => {
    if (instrumentType !== '加密货币') {
      return (
        <>
          <Col span={8}><Form.Item label="手续费（人民币）" name="commission" rules={[{ required: isClosed, message: '已平仓交易请填写手续费' }]}><InputNumber style={{ width: '100%' }} min={0} /></Form.Item></Col>
          <Col span={8}><Form.Item label="盈亏金额（人民币）" name="pnl" rules={[{ required: isClosed, message: '已平仓交易请填写盈亏金额' }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
        </>
      );
    }

    const convertedCommission = commissionUsdt == null || !usdCnyRate ? null : Number(commissionUsdt) * Number(usdCnyRate);
    const convertedPnl = pnlUsdt == null || !usdCnyRate ? null : Number(pnlUsdt) * Number(usdCnyRate);
    return (
      <>
        <Col span={8}><Form.Item label="手续费（USDT）" name="commission_usdt" rules={[{ required: isClosed, message: '已平仓交易请填写手续费' }]}><InputNumber style={{ width: '100%' }} min={0} /></Form.Item></Col>
        <Col span={8}><Form.Item label="盈亏金额（USDT）" name="pnl_usdt" rules={[{ required: isClosed, message: '已平仓交易请填写盈亏金额' }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
        <Col span={8}>
          <Form.Item
            label="美元兑人民币汇率"
            name="usd_cny_rate"
            rules={[{ required: commissionUsdt != null || pnlUsdt != null, message: '请填写换算汇率' }]}
            extra={exchangeRateMeta?.rate_date ? `自动获取：${exchangeRateMeta.rate_date}` : '可手动调整为成交时汇率'}
          >
            <InputNumber style={{ width: '100%' }} min={0.000001} precision={6} addonAfter="CNY/USD" />
          </Form.Item>
        </Col>
        <Col span={24} style={{ marginTop: -8, marginBottom: 12 }}>
          <Typography.Text type="secondary">
            自动换算人民币：手续费 {convertedCommission == null ? '-' : convertedCommission.toFixed(2)} 元；盈亏 {convertedPnl == null ? '-' : convertedPnl.toFixed(2)} 元
          </Typography.Text>
        </Col>
      </>
    );
  };

  const renderCloseFields = () => (
    <>
      <Col span={8}>
        <Form.Item
          label="平仓时间"
          name="close_time"
          dependencies={['close_price']}
          rules={[({ getFieldValue }) => ({
            validator(_, value) {
              if (getFieldValue('close_price') != null && !value) {
                return Promise.reject(new Error('填写平仓价后，平仓时间为必填项'));
              }
              return Promise.resolve();
            },
          })]}
        >
          <DatePicker showTime style={{ width: '100%' }} />
        </Form.Item>
      </Col>
      <Col span={8}>
        <Form.Item
          label="平仓价"
          name="close_price"
          dependencies={['close_time']}
          rules={[({ getFieldValue }) => ({
            validator(_, value) {
              if (getFieldValue('close_time') && value == null) {
                return Promise.reject(new Error('填写平仓时间后，平仓价为必填项'));
              }
              return Promise.resolve();
            },
          })]}
        >
          <InputNumber style={{ width: '100%' }} />
        </Form.Item>
      </Col>
    </>
  );

  const tabItems = [
    {
      key: '1', label: '成交流水',
      children: isEdit ? (
        /* 编辑模式 Tab 1 */
        <Row gutter={16}>
          {/* 核心字段 */}
          <Col span={8}>
            <Form.Item label="交易类型" name="instrument_type" rules={[{ required: true, message: '请选择交易类型' }]}>
              <Select options={opt(['期货', '加密货币', '股票', '外汇'])} onChange={handleInstrumentTypeChange} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="品种" name="symbol" rules={[{ required: true, message: '请选择品种' }]}>{instrumentSelect}</Form.Item></Col>
          <Col span={8}>
            <Form.Item label="方向" name="direction" rules={[{ required: true }]}>
              <Select options={[{ label: '做多', value: '做多' }, { label: '做空', value: '做空' }]} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="开仓时间" name="open_time" rules={[{ required: true }]}><DatePicker showTime style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="开仓价" name="open_price" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="当前止损点" name="stop_loss_point" rules={[{ required: true, message: '请填写止损点' }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="当前目标点" name="target_point" rules={[{ required: true, message: '请填写目标点' }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="占本金百分比" name="capital_percentage" rules={[{ required: true, message: '请填写占本金百分比' }]}><InputNumber style={{ width: '100%' }} min={0} max={100} addonAfter="%" /></Form.Item></Col>
          <Col span={8}><Form.Item label="合约" name="contract"><Input /></Form.Item></Col>
          {renderCloseFields()}
          <Form.Item shouldUpdate={(prev, curr) => prev.instrument_type !== curr.instrument_type} noStyle>
            {({ getFieldValue }) => {
              const t = getFieldValue('instrument_type');
              if (t === '加密货币') return (
                <Col span={8}><Form.Item label="杠杆倍数" name="leverage"><InputNumber style={{ width: '100%' }} min={1} /></Form.Item></Col>
              );
              return null;
            }}
          </Form.Item>
          {renderCurrencyFields()}

          <Col span={24} style={{ marginTop: 8 }}>
            <Collapse ghost>
              <Panel header={`止损/目标/本金占比调整历史（${riskPointHistory.length}）`} key="risk-point-history">
                {riskPointHistory.length > 0 ? (
                  <Timeline
                    items={riskPointHistory.map((item) => ({
                      children: (
                        <Space direction="vertical" size={0}>
                          <Typography.Text>止损点 {item.stop_loss_point ?? '-'} / 目标点 {item.target_point ?? '-'} / 本金占比 {item.capital_percentage != null ? `${item.capital_percentage}%` : '-'}</Typography.Text>
                          <Typography.Text type="secondary">中国时间 {formatChinaDateTime(item.recorded_at)}</Typography.Text>
                        </Space>
                      ),
                    }))}
                  />
                ) : <Typography.Text type="secondary">暂无调整历史</Typography.Text>}
              </Panel>
            </Collapse>
          </Col>

        </Row>
      ) : (
        /* 新建模式 Tab 1 */
        <Row gutter={16}>
          {/* 核心必填字段 */}
          <Col span={8}>
            <Form.Item label="交易类型" name="instrument_type" rules={[{ required: true, message: '请选择交易类型' }]}>
              <Select options={opt(['期货', '加密货币', '股票', '外汇'])} onChange={handleInstrumentTypeChange} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="品种" name="symbol" rules={[{ required: true, message: '请选择品种' }]}>{instrumentSelect}</Form.Item></Col>
          <Col span={8}>
            <Form.Item label="方向" name="direction" rules={[{ required: true }]}>
              <Select options={[{ label: '做多', value: '做多' }, { label: '做空', value: '做空' }]} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="开仓时间" name="open_time" rules={[{ required: true }]}><DatePicker showTime style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="开仓价" name="open_price" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="止损点" name="stop_loss_point" rules={[{ required: true, message: '请填写止损点' }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="目标点" name="target_point" rules={[{ required: true, message: '请填写目标点' }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="占本金百分比" name="capital_percentage" rules={[{ required: true, message: '请填写占本金百分比' }]}><InputNumber style={{ width: '100%' }} min={0} max={100} addonAfter="%" /></Form.Item></Col>
          <Form.Item shouldUpdate={(prev, curr) => prev.instrument_type !== curr.instrument_type} noStyle>
            {({ getFieldValue }) => {
              const t = getFieldValue('instrument_type');
              if (t === '加密货币') return (
                <Col span={8}><Form.Item label="杠杆倍数" name="leverage" rules={[{ required: true, message: '请填写杠杆倍数' }]}><InputNumber style={{ width: '100%' }} min={1} /></Form.Item></Col>
              );
              return null;
            }}
          </Form.Item>

          <Col span={8}><Form.Item label="合约" name="contract"><Input /></Form.Item></Col>
          {renderCloseFields()}
          {renderCurrencyFields()}
        </Row>
      ),
    },
    {
      key: '2', label: '交易决策',
      children: (
        <Row gutter={16}>
          <Col span={12}><Form.Item label="入场逻辑" name="entry_logic"><TextArea rows={3} /></Form.Item></Col>
          <Col span={12}><Form.Item label="出场逻辑" name="exit_logic"><TextArea rows={3} /></Form.Item></Col>
          <Col span={8}>
            <Form.Item label="策略类型" name="strategy_type">
              <Select allowClear options={opt(['趋势突破', '回调接力', '震荡反转', '消息驱动', '价差逻辑', '日内短线', '其他'])} />
            </Form.Item>
          </Col>
          <Col span={24}><Form.Item label="核心信号" name="core_signal"><TextArea rows={2} /></Form.Item></Col>
        </Row>
      ),
    },
    {
      key: '5', label: '结构化复盘',
      children: (
        <Row gutter={16}>
          <Col span={24}><Divider>结构化复盘</Divider></Col>
          <Col span={12}>
            <Form.Item label="机会结构" name="opportunity_structure">
              <Select
                allowClear
                options={taxonomyOptionsWithZh('opportunity_structure', reviewTaxonomy.opportunity_structure)}
                placeholder="选择机会结构"
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="优势来源" name="edge_source">
              <Select
                allowClear
                options={taxonomyOptionsWithZh('edge_source', reviewTaxonomy.edge_source)}
                placeholder="选择优势来源"
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="失败类型" name="failure_type">
              <Select
                allowClear
                options={taxonomyOptionsWithZh('failure_type', reviewTaxonomy.failure_type)}
                placeholder="选择失败类型"
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="复盘结论" name="review_conclusion">
              <Select
                allowClear
                options={taxonomyOptionsWithZh('review_conclusion', reviewTaxonomy.review_conclusion)}
                placeholder="选择复盘结论"
              />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item label="复盘标签" name="tags">
              <Select mode="tags" tokenSeparators={[',', '，']} placeholder="输入并回车添加标签" />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item name="entry_thesis" hidden><Input /></Form.Item>
            <Form.Item name="invalidation_valid_evidence" hidden><Input /></Form.Item>
            <Form.Item name="invalidation_trigger_evidence" hidden><Input /></Form.Item>
            <Form.Item name="invalidation_boundary" hidden><Input /></Form.Item>
            <Form.Item name="management_actions" hidden><Input /></Form.Item>
            <Form.Item name="exit_reason" hidden><Input /></Form.Item>
            <Form.Item name="research_notes" hidden><Input /></Form.Item>
            <Form.Item noStyle shouldUpdate>
              {() => (
                <Form.Item label="图文录入">
                  <ResearchContentPanel
                    editing
                    showStandardFields={false}
                    title="交易图文研究"
                    value={form.getFieldValue('research_notes') || ''}
                    onChange={(next) => form.setFieldValue('research_notes', next)}
                  />
                </Form.Item>
              )}
            </Form.Item>
          </Col>
        </Row>
      ),
    },
  ];
  const displayedTabItems = isEdit ? tabItems : tabItems.filter((item) => ['1', '2'].includes(item.key));

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/trades')}>返回</Button>
        <h2 style={{ margin: 0 }}>{isEdit ? '编辑交易' : '新建交易'}</h2>
      </Space>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Tabs items={displayedTabItems} />
        <Form.Item style={{ marginTop: 16 }}>
          <Button type="primary" htmlType="submit" loading={loading} icon={<SaveOutlined />} size="large">保存</Button>
        </Form.Item>
      </Form>
    </div>
  );
}
