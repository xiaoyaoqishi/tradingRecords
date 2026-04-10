import { useState, useEffect } from 'react';
import {
  Form, Input, InputNumber, Select, DatePicker, Switch, Button,
  Tabs, message, Space, Row, Col, Divider,
} from 'antd';
import { SaveOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { tradeApi, tradeReviewApi, tradeSourceApi } from '../api';
import { taxonomyOptionsWithZh } from '../features/trading/localization';
import dayjs from 'dayjs';

const { TextArea } = Input;

const ERROR_TAGS = [
  '无计划开仓', '追涨杀跌', '止损不坚决', '提前止盈', '盈利单拿不住',
  '亏损单死扛', '仓位过大', '频繁交易', '情绪化交易', '与策略不符',
  '逆势操作', '低流动性误判', '夜盘执行变形',
];

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

const TRADE_SOURCE_FIELDS = [
  'broker_name',
  'source_label',
  'import_channel',
  'parser_version',
  'source_note_snapshot',
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
  const [loading, setLoading] = useState(false);
  const [reviewExists, setReviewExists] = useState(false);
  const [sourceExists, setSourceExists] = useState(false);
  const [sourceDerivedFromNotes, setSourceDerivedFromNotes] = useState(true);
  const [reviewTaxonomy, setReviewTaxonomy] = useState(EMPTY_REVIEW_TAXONOMY);
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = !!id;

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
          setReviewTaxonomy(EMPTY_REVIEW_TAXONOMY);
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    const reviewInitFields = Object.fromEntries(TRADE_REVIEW_FIELDS.map((f) => [f, undefined]));
    const sourceInitFields = Object.fromEntries(TRADE_SOURCE_FIELDS.map((f) => [f, undefined]));

    const loadData = async () => {
      if (!isEdit) {
        setReviewExists(false);
        setSourceExists(false);
        setSourceDerivedFromNotes(true);
        form.setFieldsValue({ ...reviewInitFields, ...sourceInitFields });
        return;
      }
      try {
        const tradeRes = await tradeApi.get(id);
        if (!alive) return;
        const d = { ...tradeRes.data };
        if (d.trade_date) d.trade_date = dayjs(d.trade_date);
        if (d.open_time) d.open_time = dayjs(d.open_time);
        if (d.close_time) d.close_time = dayjs(d.close_time);
        if (d.error_tags) {
          try { d.error_tags = JSON.parse(d.error_tags); } catch { /* keep as-is */ }
        }
        form.setFieldsValue(d);

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
        try {
          const sourceRes = await tradeSourceApi.get(id);
          if (!alive) return;
          form.setFieldsValue(sourceRes.data || {});
          setSourceExists(!!sourceRes.data?.exists_in_db);
          setSourceDerivedFromNotes(!!sourceRes.data?.derived_from_notes);
        } catch {
          if (!alive) return;
          setSourceExists(false);
          setSourceDerivedFromNotes(true);
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
      const sourceData = {};
      TRADE_SOURCE_FIELDS.forEach((field) => {
        sourceData[field] = data[field];
        delete data[field];
      });

      if (data.trade_date) data.trade_date = data.trade_date.format('YYYY-MM-DD');
      if (data.open_time) data.open_time = data.open_time.format('YYYY-MM-DDTHH:mm:ss');
      if (data.close_time) data.close_time = data.close_time.format('YYYY-MM-DDTHH:mm:ss');
      if (Array.isArray(data.error_tags)) data.error_tags = JSON.stringify(data.error_tags);

      let tradeId = id;
      if (isEdit) {
        await tradeApi.update(id, data);
      } else {
        const createRes = await tradeApi.create(data);
        tradeId = createRes.data?.id;
      }

      const normalizedReview = {};
      Object.entries(reviewData).forEach(([k, v]) => {
        normalizedReview[k] = typeof v === 'string' ? v.trim() : v;
      });
      const hasReviewData = Object.values(normalizedReview).some((v) => {
        if (Array.isArray(v)) return v.length > 0;
        return v !== null && v !== undefined && v !== '';
      });

      if (tradeId && hasReviewData) {
        await tradeReviewApi.upsert(tradeId, normalizedReview);
        setReviewExists(true);
      } else if (tradeId && isEdit && reviewExists) {
        await tradeReviewApi.delete(tradeId);
        setReviewExists(false);
      }

      const normalizedSource = {};
      Object.entries(sourceData).forEach(([k, v]) => {
        if (typeof v === 'string') {
          const trimmed = v.trim();
          normalizedSource[k] = trimmed || null;
        } else {
          normalizedSource[k] = v ?? null;
        }
      });
      const hasSourceData = Object.values(normalizedSource).some((v) => v !== null && v !== undefined && v !== '');
      if (tradeId && (hasSourceData || (isEdit && sourceExists))) {
        await tradeSourceApi.upsert(tradeId, {
          ...normalizedSource,
          source_note_snapshot: normalizedSource.source_note_snapshot || (typeof data.notes === 'string' ? data.notes.trim() || null : null),
          derived_from_notes: false,
        });
        setSourceExists(true);
        setSourceDerivedFromNotes(false);
      }

      message.success(isEdit ? '更新成功' : '创建成功');
      navigate('/trades');
    } catch (e) {
      message.error('保存失败: ' + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const tabItems = [
    {
      key: '1', label: '成交流水',
      children: (
        <Row gutter={16}>
          <Col span={8}><Form.Item label="交易日期" name="trade_date" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}>
            <Form.Item label="交易类型" name="instrument_type" rules={[{ required: true }]}>
              <Select options={opt(['期货', '加密货币', '股票', '外汇'])} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="品种" name="symbol" rules={[{ required: true }]}><Input /></Form.Item></Col>
          <Col span={8}><Form.Item label="合约" name="contract"><Input /></Form.Item></Col>
          <Col span={8}>
            <Form.Item label="品种分类" name="category">
              <Select allowClear options={opt(['黑色', '能化', '有色', '农产品', '股指', '国债', '加密货币', '外汇', '其他'])} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="方向" name="direction" rules={[{ required: true }]}>
              <Select options={[{ label: '做多', value: '做多' }, { label: '做空', value: '做空' }]} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="开仓时间" name="open_time" rules={[{ required: true }]}><DatePicker showTime style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="平仓时间" name="close_time"><DatePicker showTime style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}>
            <Form.Item label="状态" name="status" initialValue="open">
              <Select options={[{ label: '持仓', value: 'open' }, { label: '已平', value: 'closed' }]} />
            </Form.Item>
          </Col>
          <Col span={6}><Form.Item label="开仓价" name="open_price" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={6}><Form.Item label="平仓价" name="close_price"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={6}><Form.Item label="手数" name="quantity" rules={[{ required: true }]}><InputNumber style={{ width: '100%' }} min={0} /></Form.Item></Col>
          <Col span={6}><Form.Item label="保证金" name="margin"><InputNumber style={{ width: '100%' }} min={0} /></Form.Item></Col>
          <Col span={6}><Form.Item label="手续费" name="commission"><InputNumber style={{ width: '100%' }} min={0} /></Form.Item></Col>
          <Col span={6}><Form.Item label="滑点" name="slippage"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={6}><Form.Item label="盈亏金额" name="pnl"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={6}><Form.Item label="盈亏点数" name="pnl_points"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="持仓时长" name="holding_duration"><Input /></Form.Item></Col>
          <Col span={8}>
            <Form.Item label="交易时段" name="trading_session">
              <Select allowClear options={opt(['上午', '下午', '夜盘前段', '夜盘后段'])} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="是否隔夜" name="is_overnight" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={24}><Divider>期货特有字段</Divider></Col>
          <Col span={6}>
            <Form.Item label="主力/次主力" name="is_main_contract">
              <Select allowClear options={opt(['主力', '次主力', '远月'])} />
            </Form.Item>
          </Col>
          <Col span={6}><Form.Item label="临近交割月" name="is_near_delivery" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="换月阶段" name="is_contract_switch" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="高波动时段" name="is_high_volatility" valuePropName="checked"><Switch /></Form.Item></Col>
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
          <Col span={8}>
            <Form.Item label="市场状态" name="market_condition">
              <Select allowClear options={opt(['趋势', '震荡', '加速', '衰竭', '假突破', '低波动', '高波动'])} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="所属周期" name="timeframe">
              <Select allowClear options={opt(['1分钟', '5分钟', '15分钟', '30分钟', '1小时', '4小时', '日线', '日内波段', '隔夜趋势'])} />
            </Form.Item>
          </Col>
          <Col span={24}><Form.Item label="核心信号" name="core_signal"><TextArea rows={2} /></Form.Item></Col>
          <Col span={8}><Form.Item label="止损设定" name="stop_loss_plan"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="目标位设定" name="target_plan"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={8}><Form.Item label="按计划执行" name="followed_plan" valuePropName="checked"><Switch /></Form.Item></Col>
        </Row>
      ),
    },
    {
      key: '3', label: '行为纪律',
      children: (
        <Row gutter={16}>
          <Col span={6}><Form.Item label="计划内交易" name="is_planned" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="临时起意" name="is_impulsive" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="追单" name="is_chasing" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="扛单" name="is_holding_loss" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="提前止盈" name="is_early_profit" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="扩大止损" name="is_extended_stop" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="重仓" name="is_overweight" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={6}><Form.Item label="报复性交易" name="is_revenge" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={8}><Form.Item label="情绪影响" name="is_emotional" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={8}>
            <Form.Item label="心理状态" name="mental_state">
              <Select allowClear options={opt(['平静', '焦虑', '急躁', '犹豫', '兴奋', '恐惧'])} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="身体状态" name="physical_state">
              <Select allowClear options={opt(['精力集中', '正常', '疲劳', '睡眠不足'])} />
            </Form.Item>
          </Col>
        </Row>
      ),
    },
    {
      key: '4', label: '交易前中后',
      children: (
        <Row gutter={16}>
          <Col span={24}><Divider>交易前</Divider></Col>
          <Col span={8}><Form.Item label="看到的机会" name="pre_opportunity"><TextArea rows={2} /></Form.Item></Col>
          <Col span={8}><Form.Item label="为什么胜率高" name="pre_win_reason"><TextArea rows={2} /></Form.Item></Col>
          <Col span={8}><Form.Item label="如果错了，错在哪" name="pre_risk"><TextArea rows={2} /></Form.Item></Col>
          <Col span={24}><Divider>交易中</Divider></Col>
          <Col span={12}><Form.Item label="走势是否符合预期" name="during_match_expectation"><TextArea rows={2} /></Form.Item></Col>
          <Col span={12}><Form.Item label="是否改变计划及原因" name="during_plan_changed"><TextArea rows={2} /></Form.Item></Col>
          <Col span={24}><Divider>交易后</Divider></Col>
          <Col span={8}>
            <Form.Item label="交易质量" name="post_quality">
              <Select allowClear options={opt(['好交易赚钱', '好交易亏钱', '坏交易赚钱', '坏交易亏钱'])} />
            </Form.Item>
          </Col>
          <Col span={8}><Form.Item label="重来还做吗" name="post_repeat" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={8}><Form.Item label="盈利可复制吗" name="post_replicable" valuePropName="checked"><Switch /></Form.Item></Col>
          <Col span={24}><Form.Item label="根因分析" name="post_root_cause"><TextArea rows={2} /></Form.Item></Col>
        </Row>
      ),
    },
    {
      key: '5', label: '标签与复盘',
      children: (
        <Row gutter={16}>
          <Col span={24}><Divider>结构化复盘（TradeReview）</Divider></Col>
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
          <Col span={24}><Form.Item label="入场论点" name="entry_thesis"><TextArea rows={2} /></Form.Item></Col>
          <Col span={12}><Form.Item label="有效证据" name="invalidation_valid_evidence"><TextArea rows={2} /></Form.Item></Col>
          <Col span={12}><Form.Item label="失效证据" name="invalidation_trigger_evidence"><TextArea rows={2} /></Form.Item></Col>
          <Col span={24}><Form.Item label="相似但不同边界" name="invalidation_boundary"><TextArea rows={2} /></Form.Item></Col>
          <Col span={24}><Form.Item label="管理动作" name="management_actions"><TextArea rows={2} /></Form.Item></Col>
          <Col span={24}><Form.Item label="离场原因" name="exit_reason"><TextArea rows={2} /></Form.Item></Col>
          <Col span={24}>
            <Form.Item label="复盘标签" name="tags">
              <Select mode="tags" tokenSeparators={[',', '，']} placeholder="输入并回车添加标签" />
            </Form.Item>
          </Col>
          <Col span={24}><Form.Item label="研究记录" name="research_notes"><TextArea rows={3} /></Form.Item></Col>
          <Col span={24}><Divider>来源元数据（TradeSourceMetadata）</Divider></Col>
          <Col span={12}><Form.Item label="券商" name="broker_name"><Input placeholder="例如：宏源期货" /></Form.Item></Col>
          <Col span={12}><Form.Item label="来源标签" name="source_label"><Input placeholder="例如：日结单粘贴导入" /></Form.Item></Col>
          <Col span={12}><Form.Item label="导入通道" name="import_channel"><Input placeholder="例如：paste_import" /></Form.Item></Col>
          <Col span={12}><Form.Item label="解析版本" name="parser_version"><Input placeholder="例如：paste_v1" /></Form.Item></Col>
          <Col span={24}><Form.Item label="来源快照" name="source_note_snapshot"><TextArea rows={2} placeholder="可选：记录来源解析快照" /></Form.Item></Col>
          <Col span={24}>
            <div style={{ color: '#888', fontSize: 12 }}>
              {isEdit
                ? (sourceExists ? '当前已存在显式 source metadata' : (sourceDerivedFromNotes ? '当前展示为 notes 回退结果，保存后将写入显式 metadata' : '当前尚无 source metadata'))
                : '新建交易时可直接填写 source metadata（可选）'}
            </div>
          </Col>
          <Col span={24}><Divider>兼容字段（Legacy 次级）</Divider></Col>
          <Col span={24}>
            <Form.Item label="错误标签" name="error_tags">
              <Select mode="multiple" allowClear options={opt(ERROR_TAGS)} />
            </Form.Item>
          </Col>
          <Col span={24}><Form.Item label="复盘一句话" name="review_note"><TextArea rows={3} /></Form.Item></Col>
          <Col span={24}><Form.Item label="备注" name="notes"><TextArea rows={3} /></Form.Item></Col>
        </Row>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/trades')}>返回</Button>
        <h2 style={{ margin: 0 }}>{isEdit ? '编辑交易' : '新建交易'}</h2>
      </Space>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Tabs items={tabItems} />
        <Form.Item style={{ marginTop: 16 }}>
          <Button type="primary" htmlType="submit" loading={loading} icon={<SaveOutlined />} size="large">保存</Button>
        </Form.Item>
      </Form>
    </div>
  );
}
