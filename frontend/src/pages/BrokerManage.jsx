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
  Segmented,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { brokerApi, knowledgeApi, noteApi, notebookApi } from '../api';
import {
  KNOWLEDGE_CATEGORY_ZH,
  KNOWLEDGE_PRIORITY_ZH,
  KNOWLEDGE_STATUS_ZH,
  dictToOptions,
  mapLabel,
} from '../features/trading/localization';
import { formatInstrumentDisplay, normalizeTagList } from '../features/trading/display';
import ReadEditActions from '../features/trading/components/ReadEditActions';
import './BrokerManage.css';

const { TextArea, Search } = Input;

const KNOWLEDGE_STATUS_OPTIONS = dictToOptions(KNOWLEDGE_STATUS_ZH);
const KNOWLEDGE_PRIORITY_OPTIONS = dictToOptions(KNOWLEDGE_PRIORITY_ZH);

function tagsToSummary(raw) {
  const tags = normalizeTagList(raw);
  return tags.length ? tags.join('、') : '';
}

function normalizeKnowledgePayload(values) {
  return {
    ...values,
    category: values.category || 'pattern_dictionary',
    title: values.title?.trim() || '',
    summary: values.summary?.trim() || null,
    content: values.content?.trim() || null,
    tags: normalizeTagList(values.tags),
    related_symbol: values.related_symbol?.trim() || null,
    related_pattern: values.related_pattern?.trim() || null,
    related_regime: values.related_regime?.trim() || null,
    status: values.status || 'active',
    priority: values.priority || 'medium',
    next_action: values.next_action?.trim() || null,
    source_ref: values.source_ref?.trim() || null,
    due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : null,
    related_note_ids: normalizeNoteIdList(values.related_note_ids),
  };
}

function normalizeNoteIdList(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  const seen = new Set();
  for (const item of raw) {
    const id = Number(item);
    if (!Number.isInteger(id) || id <= 0 || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

function mergeNoteOptions(base, extra) {
  const out = [];
  const seen = new Set();
  for (const row of [...(base || []), ...(extra || [])]) {
    if (!row || !Number.isInteger(Number(row.value))) continue;
    const value = Number(row.value);
    if (seen.has(value)) continue;
    seen.add(value);
    out.push({ value, label: row.label || `文档 #${value}` });
  }
  return out;
}

function buildNotebookPath(notebookId, notebookMap) {
  if (!notebookId || !(notebookMap instanceof Map) || notebookMap.size === 0) return '';
  const parts = [];
  let currentId = notebookId;
  let guard = 0;
  while (currentId && guard < 40) {
    const node = notebookMap.get(currentId);
    if (!node) break;
    const name = (node.name || '').trim();
    if (name) parts.push(name);
    currentId = node.parent_id || null;
    guard += 1;
  }
  return parts.reverse().join('-');
}

function toDocOption(row, notebookMap) {
  const title = ((row?.title || '').trim()) || '无标题';
  const path = buildNotebookPath(row?.notebook_id, notebookMap);
  return {
    value: Number(row?.id),
    label: path ? `${path}-${title}` : title,
  };
}

function collectDescendantNotebookIds(rootIds, notebookRows) {
  const childMap = new Map();
  for (const nb of notebookRows || []) {
    const pid = nb?.parent_id || null;
    if (!childMap.has(pid)) childMap.set(pid, []);
    childMap.get(pid).push(nb.id);
  }
  const out = new Set();
  const queue = [...rootIds];
  while (queue.length) {
    const id = queue.shift();
    if (!id || out.has(id)) continue;
    out.add(id);
    const children = childMap.get(id) || [];
    for (const childId of children) queue.push(childId);
  }
  return out;
}

function normalizeBrokerPayload(values) {
  return {
    name: values.name?.trim() || '',
    account: values.account?.trim() || null,
    password: values.password?.trim() || null,
    extra_info: values.extra_info?.trim() || null,
    notes: values.notes?.trim() || null,
  };
}

export default function InfoMaintain() {
  const [moduleKey, setModuleKey] = useState('knowledge');

  const [knowledgeRows, setKnowledgeRows] = useState([]);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeSaving, setKnowledgeSaving] = useState(false);
  const [knowledgeEditing, setKnowledgeEditing] = useState(false);
  const [selectedKnowledgeId, setSelectedKnowledgeId] = useState(null);
  const [knowledgeFilters, setKnowledgeFilters] = useState({ category: undefined, status: 'active', tag: undefined, q: '' });
  const [knowledgeCategories, setKnowledgeCategories] = useState([]);
  const [knowledgeDocOptions, setKnowledgeDocOptions] = useState([]);
  const [knowledgeDocSearching, setKnowledgeDocSearching] = useState(false);
  const [knowledgeNotebookMap, setKnowledgeNotebookMap] = useState(new Map());
  const [knowledgeForm] = Form.useForm();

  const [brokerRows, setBrokerRows] = useState([]);
  const [brokerLoading, setBrokerLoading] = useState(false);
  const [brokerSaving, setBrokerSaving] = useState(false);
  const [brokerEditing, setBrokerEditing] = useState(false);
  const [selectedBrokerId, setSelectedBrokerId] = useState(null);
  const [brokerForm] = Form.useForm();

  const selectedKnowledge = useMemo(
    () => knowledgeRows.find((x) => x.id === selectedKnowledgeId) || null,
    [knowledgeRows, selectedKnowledgeId]
  );

  const selectedBroker = useMemo(
    () => brokerRows.find((x) => x.id === selectedBrokerId) || null,
    [brokerRows, selectedBrokerId]
  );

  const knowledgeCategoryOptions = useMemo(() => {
    const map = { ...KNOWLEDGE_CATEGORY_ZH };
    for (const item of knowledgeCategories) {
      if (item && !map[item]) map[item] = item;
    }
    return Object.entries(map).map(([value, label]) => ({ value, label }));
  }, [knowledgeCategories]);

  const knowledgeTagOptions = useMemo(() => {
    const set = new Set();
    knowledgeRows.forEach((item) => normalizeTagList(item.tags || item.tags_text).forEach((tag) => set.add(tag)));
    return Array.from(set).map((x) => ({ value: x, label: x }));
  }, [knowledgeRows]);

  const loadKnowledgeCategories = async () => {
    try {
      const res = await knowledgeApi.categories();
      setKnowledgeCategories(res.data?.items || []);
    } catch {
      setKnowledgeCategories([]);
    }
  };

  const loadKnowledgeDocs = async () => {
    try {
      const nbRes = await notebookApi.list();
      const notebookRows = Array.isArray(nbRes.data) ? nbRes.data : [];
      const notebookMap = new Map(notebookRows.map((row) => [row.id, row]));
      setKnowledgeNotebookMap(notebookMap);

      const caseRootIds = notebookRows
        .filter((row) => ((row.name || '').trim() === '案例'))
        .map((row) => row.id);
      const caseNotebookIds = collectDescendantNotebookIds(caseRootIds, notebookRows);

      const pageSize = 200;
      let page = 1;
      let allRows = [];
      while (true) {
        const res = await noteApi.list({ note_type: 'doc', page, size: pageSize });
        const rows = Array.isArray(res.data) ? res.data : [];
        allRows = allRows.concat(rows);
        if (rows.length < pageSize) break;
        page += 1;
      }
      const defaultRows = allRows.filter((row) => caseNotebookIds.has(row.notebook_id));
      const options = defaultRows.map((row) => toDocOption(row, notebookMap));
      setKnowledgeDocOptions(mergeNoteOptions([], options));
    } catch {
      message.error('文档列表加载失败');
    }
  };

  const searchKnowledgeDocs = async (kw) => {
    const keyword = (kw || '').trim();
    if (!keyword) return;
    try {
      setKnowledgeDocSearching(true);
      const res = await noteApi.search({ q: keyword, note_type: 'doc', limit: 80 });
      const rows = Array.isArray(res.data) ? res.data : [];
      const options = rows.map((row) => toDocOption(row, knowledgeNotebookMap));
      setKnowledgeDocOptions((prev) => mergeNoteOptions(prev, options));
    } catch {
      message.error('文档搜索失败');
    } finally {
      setKnowledgeDocSearching(false);
    }
  };

  const loadKnowledge = async (nextSelectedId = null) => {
    setKnowledgeLoading(true);
    try {
      const params = { size: 200 };
      if (knowledgeFilters.category) params.category = knowledgeFilters.category;
      if (knowledgeFilters.status) params.status = knowledgeFilters.status;
      if (knowledgeFilters.tag) params.tag = knowledgeFilters.tag;
      if (knowledgeFilters.q?.trim()) params.q = knowledgeFilters.q.trim();
      const res = await knowledgeApi.list(params);
      const rows = res.data || [];
      setKnowledgeRows(rows);
      const target = nextSelectedId ?? selectedKnowledgeId;
      if (!rows.length) {
        setSelectedKnowledgeId(null);
        return;
      }
      if (target && rows.some((x) => x.id === target)) {
        setSelectedKnowledgeId(target);
      } else {
        setSelectedKnowledgeId(rows[0].id);
      }
    } catch {
      message.error('知识条目加载失败');
    } finally {
      setKnowledgeLoading(false);
    }
  };

  const loadBrokers = async (nextSelectedId = null) => {
    setBrokerLoading(true);
    try {
      const res = await brokerApi.list();
      const rows = res.data || [];
      setBrokerRows(rows);
      const target = nextSelectedId ?? selectedBrokerId;
      if (!rows.length) {
        setSelectedBrokerId(null);
        return;
      }
      if (target && rows.some((x) => x.id === target)) {
        setSelectedBrokerId(target);
      } else {
        setSelectedBrokerId(rows[0].id);
      }
    } catch {
      message.error('券商列表加载失败');
    } finally {
      setBrokerLoading(false);
    }
  };

  useEffect(() => {
    loadKnowledgeCategories();
    loadKnowledgeDocs();
    loadKnowledge();
    loadBrokers();
  }, []);

  useEffect(() => {
    loadKnowledge();
  }, [knowledgeFilters.category, knowledgeFilters.status, knowledgeFilters.tag, knowledgeFilters.q]);

  useEffect(() => {
    if (!selectedKnowledge) {
      knowledgeForm.resetFields();
      knowledgeForm.setFieldsValue({
        category: 'pattern_dictionary',
        status: 'active',
        priority: 'medium',
        tags: [],
        related_note_ids: [],
      });
      return;
    }
    const selectedDocOptions = (selectedKnowledge.related_notes || []).map((note) => ({
      value: Number(note.id),
      label: toDocOption(note, knowledgeNotebookMap).label,
    }));
    setKnowledgeDocOptions((prev) => mergeNoteOptions(prev, selectedDocOptions));
    knowledgeForm.setFieldsValue({
      ...selectedKnowledge,
      tags: normalizeTagList(selectedKnowledge.tags || selectedKnowledge.tags_text),
      related_note_ids: (selectedKnowledge.related_notes || []).map((note) => note.id),
      due_date: selectedKnowledge.due_date ? dayjs(selectedKnowledge.due_date) : null,
    });
  }, [selectedKnowledge, knowledgeForm, knowledgeNotebookMap]);

  useEffect(() => {
    if (!selectedBroker) {
      brokerForm.resetFields();
      return;
    }
    brokerForm.setFieldsValue({
      name: selectedBroker.name || '',
      account: selectedBroker.account || '',
      password: selectedBroker.password || '',
      extra_info: selectedBroker.extra_info || '',
      notes: selectedBroker.notes || '',
    });
  }, [selectedBroker, brokerForm]);

  const createKnowledge = () => {
    setSelectedKnowledgeId(null);
    knowledgeForm.resetFields();
    knowledgeForm.setFieldsValue({
      category: knowledgeFilters.category || 'pattern_dictionary',
      status: 'active',
      priority: 'medium',
      tags: [],
      related_note_ids: [],
    });
    setKnowledgeEditing(true);
  };

  const saveKnowledge = async () => {
    try {
      const values = await knowledgeForm.validateFields();
      const payload = normalizeKnowledgePayload(values);
      if (!payload.title) {
        message.warning('标题不能为空');
        return;
      }
      setKnowledgeSaving(true);
      let saved;
      if (selectedKnowledgeId) {
        const res = await knowledgeApi.update(selectedKnowledgeId, payload);
        saved = res.data;
      } else {
        const res = await knowledgeApi.create(payload);
        saved = res.data;
      }
      message.success(selectedKnowledgeId ? '知识条目已更新' : '知识条目已创建');
      await loadKnowledge(saved.id);
      setSelectedKnowledgeId(saved.id);
      setKnowledgeEditing(false);
      await loadKnowledgeCategories();
    } catch (e) {
      if (!e?.errorFields) {
        message.error(e?.response?.data?.detail || '保存失败');
      }
    } finally {
      setKnowledgeSaving(false);
    }
  };

  const deleteKnowledge = async () => {
    if (!selectedKnowledgeId) return;
    try {
      await knowledgeApi.delete(selectedKnowledgeId);
      message.success('知识条目已删除');
      await loadKnowledge();
      setKnowledgeEditing(false);
      await loadKnowledgeCategories();
    } catch {
      message.error('删除失败');
    }
  };

  const createBroker = () => {
    setSelectedBrokerId(null);
    brokerForm.resetFields();
    setBrokerEditing(true);
  };

  const saveBroker = async () => {
    try {
      const values = await brokerForm.validateFields();
      const payload = normalizeBrokerPayload(values);
      if (!payload.name) {
        message.warning('名称不能为空');
        return;
      }
      setBrokerSaving(true);
      let saved;
      if (selectedBrokerId) {
        const res = await brokerApi.update(selectedBrokerId, payload);
        saved = res.data;
      } else {
        const res = await brokerApi.create(payload);
        saved = res.data;
      }
      message.success(selectedBrokerId ? '券商信息已更新' : '券商信息已创建');
      await loadBrokers(saved.id);
      setSelectedBrokerId(saved.id);
      setBrokerEditing(false);
    } catch (e) {
      if (!e?.errorFields) {
        message.error(e?.response?.data?.detail || '保存失败');
      }
    } finally {
      setBrokerSaving(false);
    }
  };

  const deleteBroker = async () => {
    if (!selectedBrokerId) return;
    try {
      await brokerApi.delete(selectedBrokerId);
      message.success('券商信息已删除');
      await loadBrokers();
      setBrokerEditing(false);
    } catch {
      message.error('删除失败');
    }
  };

  const selectKnowledge = (id) => {
    setSelectedKnowledgeId(id);
    setKnowledgeEditing(false);
  };

  const startEditKnowledge = () => {
    if (!selectedKnowledge) return;
    knowledgeForm.setFieldsValue({
      ...selectedKnowledge,
      tags: normalizeTagList(selectedKnowledge.tags || selectedKnowledge.tags_text),
      related_note_ids: (selectedKnowledge.related_notes || []).map((note) => note.id),
      due_date: selectedKnowledge.due_date ? dayjs(selectedKnowledge.due_date) : null,
    });
    setKnowledgeEditing(true);
  };

  const cancelKnowledgeEdit = () => {
    if (selectedKnowledge) {
      knowledgeForm.setFieldsValue({
        ...selectedKnowledge,
        tags: normalizeTagList(selectedKnowledge.tags || selectedKnowledge.tags_text),
        related_note_ids: (selectedKnowledge.related_notes || []).map((note) => note.id),
        due_date: selectedKnowledge.due_date ? dayjs(selectedKnowledge.due_date) : null,
      });
      setKnowledgeEditing(false);
      return;
    }
    knowledgeForm.resetFields();
    knowledgeForm.setFieldsValue({
      category: knowledgeFilters.category || 'pattern_dictionary',
      status: 'active',
      priority: 'medium',
      tags: [],
      related_note_ids: [],
    });
    setKnowledgeEditing(false);
  };

  const selectBroker = (id) => {
    setSelectedBrokerId(id);
    setBrokerEditing(false);
  };

  const startEditBroker = () => {
    if (!selectedBroker) return;
    brokerForm.setFieldsValue({
      name: selectedBroker.name || '',
      account: selectedBroker.account || '',
      password: selectedBroker.password || '',
      extra_info: selectedBroker.extra_info || '',
      notes: selectedBroker.notes || '',
    });
    setBrokerEditing(true);
  };

  const cancelBrokerEdit = () => {
    if (selectedBroker) {
      brokerForm.setFieldsValue({
        name: selectedBroker.name || '',
        account: selectedBroker.account || '',
        password: selectedBroker.password || '',
        extra_info: selectedBroker.extra_info || '',
        notes: selectedBroker.notes || '',
      });
      setBrokerEditing(false);
      return;
    }
    brokerForm.resetFields();
    setBrokerEditing(false);
  };

  const selectedKnowledgeTags = normalizeTagList(selectedKnowledge?.tags || selectedKnowledge?.tags_text);
  const selectedKnowledgeSymbolLabel = selectedKnowledge?.related_symbol
    ? formatInstrumentDisplay(selectedKnowledge.related_symbol, selectedKnowledge.related_symbol)
    : '-';

  return (
    <div className="maintain-workspace">
      <Card className="maintain-toolbar" bodyStyle={{ padding: 12 }}>
        <div className="maintain-toolbar-inner">
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>信息维护工作台</Typography.Title>
            <Typography.Text type="secondary">把复盘结论沉淀为可复用知识，券商维护作为来源兼容能力保留。</Typography.Text>
          </div>
          <Segmented
            value={moduleKey}
            onChange={setModuleKey}
            options={[
              { label: '知识库', value: 'knowledge' },
              { label: '券商来源', value: 'broker' },
            ]}
          />
        </div>
      </Card>

      {moduleKey === 'knowledge' && (
        <>
          <Card className="maintain-filter-card" bodyStyle={{ padding: 12 }}>
            <Space wrap>
              <Select
                allowClear
                value={knowledgeFilters.category}
                options={knowledgeCategoryOptions}
                placeholder="分类"
                style={{ width: 220 }}
                onChange={(v) => setKnowledgeFilters((p) => ({ ...p, category: v }))}
              />
              <Select
                allowClear
                value={knowledgeFilters.status}
                options={KNOWLEDGE_STATUS_OPTIONS}
                placeholder="状态"
                style={{ width: 140 }}
                onChange={(v) => setKnowledgeFilters((p) => ({ ...p, status: v }))}
              />
              <Select
                allowClear
                value={knowledgeFilters.tag}
                options={knowledgeTagOptions}
                placeholder="标签"
                style={{ width: 180 }}
                onChange={(v) => setKnowledgeFilters((p) => ({ ...p, tag: v }))}
              />
              <Search
                allowClear
                placeholder="搜索标题/标签/内容"
                style={{ width: 280 }}
                onSearch={(v) => setKnowledgeFilters((p) => ({ ...p, q: v }))}
              />
              <Button onClick={createKnowledge} icon={<PlusOutlined />}>新建知识</Button>
              <ReadEditActions
                editing={knowledgeEditing}
                saving={knowledgeSaving}
                onEdit={startEditKnowledge}
                onSave={saveKnowledge}
                onCancel={cancelKnowledgeEdit}
                editDisabled={!selectedKnowledgeId}
              />
              <Popconfirm title="确认删除当前知识条目？" onConfirm={deleteKnowledge} disabled={!selectedKnowledgeId}>
                <Button danger icon={<DeleteOutlined />} disabled={!selectedKnowledgeId}>删除</Button>
              </Popconfirm>
            </Space>
          </Card>

          <Row gutter={12}>
            <Col xs={24} xl={8}>
              <Card title="知识条目" className="maintain-list-card" loading={knowledgeLoading}>
                <List
                  dataSource={knowledgeRows}
                  locale={{ emptyText: <Empty description="暂无知识条目" /> }}
                  renderItem={(item) => (
                    <List.Item
                      className={`maintain-list-item ${item.id === selectedKnowledgeId ? 'active' : ''}`}
                      onClick={() => selectKnowledge(item.id)}
                    >
                      <div className="maintain-list-main">
                        <div className="maintain-list-title">{item.title}</div>
                        <div className="maintain-list-meta">
                          <Tag color="blue">{mapLabel(KNOWLEDGE_CATEGORY_ZH, item.category)}</Tag>
                          <Tag>{mapLabel(KNOWLEDGE_STATUS_ZH, item.status)}</Tag>
                          <Tag color="gold">{mapLabel(KNOWLEDGE_PRIORITY_ZH, item.priority)}</Tag>
                        </div>
                        <Typography.Paragraph className="maintain-list-summary" ellipsis={{ rows: 2 }}>
                          {item.summary || item.next_action || tagsToSummary(item.tags || item.tags_text) || '无摘要'}
                        </Typography.Paragraph>
                      </div>
                    </List.Item>
                  )}
                />
              </Card>
            </Col>

            <Col xs={24} xl={16}>
              <Card title={selectedKnowledgeId ? `知识 #${selectedKnowledgeId}` : '新建知识条目'} className="maintain-editor-card">
                {knowledgeEditing ? (
                  <Form form={knowledgeForm} layout="vertical" initialValues={{ category: 'pattern_dictionary', status: 'active', priority: 'medium', tags: [], related_note_ids: [] }}>
                    <Row gutter={12}>
                      <Col span={10}><Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}><Input placeholder="例如：趋势启动回调判定" /></Form.Item></Col>
                      <Col span={7}><Form.Item name="category" label="分类"><Select options={knowledgeCategoryOptions} /></Form.Item></Col>
                      <Col span={7}><Form.Item name="status" label="状态"><Select options={KNOWLEDGE_STATUS_OPTIONS} /></Form.Item></Col>
                      <Col span={8}><Form.Item name="priority" label="优先级"><Select options={KNOWLEDGE_PRIORITY_OPTIONS} /></Form.Item></Col>
                      <Col span={8}><Form.Item name="related_symbol" label="关联品种"><Input placeholder="IF / AU" /></Form.Item></Col>
                      <Col span={8}><Form.Item name="related_pattern" label="关联结构"><Input placeholder="failed_breakout_reversal" /></Form.Item></Col>
                      <Col span={8}><Form.Item name="related_regime" label="关联环境"><Input placeholder="high-vol directional" /></Form.Item></Col>
                      <Col span={24}>
                        <Form.Item name="tags" label="标签">
                          <Select mode="tags" tokenSeparators={[',', '，']} options={knowledgeTagOptions} placeholder="输入标签并回车" />
                        </Form.Item>
                      </Col>
                      <Col span={24}>
                        <Form.Item name="related_note_ids" label="关联文档">
                          <Select
                            mode="multiple"
                            allowClear
                            showSearch
                            optionFilterProp="label"
                            options={knowledgeDocOptions}
                            onSearch={searchKnowledgeDocs}
                            placeholder="输入关键字搜索笔记文档并多选"
                            notFoundContent={knowledgeDocSearching ? '搜索中...' : '无匹配文档'}
                          />
                        </Form.Item>
                      </Col>
                      <Col span={24}><Form.Item name="summary" label="摘要"><TextArea rows={2} /></Form.Item></Col>
                      <Col span={24}><Form.Item name="content" label="正文"><TextArea rows={6} /></Form.Item></Col>
                      <Col span={12}><Form.Item name="next_action" label="下一步动作"><TextArea rows={2} /></Form.Item></Col>
                      <Col span={6}><Form.Item name="due_date" label="截止日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
                      <Col span={6}><Form.Item name="source_ref" label="来源引用"><Input placeholder="链接/来源" /></Form.Item></Col>
                    </Row>
                  </Form>
                ) : !selectedKnowledge ? (
                  <Empty description="请选择左侧知识条目或新建" />
                ) : (
                  <Space direction="vertical" size={12} style={{ width: '100%' }}>
                    <Descriptions size="small" column={2}>
                      <Descriptions.Item label="标题">{selectedKnowledge.title || '-'}</Descriptions.Item>
                      <Descriptions.Item label="分类">{mapLabel(KNOWLEDGE_CATEGORY_ZH, selectedKnowledge.category)}</Descriptions.Item>
                      <Descriptions.Item label="状态">{mapLabel(KNOWLEDGE_STATUS_ZH, selectedKnowledge.status)}</Descriptions.Item>
                      <Descriptions.Item label="优先级">{mapLabel(KNOWLEDGE_PRIORITY_ZH, selectedKnowledge.priority)}</Descriptions.Item>
                      <Descriptions.Item label="关联品种">{selectedKnowledgeSymbolLabel}</Descriptions.Item>
                      <Descriptions.Item label="关联结构">{selectedKnowledge.related_pattern || '-'}</Descriptions.Item>
                      <Descriptions.Item label="关联环境">{selectedKnowledge.related_regime || '-'}</Descriptions.Item>
                      <Descriptions.Item label="截止日期">{selectedKnowledge.due_date || '-'}</Descriptions.Item>
                    </Descriptions>
                    {selectedKnowledgeTags.length > 0 ? (
                      <div>
                        <Typography.Text type="secondary">标签</Typography.Text>
                        <div style={{ marginTop: 4 }}>{selectedKnowledgeTags.map((t) => <Tag key={t}>{t}</Tag>)}</div>
                      </div>
                    ) : null}
                    {(selectedKnowledge.related_notes || []).length > 0 ? (
                      <div>
                        <Typography.Text type="secondary">关联文档</Typography.Text>
                        <div style={{ marginTop: 4 }}>
                          <Space direction="vertical" size={2}>
                            {(selectedKnowledge.related_notes || []).map((note) => (
                              <a key={note.id} href={`/notes/?tab=doc&noteId=${note.id}`} target="_blank" rel="noreferrer">
                                {toDocOption(note, knowledgeNotebookMap).label} (#{note.id})
                              </a>
                            ))}
                          </Space>
                        </div>
                      </div>
                    ) : null}
                    {selectedKnowledge.summary ? (
                      <div>
                        <Typography.Text type="secondary">摘要</Typography.Text>
                        <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{selectedKnowledge.summary}</Typography.Paragraph>
                      </div>
                    ) : null}
                    {selectedKnowledge.content ? (
                      <div>
                        <Typography.Text type="secondary">正文</Typography.Text>
                        <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{selectedKnowledge.content}</Typography.Paragraph>
                      </div>
                    ) : null}
                    {selectedKnowledge.next_action ? (
                      <div>
                        <Typography.Text type="secondary">下一步动作</Typography.Text>
                        <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{selectedKnowledge.next_action}</Typography.Paragraph>
                      </div>
                    ) : null}
                    {selectedKnowledge.source_ref ? (
                      <div>
                        <Typography.Text type="secondary">来源引用</Typography.Text>
                        <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{selectedKnowledge.source_ref}</Typography.Paragraph>
                      </div>
                    ) : null}
                  </Space>
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}

      {moduleKey === 'broker' && (
        <Row gutter={12}>
          <Col xs={24} xl={8}>
            <Card
              title="券商来源"
              className="maintain-list-card"
              loading={brokerLoading}
              extra={<Button onClick={createBroker} icon={<PlusOutlined />}>新建</Button>}
            >
              <List
                dataSource={brokerRows}
                locale={{ emptyText: <Empty description="暂无券商" /> }}
                renderItem={(item) => (
                  <List.Item
                    className={`maintain-list-item ${item.id === selectedBrokerId ? 'active' : ''}`}
                    onClick={() => selectBroker(item.id)}
                  >
                    <div className="maintain-list-main">
                      <div className="maintain-list-title">{item.name}</div>
                      <Typography.Text type="secondary">{item.account || '无账号信息'}</Typography.Text>
                    </div>
                  </List.Item>
                )}
              />
            </Card>
          </Col>

          <Col xs={24} xl={16}>
            <Card
              title={selectedBrokerId ? `券商 #${selectedBrokerId}` : '新建券商'}
              className="maintain-editor-card"
              extra={(
                <Space>
                  <ReadEditActions
                    editing={brokerEditing}
                    saving={brokerSaving}
                    onEdit={startEditBroker}
                    onSave={saveBroker}
                    onCancel={cancelBrokerEdit}
                    editDisabled={!selectedBrokerId}
                  />
                  <Popconfirm title="确认删除当前券商？" onConfirm={deleteBroker} disabled={!selectedBrokerId}>
                    <Button danger icon={<DeleteOutlined />} disabled={!selectedBrokerId}>删除</Button>
                  </Popconfirm>
                </Space>
              )}
            >
              {brokerEditing ? (
                <Form form={brokerForm} layout="vertical">
                  <Row gutter={12}>
                    <Col span={12}><Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input placeholder="例如：宏源期货" /></Form.Item></Col>
                    <Col span={12}><Form.Item label="账号" name="account"><Input placeholder="账号/客户号" /></Form.Item></Col>
                    <Col span={12}><Form.Item label="密码" name="password"><Input.Password placeholder="可留空" /></Form.Item></Col>
                    <Col span={12}><Form.Item label="其他信息" name="extra_info"><TextArea rows={2} placeholder="通道/风控限制等" /></Form.Item></Col>
                    <Col span={24}><Form.Item label="备注" name="notes"><TextArea rows={3} /></Form.Item></Col>
                  </Row>
                </Form>
              ) : !selectedBroker ? (
                <Empty description="请选择左侧券商或新建" />
              ) : (
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="名称">{selectedBroker.name || '-'}</Descriptions.Item>
                  <Descriptions.Item label="账号">{selectedBroker.account || '-'}</Descriptions.Item>
                  <Descriptions.Item label="密码">{selectedBroker.password || '-'}</Descriptions.Item>
                  <Descriptions.Item label="其他信息">{selectedBroker.extra_info || '-'}</Descriptions.Item>
                  <Descriptions.Item label="备注">
                    <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                      {selectedBroker.notes || '-'}
                    </Typography.Paragraph>
                  </Descriptions.Item>
                </Descriptions>
              )}
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
