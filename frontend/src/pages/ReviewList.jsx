import { useEffect, useMemo, useRef, useState } from 'react';
import {
  FloatButton,
  Button,
  Col,
  Collapse,
  DatePicker,
  Drawer,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Popover,
  Popconfirm,
  Rate,
  Row,
  Select,
  Slider,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import InkSection from '../components/InkSection';
import {
  DeleteOutlined,
  FolderOpenOutlined,
  FolderOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  ReadOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useSearchParams } from 'react-router-dom';
import { reviewSessionApi, tradeApi } from '../api';
import { FUTURES_SYMBOL_OPTIONS } from '../utils/futures';
import {
  buildTradeSearchOption,
  formatInstrumentDisplay,
  formatReviewConclusionLabel,
  formatReviewRoleLabel,
  normalizeTagList,
} from '../features/trading/display';
import { REVIEW_SCOPE_ZH, dictToOptions, mapLabel } from '../features/trading/localization';
import ReadEditActions from '../features/trading/components/ReadEditActions';
import ResearchContentPanel from '../features/trading/components/ResearchContentPanel';
import './ReviewList.css';

const { TextArea } = Input;
const { RangePicker } = DatePicker;

const REVIEW_KIND_OPTIONS = [
  { value: 'period', label: '周期' },
  { value: 'theme', label: '主题' },
  { value: 'setup', label: '形态' },
  { value: 'symbol', label: '品种' },
  { value: 'regime', label: '环境' },
  { value: 'failure-pattern', label: '失败模式' },
  { value: 'source', label: '来源' },
  { value: 'plan-followup', label: '计划跟踪' },
  { value: 'custom', label: '自定义' },
];
const REVIEW_SCOPE_OPTIONS = dictToOptions(REVIEW_SCOPE_ZH);
const REVIEW_ROLE_OPTIONS = [
  { value: 'linked_trade', label: formatReviewRoleLabel('linked_trade') },
  { value: 'best_trade', label: formatReviewRoleLabel('best_trade') },
  { value: 'worst_trade', label: formatReviewRoleLabel('worst_trade') },
  { value: 'representative_trade', label: formatReviewRoleLabel('representative_trade') },
  { value: 'outlier_trade', label: formatReviewRoleLabel('outlier_trade') },
  { value: 'execution_mistake_example', label: formatReviewRoleLabel('execution_mistake_example') },
  { value: 'setup_example', label: formatReviewRoleLabel('setup_example') },
];
const TRADE_STATUS_OPTIONS = [
  { value: 'open', label: '持仓' },
  { value: 'closed', label: '已平' },
];
const REVIEW_READER_FONT_STORAGE_KEY = 'trading.review.reader_font_scale';
const REVIEW_READER_DEFAULT_SCALE = 100;
const REVIEW_READER_SCALE_MIN = 95;
const REVIEW_READER_SCALE_MAX = 135;
const REVIEW_READER_SCALE_STEP = 5;
const LEGACY_READER_LEVEL_TO_SCALE = { xs: 85, sm: 95, md: 100, lg: 110, xl: 120 };

function kindLabel(kind) {
  return REVIEW_KIND_OPTIONS.find((x) => x.value === kind)?.label || kind || '-';
}

function isValidReviewKind(kind) {
  return REVIEW_KIND_OPTIONS.some((x) => x.value === kind);
}

function selectionModeLabel(mode) {
  if (mode === 'manual') return '手动选择';
  if (mode === 'filter_snapshot') return '筛选快照';
  if (mode === 'saved_cohort') return '已保存样本集';
  if (mode === 'plan_linked') return '计划关联';
  if (mode === 'imported') return '导入';
  return mode || '-';
}

function loadReviewReaderFontScale() {
  if (typeof window === 'undefined') return REVIEW_READER_DEFAULT_SCALE;
  try {
    const raw = window.localStorage.getItem(REVIEW_READER_FONT_STORAGE_KEY);
    if (!raw) return REVIEW_READER_DEFAULT_SCALE;
    if (LEGACY_READER_LEVEL_TO_SCALE[raw]) return LEGACY_READER_LEVEL_TO_SCALE[raw];
    const num = Number(raw);
    if (!Number.isFinite(num)) return REVIEW_READER_DEFAULT_SCALE;
    const clamped = Math.min(REVIEW_READER_SCALE_MAX, Math.max(REVIEW_READER_SCALE_MIN, num));
    return Math.round(clamped / REVIEW_READER_SCALE_STEP) * REVIEW_READER_SCALE_STEP;
  } catch {
    // ignore
  }
  return REVIEW_READER_DEFAULT_SCALE;
}

function formatDateTime(value) {
  if (!value) return '-';
  const d = dayjs(value);
  if (!d.isValid()) return '-';
  return d.format('YYYY-MM-DD HH:mm');
}

function normalizePayload(values) {
  return {
    title: values.title?.trim() || null,
    review_kind: values.review_kind || 'custom',
    review_scope: values.review_scope || 'custom',
    selection_mode: values.selection_mode || 'manual',
    selection_basis: values.selection_basis?.trim() || null,
    review_goal: values.review_goal?.trim() || null,
    market_regime: values.market_regime?.trim() || null,
    summary: values.summary?.trim() || null,
    repeated_errors: values.repeated_errors?.trim() || null,
    next_focus: values.next_focus?.trim() || null,
    action_items: values.action_items?.trim() || null,
    content: values.content?.trim() || null,
    research_notes: values.research_notes || null,
    tags: normalizeTagList(values.tags),
    is_favorite: !!values.is_favorite,
    star_rating: values.star_rating || null,
  };
}

function summaryToOption(summary) {
  if (!summary?.trade_id) return null;
  return buildTradeSearchOption({
    trade_id: summary.trade_id,
    trade_date: summary.trade_date,
    symbol: summary.symbol,
    contract: summary.contract,
    direction: summary.direction,
    quantity: summary.quantity,
    open_price: summary.open_price,
    close_price: summary.close_price,
    status: summary.status,
    pnl: summary.pnl,
    source_display: summary.source_display,
    has_trade_review: summary.has_trade_review,
    review_conclusion: summary.review_conclusion,
  });
}

function LinkedTradeCard({ item }) {
  const s = item?.trade_summary || {};
  return (
    <div className="review-linked-card">
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        <Space wrap>
          <Tag color="blue">{formatReviewRoleLabel(item.role)}</Tag>
          {s.direction ? <Tag>{s.direction}</Tag> : null}
          {s.status ? <Tag>{s.status === 'closed' ? '已平' : '持仓'}</Tag> : null}
          {s.review_conclusion ? <Tag color="purple">{formatReviewConclusionLabel(s.review_conclusion)}</Tag> : null}
        </Space>
        <Typography.Text strong>{s.trade_date || '-'} / {formatInstrumentDisplay(s.symbol, s.contract)}</Typography.Text>
        <Typography.Text type="secondary">合约 {s.contract || '-'} / 手数 {s.quantity ?? '-'} / 价格 {s.open_price ?? '-'} {'->'} {s.close_price ?? '-'}</Typography.Text>
        <Typography.Text type="secondary">PnL {s.pnl ?? '-'} / 来源 {s.source_display || '-'}</Typography.Text>
        {(item.note || item.notes) ? <Typography.Text type="secondary">备注: {item.note || item.notes}</Typography.Text> : null}
      </Space>
    </div>
  );
}

export default function ReviewList() {
  const [searchParams] = useSearchParams();
  const initialKindFromQuery = searchParams.get('kind');
  const initialSessionIdFromQuery = Number(searchParams.get('sessionId') || 0) || null;
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [activeKind, setActiveKind] = useState(isValidReviewKind(initialKindFromQuery) ? initialKindFromQuery : 'period');
  const [activeScope, setActiveScope] = useState(undefined);
  const [activeTag, setActiveTag] = useState(undefined);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [minStars, setMinStars] = useState(undefined);
  const [selectedId, setSelectedId] = useState(initialSessionIdFromQuery);
  const [expandedScope, setExpandedScope] = useState(null);
  const [reviewSidebarCollapsed, setReviewSidebarCollapsed] = useState(false);
  const [linkedTrades, setLinkedTrades] = useState([]);
  const [tradeOptions, setTradeOptions] = useState([]);
  const [tradeOptionLoading, setTradeOptionLoading] = useState(false);
  const [quickTradeId, setQuickTradeId] = useState(undefined);
  const [quickRole, setQuickRole] = useState('linked_trade');
  const [tradeSearch, setTradeSearch] = useState({ q: '', symbol: undefined, status: undefined, dateRange: null });
  const [reviewDetailDrawerOpen, setReviewDetailDrawerOpen] = useState(false);
  const [reviewFontPopoverOpen, setReviewFontPopoverOpen] = useState(false);
  const [reviewReaderFontScale, setReviewReaderFontScale] = useState(loadReviewReaderFontScale);
  const [form] = Form.useForm();
  const tradeSearchTimerRef = useRef(null);
  const tradeSearchReqRef = useRef(0);

  const selected = useMemo(() => rows.find((x) => x.id === selectedId) || null, [rows, selectedId]);
  const reviewTagOptions = useMemo(() => {
    const set = new Set();
    rows.forEach((r) => normalizeTagList(r.tags).forEach((t) => set.add(t)));
    return Array.from(set).map((x) => ({ value: x, label: x }));
  }, [rows]);

  const groupedRows = useMemo(() => {
    const priorityRank = { high: 0, medium: 1, low: 2 };
    const normalizedScope = (item) => (item?.review_scope || '').trim() || 'custom';
    const maintenanceTs = (item) => {
      const updated = item?.updated_at ? new Date(item.updated_at).getTime() : NaN;
      if (Number.isFinite(updated)) return updated;
      const created = item?.created_at ? new Date(item.created_at).getTime() : NaN;
      if (Number.isFinite(created)) return created;
      return Number.MAX_SAFE_INTEGER;
    };
    const priorityWeight = (item) => {
      const p = String(item?.priority || '').trim().toLowerCase();
      if (priorityRank[p] !== undefined) return priorityRank[p];
      const stars = Number(item?.star_rating || 0);
      if (Number.isFinite(stars) && stars > 0) return 10 - stars;
      return 99;
    };
    const compareSession = (a, b) => {
      const pa = priorityWeight(a);
      const pb = priorityWeight(b);
      if (pa !== pb) return pa - pb;
      const ta = maintenanceTs(a);
      const tb = maintenanceTs(b);
      if (ta !== tb) return ta - tb;
      return (Number(a?.id) || 0) - (Number(b?.id) || 0);
    };

    const groups = new Map();
    for (const item of rows) {
      const scope = normalizedScope(item);
      if (!groups.has(scope)) groups.set(scope, []);
      groups.get(scope).push(item);
    }
    return Array.from(groups.entries())
      .map(([scope, items]) => ({
        scope,
        label: mapLabel(REVIEW_SCOPE_ZH, scope || 'custom'),
        items: [...items].sort(compareSession),
      }))
      .sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'));
  }, [rows]);

  const linkedTradeIds = useMemo(() => {
    const set = new Set();
    linkedTrades.forEach((x) => {
      const id = Number(x.trade_id);
      if (id > 0) set.add(id);
    });
    if (quickTradeId) set.add(Number(quickTradeId));
    return Array.from(set);
  }, [linkedTrades, quickTradeId]);

  const tradeOptionsMerged = useMemo(() => {
    const map = {};
    tradeOptions.forEach((item) => {
      map[item.value] = item;
    });
    linkedTrades.forEach((item) => {
      const option = summaryToOption(item.trade_summary);
      if (option && !map[option.value]) map[option.value] = option;
    });
    return Object.values(map);
  }, [tradeOptions, linkedTrades]);

  const tradeOptionMap = useMemo(() => {
    const out = {};
    tradeOptionsMerged.forEach((item) => {
      out[item.value] = item;
    });
    return out;
  }, [tradeOptionsMerged]);

  const reviewReaderStyle = useMemo(() => {
    const scale = Number.isFinite(Number(reviewReaderFontScale))
      ? Number(reviewReaderFontScale)
      : REVIEW_READER_DEFAULT_SCALE;
    const ratio = scale / 100;
    const fontSize = `${(14 * ratio).toFixed(2)}px`;
    const lineHeight = (1.94 + (ratio - 1) * 0.4).toFixed(2);
    const paragraphSpacing = `${(0.78 + (ratio - 1) * 0.36).toFixed(2)}em`;
    return {
      '--reader-font-size': fontSize,
      '--reader-line-height': lineHeight,
      '--reader-paragraph-spacing': paragraphSpacing,
    };
  }, [reviewReaderFontScale]);

  const resetForm = (item) => {
    if (!item) {
      form.resetFields();
      form.setFieldsValue({
        review_kind: activeKind,
        review_scope: activeScope || 'custom',
        selection_mode: 'manual',
        tags: [],
        is_favorite: false,
      });
      setLinkedTrades([]);
      return;
    }
    form.setFieldsValue({
      ...item,
      tags: normalizeTagList(item.tags),
      review_kind: item.review_kind || activeKind,
      review_scope: item.review_scope || 'custom',
    });
    setLinkedTrades((item.trade_links || []).map((x) => ({
      trade_id: x.trade_id,
      role: x.role || 'linked_trade',
      note: x.note || x.notes || '',
      trade_summary: x.trade_summary || null,
    })));
  };

  const loadRows = async (nextSelectedId = null) => {
    setLoading(true);
    try {
      const params = { review_kind: activeKind, size: 200 };
      if (activeScope) params.review_scope = activeScope;
      if (activeTag) params.tag = activeTag;
      if (favoriteOnly) params.is_favorite = true;
      if (minStars) params.min_star_rating = minStars;
      const res = await reviewSessionApi.list(params);
      const list = res.data || [];
      const targetId = nextSelectedId ?? selectedId;
      if (targetId && !list.some((x) => x.id === targetId)) {
        try {
          const focused = (await reviewSessionApi.get(targetId)).data;
          const merged = [focused, ...list.filter((x) => x.id !== focused.id)];
          setRows(merged);
          setSelectedId(focused.id);
          resetForm(focused);
          return;
        } catch {
          // fallback to filtered list
        }
      }
      setRows(list);
      if (!list.length) {
        setSelectedId(null);
        resetForm(null);
        return;
      }
      if (targetId && list.some((x) => x.id === targetId)) {
        setSelectedId(targetId);
        resetForm(list.find((x) => x.id === targetId));
        return;
      }
      setSelectedId(list[0].id);
      resetForm(list[0]);
    } catch {
      message.error('复盘会话加载失败');
    } finally {
      setLoading(false);
    }
  };

  const searchTradeOptions = async ({ query, includeTradeIds = [], silent = false, searchState } = {}) => {
    const reqId = tradeSearchReqRef.current + 1;
    tradeSearchReqRef.current = reqId;
    if (!silent) setTradeOptionLoading(true);
    try {
      const activeSearch = searchState || tradeSearch;
      const includeIds = Array.from(new Set([...linkedTradeIds, ...(includeTradeIds || [])]))
        .filter((x) => Number(x) > 0)
        .map((x) => Number(x));
      const params = { limit: 50 };
      const keyword = String(query ?? activeSearch.q ?? '').trim();
      if (keyword) params.q = keyword;
      if (activeSearch.symbol) params.symbol = activeSearch.symbol;
      if (activeSearch.status) params.status = activeSearch.status;
      if (activeSearch.dateRange?.[0] && activeSearch.dateRange?.[1]) {
        params.date_from = activeSearch.dateRange[0].format('YYYY-MM-DD');
        params.date_to = activeSearch.dateRange[1].format('YYYY-MM-DD');
      }
      if (includeIds.length > 0) params.include_ids = includeIds.join(',');
      const res = await tradeApi.searchOptions(params);
      if (reqId !== tradeSearchReqRef.current) return;
      setTradeOptions((res.data?.items || []).map(buildTradeSearchOption));
    } catch {
      if (reqId !== tradeSearchReqRef.current) return;
      if (!silent) message.error('交易搜索失败');
    } finally {
      if (reqId === tradeSearchReqRef.current && !silent) setTradeOptionLoading(false);
    }
  };

  const scheduleSearchTradeOptions = (query) => {
    if (tradeSearchTimerRef.current) clearTimeout(tradeSearchTimerRef.current);
    tradeSearchTimerRef.current = setTimeout(() => {
      searchTradeOptions({ query });
    }, 300);
  };

  useEffect(() => {
    loadRows();
  }, [activeKind, activeScope, activeTag, favoriteOnly, minStars]);

  useEffect(() => {
    const kindFromQuery = searchParams.get('kind');
    const sessionIdFromQuery = Number(searchParams.get('sessionId') || 0) || null;
    if (isValidReviewKind(kindFromQuery) && kindFromQuery !== activeKind) {
      setActiveKind(kindFromQuery);
      return;
    }
    if (sessionIdFromQuery && sessionIdFromQuery !== selectedId) {
      setSelectedId(sessionIdFromQuery);
      loadRows(sessionIdFromQuery);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!rows.length) {
      setExpandedScope(null);
      return;
    }
    if (expandedScope && !rows.some((x) => ((x.review_scope || '').trim() || 'custom') === expandedScope)) {
      setExpandedScope(null);
    }
  }, [rows, expandedScope]);

  useEffect(() => {
    setReviewDetailDrawerOpen(false);
    setReviewFontPopoverOpen(false);
  }, [selectedId]);

  useEffect(() => () => {
    if (tradeSearchTimerRef.current) clearTimeout(tradeSearchTimerRef.current);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(REVIEW_READER_FONT_STORAGE_KEY, String(reviewReaderFontScale));
  }, [reviewReaderFontScale]);

  useEffect(() => {
    if (!editing) return;
    searchTradeOptions({ query: tradeSearch.q, includeTradeIds: linkedTradeIds, silent: true });
  }, [editing, linkedTradeIds.join(',')]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = normalizePayload(values);
      if (!payload.selection_basis || !payload.review_goal) {
        message.warning('分组依据和复盘目标为必填');
        return;
      }
      let saved;
      if (selectedId) {
        saved = (await reviewSessionApi.update(selectedId, payload)).data;
      } else {
        saved = (await reviewSessionApi.create(payload)).data;
      }
      await reviewSessionApi.upsertTradeLinks(saved.id, {
        trade_links: linkedTrades
          .filter((x) => x.trade_id)
          .map((x, idx) => ({
            trade_id: Number(x.trade_id),
            role: x.role || 'linked_trade',
            note: (x.note || '').trim() || null,
            sort_order: idx,
          })),
      });
      message.success(selectedId ? '复盘会话已更新' : '复盘会话已创建');
      setEditing(false);
      await loadRows(saved.id);
      setSelectedId(saved.id);
    } catch (e) {
      if (!e?.errorFields) message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) return;
    try {
      await reviewSessionApi.delete(selectedId);
      message.success('复盘会话已移入回收站');
      setEditing(false);
      await loadRows();
    } catch {
      message.error('移入回收站失败');
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
        next.push({ trade_id: Number(quickTradeId), role: quickRole || 'linked_trade', note: '', trade_summary: tradeSummary });
      }
      return next;
    });
    setQuickTradeId(undefined);
  };

  const updateLinkedTrade = (index, patch) => {
    setLinkedTrades((prev) => prev.map((x, i) => {
      if (i !== index) return x;
      const next = { ...x, ...patch };
      if (patch.trade_id) next.trade_summary = tradeOptionMap[Number(patch.trade_id)]?.summary || x.trade_summary || null;
      return next;
    }));
  };

  const removeLinkedTrade = (index) => setLinkedTrades((prev) => prev.filter((_, i) => i !== index));

  const selectSession = (item) => {
    const scope = (item?.review_scope || '').trim() || 'custom';
    setExpandedScope(scope);
    setSelectedId(item.id);
    resetForm(item);
    setEditing(false);
    setReviewDetailDrawerOpen(false);
    setReviewFontPopoverOpen(false);
  };
  const selectedReviewTags = normalizeTagList(selected?.tags || selected?.tags_text);
  const resolveScrollTarget = () => document.querySelector('.app-content') || window;

  return (
    <div className="review-workspace">
      <div className="review-header-card review-toolbar">
        <div className="review-header-main">
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>复盘研究工作台</Typography.Title>
            <Typography.Text type="secondary">ReviewSession 是分组复盘唯一主对象</Typography.Text>
          </div>
          <Space wrap>
            <Button
              icon={reviewSidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setReviewSidebarCollapsed((prev) => !prev)}
            >
              {reviewSidebarCollapsed ? '展开目录' : '收起目录'}
            </Button>
          </Space>
        </div>
      </div>

      <div className="review-toolbar-strip">
        <div className="review-tool-group review-tool-group-filters">
          <div className="review-tool-label">筛选</div>
          <div className="review-tool-fields">
            <Select value={activeKind} options={REVIEW_KIND_OPTIONS} onChange={setActiveKind} style={{ width: 130 }} />
            <Select allowClear value={activeScope} options={REVIEW_SCOPE_OPTIONS} placeholder="范围" onChange={setActiveScope} style={{ width: 130 }} />
            <Select allowClear value={activeTag} options={reviewTagOptions} placeholder="标签" onChange={setActiveTag} style={{ width: 140 }} />
            <Select value={favoriteOnly ? 'fav' : 'all'} style={{ width: 110 }} onChange={(v) => setFavoriteOnly(v === 'fav')} options={[{ label: '全部', value: 'all' }, { label: '仅收藏', value: 'fav' }]} />
            <Select allowClear value={minStars} placeholder="最低星级" style={{ width: 120 }} onChange={setMinStars} options={[1, 2, 3, 4, 5].map((x) => ({ value: x, label: `${x} 星` }))} />
          </div>
        </div>
        <div className="review-tool-group review-tool-group-actions">
          <div className="review-tool-label">会话操作</div>
          <Space wrap>
            <Button type="primary" onClick={() => { setSelectedId(null); resetForm(null); setEditing(true); setReviewDetailDrawerOpen(false); setReviewFontPopoverOpen(false); }} icon={<PlusOutlined />}>新建会话</Button>
            <ReadEditActions editing={editing} saving={saving} onEdit={() => { if (selected) { resetForm(selected); setEditing(true); setReviewDetailDrawerOpen(false); setReviewFontPopoverOpen(false); } }} onSave={handleSave} onCancel={() => { resetForm(selected); setEditing(false); setReviewDetailDrawerOpen(false); setReviewFontPopoverOpen(false); }} editDisabled={!selectedId} />
            <Popconfirm title="确认移入回收站？" onConfirm={handleDelete} disabled={!selectedId}><Button danger icon={<DeleteOutlined />} disabled={!selectedId}>删除</Button></Popconfirm>
          </Space>
        </div>
      </div>

      <Row gutter={12}>
        {!reviewSidebarCollapsed ? (
          <Col xs={24} xl={6}>
            <InkSection className="review-list-card" loading={loading}>
              {groupedRows.length === 0 ? (
                <Empty description="暂无会话" />
              ) : (
                <Collapse
                  accordion
                  bordered={false}
                  className="review-folder-collapse"
                  activeKey={expandedScope || undefined}
                  onChange={(key) => {
                    const nextKey = Array.isArray(key) ? key[0] : key;
                    setExpandedScope(nextKey ? String(nextKey) : null);
                  }}
                  items={groupedRows.map((group) => ({
                    key: group.scope,
                    label: (
                      <div className="review-folder-label">
                        <span className="review-folder-name">
                          <span className="review-folder-icon">
                            {expandedScope === group.scope ? <FolderOpenOutlined /> : <FolderOutlined />}
                          </span>
                          {group.label}
                        </span>
                        <span className="review-folder-count">{group.items.length}</span>
                      </div>
                    ),
                    children: (
                      <List
                        dataSource={group.items}
                        locale={{ emptyText: <Empty description="该分类下暂无会话" /> }}
                        renderItem={(item) => {
                          const itemTags = normalizeTagList(item.tags);
                          return (
                            <List.Item className={`review-list-item review-list-child-item ${item.id === selectedId ? 'active' : ''}`} onClick={() => selectSession(item)}>
                              <div className="review-list-main">
                                <div className="review-list-head">
                                  <div className="review-list-title" title={item.title || `Session #${item.id}`}>{item.title || `Session #${item.id}`}</div>
                                  <div className="review-list-meta">
                                    <Tag className="review-mini-tag">{kindLabel(item.review_kind)}</Tag>
                                    <Tag className="review-mini-tag" color="gold">★{item.star_rating || 0}</Tag>
                                  </div>
                                </div>
                                {itemTags.length > 0 ? (
                                  <div className="review-list-tags">
                                    {itemTags.map((tag) => <Tag key={`${item.id}-${tag}`}>{tag}</Tag>)}
                                  </div>
                                ) : null}
                              </div>
                            </List.Item>
                          );
                        }}
                      />
                    ),
                  }))}
                />
              )}
            </InkSection>
          </Col>
        ) : null}

        <Col xs={24} xl={reviewSidebarCollapsed ? 24 : 18}>
          <InkSection className="review-editor-card">
            {editing ? (
              <>
                <Form form={form} layout="vertical" initialValues={{ review_kind: activeKind, review_scope: 'custom', selection_mode: 'manual', tags: [], is_favorite: false }}>
                  <Row gutter={12}>
                    <Col span={24}>
                      <div className="review-group-header">
                        <span className="review-group-name"><ReadOutlined />研究内容</span>
                      </div>
                    </Col>
                    <Col span={24}><Form.Item name="summary" label="结论摘要"><TextArea rows={2} /></Form.Item></Col>
                    <Col span={24}><Form.Item name="action_items" label="后续动作"><TextArea rows={2} /></Form.Item></Col>
                    <Col span={24}><Form.Item name="content" label="详细文本"><TextArea rows={4} /></Form.Item></Col>
                    <Form.Item name="research_notes" hidden><Input /></Form.Item>
                    <Col span={24}>
                      <Form.Item shouldUpdate noStyle>
                        {() => (
                          <ResearchContentPanel
                            editing
                            title="研究内容"
                            value={form.getFieldValue('research_notes')}
                            onChange={(next) => form.setFieldValue('research_notes', next)}
                          />
                        )}
                      </Form.Item>
                    </Col>
                    <Col span={24}>
                      <div className="review-group-header">
                        <span className="review-group-name"><ShareAltOutlined />会话属性与关联</span>
                      </div>
                    </Col>
                    <Col span={10}><Form.Item name="title" label="标题"><Input /></Form.Item></Col>
                    <Col span={5}><Form.Item name="review_kind" label="类型" rules={[{ required: true }]}><Select options={REVIEW_KIND_OPTIONS} /></Form.Item></Col>
                    <Col span={5}><Form.Item name="review_scope" label="范围"><Select options={REVIEW_SCOPE_OPTIONS} /></Form.Item></Col>
                    <Col span={4}><Form.Item name="selection_mode" label="选择方式"><Select options={[{ value: 'manual', label: '手动选择' }, { value: 'filter_snapshot', label: '筛选快照' }, { value: 'plan_linked', label: '计划关联' }]} /></Form.Item></Col>
                    <Col span={12}><Form.Item name="selection_basis" label="分组依据" rules={[{ required: true }]}><Input /></Form.Item></Col>
                    <Col span={12}><Form.Item name="review_goal" label="复盘目标" rules={[{ required: true }]}><Input /></Form.Item></Col>
                    <Col span={8}><Form.Item name="market_regime" label="市场环境"><Input /></Form.Item></Col>
                    <Col span={8}><Form.Item name="tags" label="标签"><Select mode="tags" tokenSeparators={[',', '，']} options={reviewTagOptions} /></Form.Item></Col>
                    <Col span={4}><Form.Item name="is_favorite" label="收藏" valuePropName="checked"><Switch /></Form.Item></Col>
                    <Col span={4}><Form.Item name="star_rating" label="星级"><Rate /></Form.Item></Col>
                    <Col span={12}><Form.Item name="repeated_errors" label="重复错误"><TextArea rows={2} /></Form.Item></Col>
                    <Col span={12}><Form.Item name="next_focus" label="下一步聚焦"><TextArea rows={2} /></Form.Item></Col>
                  </Row>
                </Form>

                <InkSection size="small" title="关联交易（搜索 + 样本）" className="review-link-card">
                  <div className="review-link-search-grid">
                    <Input allowClear value={tradeSearch.q} onChange={(e) => { const v = e.target.value; setTradeSearch((prev) => ({ ...prev, q: v })); scheduleSearchTradeOptions(v); }} placeholder="搜索: ID/合约/品种/来源" />
                    <Select allowClear showSearch optionFilterProp="label" options={FUTURES_SYMBOL_OPTIONS} value={tradeSearch.symbol} placeholder="品种" onChange={(v) => { const next = { ...tradeSearch, symbol: v }; setTradeSearch(next); searchTradeOptions({ query: next.q, searchState: next }); }} />
                    <Select allowClear options={TRADE_STATUS_OPTIONS} value={tradeSearch.status} placeholder="状态" onChange={(v) => { const next = { ...tradeSearch, status: v }; setTradeSearch(next); searchTradeOptions({ query: next.q, searchState: next }); }} />
                    <RangePicker value={tradeSearch.dateRange} onChange={(dates) => { const next = { ...tradeSearch, dateRange: dates }; setTradeSearch(next); searchTradeOptions({ query: next.q, searchState: next }); }} />
                  </div>

                  <Space wrap style={{ marginTop: 10, marginBottom: 10, width: '100%' }}>
                    <Select showSearch filterOption={false} value={quickTradeId} onChange={setQuickTradeId} onSearch={scheduleSearchTradeOptions} onFocus={() => searchTradeOptions({ query: tradeSearch.q, includeTradeIds: linkedTradeIds })} options={tradeOptionsMerged} style={{ width: 520, maxWidth: '100%' }} optionFilterProp="label" loading={tradeOptionLoading} />
                    <Select value={quickRole} onChange={setQuickRole} options={REVIEW_ROLE_OPTIONS} style={{ width: 180 }} />
                    <Button onClick={addLinkedTrade}>添加关联</Button>
                  </Space>

                  {!linkedTrades.length ? (
                    <Empty description="尚未关联交易" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <List
                      dataSource={linkedTrades}
                      renderItem={(item, index) => (
                        <List.Item actions={[<Button key="delete" type="link" danger onClick={() => removeLinkedTrade(index)}>移除</Button>]}>
                          <div className="review-link-row">
                            <Select size="small" showSearch filterOption={false} optionFilterProp="label" value={item.trade_id} onSearch={scheduleSearchTradeOptions} onFocus={() => searchTradeOptions({ query: tradeSearch.q, includeTradeIds: linkedTradeIds })} onChange={(v) => updateLinkedTrade(index, { trade_id: v })} options={tradeOptionsMerged} style={{ width: 420 }} loading={tradeOptionLoading} />
                            <Select size="small" value={item.role || 'linked_trade'} options={REVIEW_ROLE_OPTIONS} onChange={(v) => updateLinkedTrade(index, { role: v })} style={{ width: 180 }} />
                            <Input size="small" placeholder="样本备注" value={item.note || ''} onChange={(e) => updateLinkedTrade(index, { note: e.target.value })} />
                          </div>
                        </List.Item>
                      )}
                    />
                  )}
                </InkSection>
              </>
            ) : !selected ? (
              <Empty description="请选择左侧会话或新建" />
            ) : (
              <div className="review-detail-layout">
                <div className="review-reading-toolbar">
                  <Typography.Text type="secondary" className="review-reading-title">
                    {selected.title || `Session #${selected.id}`}
                  </Typography.Text>
                  <Space size={6} className="review-reading-actions">
                    <Popover
                      trigger="click"
                      placement="bottomRight"
                      open={reviewFontPopoverOpen}
                      onOpenChange={setReviewFontPopoverOpen}
                      overlayClassName="review-font-popover"
                      content={(
                        <div className="review-font-panel">
                          <div className="review-font-panel-head">
                            <Typography.Text className="review-font-panel-title">阅读字号</Typography.Text>
                            <Typography.Text type="secondary">{reviewReaderFontScale}%</Typography.Text>
                          </div>
                          <Slider
                            min={REVIEW_READER_SCALE_MIN}
                            max={REVIEW_READER_SCALE_MAX}
                            step={REVIEW_READER_SCALE_STEP}
                            value={reviewReaderFontScale}
                            onChange={setReviewReaderFontScale}
                            tooltip={{ formatter: (value) => `${value}%` }}
                          />
                          <div className="review-font-panel-foot">
                            <Typography.Text type="secondary">95%</Typography.Text>
                            <Button
                              type="text"
                              size="small"
                              onClick={() => setReviewReaderFontScale(REVIEW_READER_DEFAULT_SCALE)}
                            >
                              恢复默认
                            </Button>
                            <Typography.Text type="secondary">135%</Typography.Text>
                          </div>
                        </div>
                      )}
                    >
                      <Button size="small" className="review-font-trigger">Aa</Button>
                    </Popover>
                    <Button size="small" onClick={() => setReviewDetailDrawerOpen(true)}>
                      详情
                    </Button>
                  </Space>
                </div>

                <div className="review-article-paper review-article-reading" style={reviewReaderStyle}>
                  {selected.summary ? (
                    <Typography.Paragraph className="review-reader-lead">{selected.summary}</Typography.Paragraph>
                  ) : null}
                  <ResearchContentPanel showStandardFields={false} value={selected.research_notes || selected.content} />
                </div>

                <Drawer
                  title="复盘详情"
                  placement="right"
                  width={460}
                  onClose={() => setReviewDetailDrawerOpen(false)}
                  open={reviewDetailDrawerOpen}
                  className="review-detail-drawer"
                >
                  <div className="review-drawer-group">
                    <Typography.Text className="review-drawer-group-title">基本信息</Typography.Text>
                    <div className="review-drawer-block">
                      <Typography.Text className="review-drawer-main-title">{selected.title || `Session #${selected.id}`}</Typography.Text>
                      <Space size={6} wrap>
                        <Tag>{kindLabel(selected.review_kind)}</Tag>
                        <Tag>{mapLabel(REVIEW_SCOPE_ZH, selected.review_scope || 'custom')}</Tag>
                        <Tag color="gold">★{selected.star_rating || 0}</Tag>
                        {selected.is_favorite ? <Tag color="green">收藏</Tag> : null}
                      </Space>
                      <Descriptions size="small" column={1}>
                        <Descriptions.Item label="选择方式">{selectionModeLabel(selected.selection_mode)}</Descriptions.Item>
                        <Descriptions.Item label="分组依据">{selected.selection_basis || '-'}</Descriptions.Item>
                        <Descriptions.Item label="复盘目标">{selected.review_goal || '-'}</Descriptions.Item>
                        <Descriptions.Item label="更新时间">{formatDateTime(selected.updated_at || selected.created_at)}</Descriptions.Item>
                      </Descriptions>
                    </div>
                  </div>

                  <div className="review-drawer-group">
                    <Typography.Text className="review-drawer-group-title">会话属性</Typography.Text>
                    <div className="review-drawer-block">
                      <Descriptions size="small" column={1}>
                        <Descriptions.Item label="市场环境">{selected.market_regime || '-'}</Descriptions.Item>
                        <Descriptions.Item label="重复错误">{selected.repeated_errors || '-'}</Descriptions.Item>
                        <Descriptions.Item label="下一步聚焦">{selected.next_focus || '-'}</Descriptions.Item>
                      </Descriptions>
                      <dl className="review-meta-list">
                        <dt><Typography.Text type="secondary">标签</Typography.Text></dt>
                        <dd className="review-detail-tags">
                          {selectedReviewTags.length > 0
                            ? selectedReviewTags.map((tag) => <Tag key={tag}>{tag}</Tag>)
                            : <Typography.Text type="secondary">-</Typography.Text>}
                        </dd>
                      </dl>
                    </div>
                  </div>

                  {(selected.action_items || (selected.content && selected.research_notes)) ? (
                    <div className="review-drawer-group">
                      <Typography.Text className="review-drawer-group-title">后续与记录</Typography.Text>
                      <div className="review-drawer-block">
                        {selected.action_items ? (
                          <dl className="review-meta-list">
                            <dt><Typography.Text type="secondary">后续动作</Typography.Text></dt>
                            <dd>
                              <Typography.Paragraph className="review-drawer-text">
                                {selected.action_items}
                              </Typography.Paragraph>
                            </dd>
                          </dl>
                        ) : null}
                        {selected.content && selected.research_notes ? (
                          <dl className="review-meta-list">
                            <dt><Typography.Text type="secondary">详细记录</Typography.Text></dt>
                            <dd>
                              <Typography.Paragraph className="review-drawer-text">
                                {selected.content}
                              </Typography.Paragraph>
                            </dd>
                          </dl>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  <div className="review-drawer-group">
                    <Typography.Text className="review-drawer-group-title">关联交易</Typography.Text>
                    {(selected.trade_links || []).length === 0 ? (
                      <Empty description="暂无关联交易" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ) : (
                      <div className="review-linked-grid review-linked-grid-drawer">
                        {(selected.trade_links || []).map((item) => <LinkedTradeCard key={`${item.id}-${item.trade_id}`} item={item} />)}
                      </div>
                    )}
                  </div>
                </Drawer>
              </div>
            )}
          </InkSection>
        </Col>
      </Row>
      <div className="review-scroll-spacer" aria-hidden />
      <FloatButton.BackTop
        target={resolveScrollTarget}
        visibilityHeight={480}
      />
    </div>
  );
}
