import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  FloatButton,
  AutoComplete,
  Button,
  Col,
  Drawer,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Popover,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import InkSection from '../components/InkSection';
import {
  DeleteOutlined,
  DownOutlined,
  FolderOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  ReadOutlined,
  RightOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { brokerApi, knowledgeApi, noteApi, notebookApi } from '../api';
import {
  KNOWLEDGE_CATEGORY_ZH,
  KNOWLEDGE_PRIORITY_ZH,
  KNOWLEDGE_STATUS_ZH,
  dictToOptions,
  mapLabel,
} from '../features/trading/localization';
import { normalizeTagList } from '../features/trading/display';
import ReadEditActions from '../features/trading/components/ReadEditActions';
import ResearchContentPanel from '../features/trading/components/ResearchContentPanel';
import './BrokerManage.css';

const { TextArea, Search } = Input;

const KNOWLEDGE_STATUS_OPTIONS = dictToOptions(KNOWLEDGE_STATUS_ZH);
const KNOWLEDGE_PRIORITY_OPTIONS = dictToOptions(KNOWLEDGE_PRIORITY_ZH);
const KNOWLEDGE_READER_FONT_STORAGE_KEY = 'trading.maintain.knowledge_reader_font_level';
const KNOWLEDGE_READER_DEFAULT_SCALE = 100;
const KNOWLEDGE_READER_SCALE_MIN = 95;
const KNOWLEDGE_READER_SCALE_MAX = 135;
const KNOWLEDGE_READER_SCALE_STEP = 5;
const LEGACY_READER_LEVEL_TO_SCALE = { xs: 85, sm: 95, md: 100, lg: 110, xl: 120 };

function loadKnowledgeReaderFontLevel() {
  if (typeof window === 'undefined') return KNOWLEDGE_READER_DEFAULT_SCALE;
  try {
    const raw = window.localStorage.getItem(KNOWLEDGE_READER_FONT_STORAGE_KEY);
    if (!raw) return KNOWLEDGE_READER_DEFAULT_SCALE;
    if (LEGACY_READER_LEVEL_TO_SCALE[raw]) return LEGACY_READER_LEVEL_TO_SCALE[raw];
    const num = Number(raw);
    if (!Number.isFinite(num)) return KNOWLEDGE_READER_DEFAULT_SCALE;
    const clamped = Math.min(KNOWLEDGE_READER_SCALE_MAX, Math.max(KNOWLEDGE_READER_SCALE_MIN, num));
    const normalized = Math.round(clamped / KNOWLEDGE_READER_SCALE_STEP) * KNOWLEDGE_READER_SCALE_STEP;
    return normalized;
  } catch {
    // ignore
  }
  return KNOWLEDGE_READER_DEFAULT_SCALE;
}

function normalizeSubCategory(value) {
  if (Array.isArray(value)) {
    for (let i = value.length - 1; i >= 0; i -= 1) {
      const item = String(value[i] || '').trim();
      if (item) return item;
    }
    return null;
  }
  const text = String(value || '').trim();
  return text || null;
}

function normalizeSourceRef(value) {
  const text = String(value || '').trim();
  return text || null;
}

function normalizeKnowledgePayload(values) {
  return {
    ...values,
    category: values.category || 'pattern_dictionary',
    sub_category: normalizeSubCategory(values.sub_category),
    title: values.title?.trim() || '',
    summary: values.summary?.trim() || null,
    content: values.content?.trim() || null,
    tags: normalizeTagList(values.tags),
    status: values.status || 'active',
    priority: values.priority || 'medium',
    source_ref: values.source_ref?.trim() || null,
    related_note_ids: normalizeNoteIdList(values.related_note_ids),
  };
}

function normalizeNoteIdList(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  const seen = new Set();
  for (const item of raw) {
    const primitive = (item && typeof item === 'object' && 'value' in item)
      ? item.value
      : item;
    const id = Number(primitive);
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

function formatDateText(value) {
  if (!value) return '--';
  const ts = new Date(value).getTime();
  if (!Number.isFinite(ts)) return '--';
  return new Date(ts).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function statusTone(status) {
  const key = String(status || '').trim().toLowerCase();
  if (key === 'archived') return 'muted';
  return 'normal';
}

function priorityTone(priority) {
  const key = String(priority || '').trim().toLowerCase();
  if (key === 'high') return 'high';
  if (key === 'low') return 'low';
  return 'medium';
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
  const [knowledgeSubCategoryHistory, setKnowledgeSubCategoryHistory] = useState([]);
  const [knowledgeSourceRefHistory, setKnowledgeSourceRefHistory] = useState([]);
  const [knowledgeNotebookMap, setKnowledgeNotebookMap] = useState(new Map());
  const [knowledgeExpandedCategory, setKnowledgeExpandedCategory] = useState(null);
  const [knowledgeExpandedSubFolderMap, setKnowledgeExpandedSubFolderMap] = useState({});
  const [maintainSidebarCollapsed, setMaintainSidebarCollapsed] = useState(false);
  const [knowledgeDetailDrawerOpen, setKnowledgeDetailDrawerOpen] = useState(false);
  const [knowledgeFontPopoverOpen, setKnowledgeFontPopoverOpen] = useState(false);
  const [knowledgeCategoryModalOpen, setKnowledgeCategoryModalOpen] = useState(false);
  const [knowledgeCategoryDeletingOpen, setKnowledgeCategoryDeletingOpen] = useState(false);
  const [knowledgeCategorySubmitting, setKnowledgeCategorySubmitting] = useState(false);
  const [knowledgeCategoryDeleteSubmitting, setKnowledgeCategoryDeleteSubmitting] = useState(false);
  const [knowledgeCategoryDeleteError, setKnowledgeCategoryDeleteError] = useState('');
  const [knowledgeCategoryCreateError, setKnowledgeCategoryCreateError] = useState('');
  const [knowledgeCategoryForm] = Form.useForm();
  const [knowledgeReaderFontLevel, setKnowledgeReaderFontLevel] = useState(loadKnowledgeReaderFontLevel);
  const [knowledgeForm] = Form.useForm();

  const [brokerRows, setBrokerRows] = useState([]);
  const [brokerLoading, setBrokerLoading] = useState(false);
  const [brokerSaving, setBrokerSaving] = useState(false);
  const [brokerEditing, setBrokerEditing] = useState(false);
  const [selectedBrokerId, setSelectedBrokerId] = useState(null);
  const [brokerKeyword, setBrokerKeyword] = useState('');
  const [brokerForm] = Form.useForm();

  const selectedKnowledge = useMemo(
    () => knowledgeRows.find((x) => x.id === selectedKnowledgeId) || null,
    [knowledgeRows, selectedKnowledgeId]
  );

  const selectedBroker = useMemo(
    () => brokerRows.find((x) => x.id === selectedBrokerId) || null,
    [brokerRows, selectedBrokerId]
  );

  const brokerFilteredRows = useMemo(() => {
    const keyword = brokerKeyword.trim().toLowerCase();
    if (!keyword) return brokerRows;
    return brokerRows.filter((item) => {
      const name = String(item.name || '').toLowerCase();
      const account = String(item.account || '').toLowerCase();
      const notes = String(item.notes || '').toLowerCase();
      return name.includes(keyword) || account.includes(keyword) || notes.includes(keyword);
    });
  }, [brokerRows, brokerKeyword]);

  const knowledgeCategoryOptions = useMemo(() => {
    const values = new Set();
    for (const item of knowledgeCategories) {
      const name = String(item || '').trim();
      if (name) values.add(name);
    }
    for (const row of knowledgeRows) {
      const name = String(row?.category || '').trim();
      if (name) values.add(name);
    }
    return Array.from(values)
      .sort((a, b) => mapLabel(KNOWLEDGE_CATEGORY_ZH, a).localeCompare(mapLabel(KNOWLEDGE_CATEGORY_ZH, b), 'zh-CN'))
      .map((value) => ({ value, label: mapLabel(KNOWLEDGE_CATEGORY_ZH, value) }));
  }, [knowledgeCategories, knowledgeRows]);

  const knowledgeTagOptions = useMemo(() => {
    const set = new Set();
    knowledgeRows.forEach((item) => normalizeTagList(item.tags || item.tags_text).forEach((tag) => set.add(tag)));
    return Array.from(set).map((x) => ({ value: x, label: x }));
  }, [knowledgeRows]);

  const knowledgeSubCategoryOptions = useMemo(() => {
    const set = new Set(knowledgeSubCategoryHistory);
    knowledgeRows.forEach((item) => {
      const name = normalizeSubCategory(item.sub_category);
      if (name) set.add(name);
    });
    return Array.from(set)
      .sort((a, b) => a.localeCompare(b, 'zh-CN'))
      .map((x) => ({ value: x, label: x }));
  }, [knowledgeRows, knowledgeSubCategoryHistory]);

  const knowledgeSourceRefOptions = useMemo(() => {
    const set = new Set(knowledgeSourceRefHistory);
    knowledgeRows.forEach((item) => {
      const value = normalizeSourceRef(item.source_ref);
      if (value) set.add(value);
    });
    return Array.from(set)
      .sort((a, b) => a.localeCompare(b, 'zh-CN'))
      .map((x) => ({ value: x, label: x }));
  }, [knowledgeRows, knowledgeSourceRefHistory]);

  const knowledgeGroupedRows = useMemo(() => {
    const priorityRank = { high: 0, medium: 1, low: 2 };
    const maintenanceTs = (item) => {
      const updated = item?.updated_at ? new Date(item.updated_at).getTime() : NaN;
      if (Number.isFinite(updated)) return updated;
      const created = item?.created_at ? new Date(item.created_at).getTime() : NaN;
      if (Number.isFinite(created)) return created;
      return Number.MAX_SAFE_INTEGER;
    };
    const compareKnowledgeItem = (a, b) => {
      const pa = priorityRank[a?.priority] ?? 99;
      const pb = priorityRank[b?.priority] ?? 99;
      if (pa !== pb) return pa - pb;

      const ta = maintenanceTs(a);
      const tb = maintenanceTs(b);
      if (ta !== tb) return ta - tb;

      return (Number(a?.id) || 0) - (Number(b?.id) || 0);
    };

    const groups = new Map();
    for (const item of knowledgeRows) {
      const category = (item.category || '').trim() || 'uncategorized';
      if (!groups.has(category)) {
        groups.set(category, { rootItems: [], subMap: new Map() });
      }
      const bucket = groups.get(category);
      const subCategory = normalizeSubCategory(item.sub_category);
      if (subCategory) {
        if (!bucket.subMap.has(subCategory)) bucket.subMap.set(subCategory, []);
        bucket.subMap.get(subCategory).push(item);
      } else {
        bucket.rootItems.push(item);
      }
    }
    return Array.from(groups.entries())
      .map(([category, bucket]) => {
        const rootItems = [...bucket.rootItems].sort(compareKnowledgeItem);
        const subGroups = Array.from(bucket.subMap.entries())
          .map(([subCategory, items]) => ({
            subCategory,
            label: subCategory,
            items: [...items].sort(compareKnowledgeItem),
          }))
          .sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'));
        const totalCount = rootItems.length + subGroups.reduce((acc, group) => acc + group.items.length, 0);
        return {
          category,
          label: category === 'uncategorized' ? '未分类' : mapLabel(KNOWLEDGE_CATEGORY_ZH, category),
          rootItems,
          subGroups,
          totalCount,
        };
      })
      .sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'));
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
      setKnowledgeSubCategoryHistory((prev) => {
        const set = new Set(prev);
        rows.forEach((item) => {
          const name = normalizeSubCategory(item.sub_category);
          if (name) set.add(name);
        });
        return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-CN'));
      });
      setKnowledgeSourceRefHistory((prev) => {
        const set = new Set(prev);
        rows.forEach((item) => {
          const value = normalizeSourceRef(item.source_ref);
          if (value) set.add(value);
        });
        return Array.from(set).sort((a, b) => a.localeCompare(b, 'zh-CN'));
      });
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
    if (!knowledgeRows.length) {
      setKnowledgeExpandedCategory(null);
    } else if (knowledgeExpandedCategory && !knowledgeRows.some((x) => ((x.category || '').trim() || 'uncategorized') === knowledgeExpandedCategory)) {
      setKnowledgeExpandedCategory(null);
    }
  }, [knowledgeRows, knowledgeExpandedCategory]);

  useEffect(() => {
    if (!selectedKnowledge) {
      knowledgeForm.resetFields();
      knowledgeForm.setFieldsValue({
        category: 'pattern_dictionary',
        sub_category: undefined,
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
      sub_category: selectedKnowledge.sub_category || undefined,
      tags: normalizeTagList(selectedKnowledge.tags || selectedKnowledge.tags_text),
      related_note_ids: (selectedKnowledge.related_notes || []).map((note) => note.id),
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

  useEffect(() => {
    setKnowledgeDetailDrawerOpen(false);
  }, [selectedKnowledgeId, moduleKey]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(KNOWLEDGE_READER_FONT_STORAGE_KEY, knowledgeReaderFontLevel);
    } catch {
      // ignore
    }
  }, [knowledgeReaderFontLevel]);

  const createKnowledge = () => {
    setSelectedKnowledgeId(null);
    knowledgeForm.resetFields();
    knowledgeForm.setFieldsValue({
      category: knowledgeFilters.category || 'pattern_dictionary',
      sub_category: undefined,
      status: 'active',
      priority: 'medium',
      tags: [],
      related_note_ids: [],
    });
    setKnowledgeEditing(true);
  };

  const openCreateKnowledgeCategoryModal = () => {
    setKnowledgeCategoryCreateError('');
    knowledgeCategoryForm.resetFields();
    knowledgeCategoryForm.setFieldsValue({ name: '' });
    setKnowledgeCategoryModalOpen(true);
  };

  const submitCreateKnowledgeCategory = async () => {
    try {
      setKnowledgeCategoryCreateError('');
      const values = await knowledgeCategoryForm.validateFields();
      const name = String(values.name || '').trim();
      const lowerName = name.toLocaleLowerCase();
      const duplicate = knowledgeCategoryOptions.some((item) => String(item.value || '').trim().toLocaleLowerCase() === lowerName);
      if (duplicate) {
        knowledgeCategoryForm.setFields([{ name: 'name', errors: ['同级分类已存在，请使用其他名称'] }]);
        return;
      }
      setKnowledgeCategorySubmitting(true);
      await knowledgeApi.createCategory(name);
      message.success('分类已创建');
      setKnowledgeCategoryModalOpen(false);
      await loadKnowledgeCategories();
      setKnowledgeFilters((prev) => ({ ...prev, category: name }));
      setKnowledgeExpandedCategory(name);
      if (knowledgeEditing) {
        knowledgeForm.setFieldValue('category', name);
      }
    } catch (e) {
      if (!e?.errorFields) {
        setKnowledgeCategoryCreateError(e?.response?.data?.detail || '分类创建失败');
      }
    } finally {
      setKnowledgeCategorySubmitting(false);
    }
  };

  const openDeleteKnowledgeCategoryModal = async () => {
    const category = (knowledgeFilters.category || '').trim();
    if (!category) return;
    setKnowledgeCategoryDeleteError('');
    setKnowledgeCategoryDeletingOpen(true);
  };

  const submitDeleteKnowledgeCategory = async () => {
    const category = (knowledgeFilters.category || '').trim();
    if (!category) return;
    try {
      setKnowledgeCategoryDeleteError('');
      setKnowledgeCategoryDeleteSubmitting(true);
      await knowledgeApi.deleteCategory(category);
      message.success('分类已删除');
      setKnowledgeCategoryDeletingOpen(false);
      setKnowledgeFilters((prev) => ({ ...prev, category: undefined }));
      await loadKnowledgeCategories();
      if (knowledgeEditing && String(knowledgeForm.getFieldValue('category') || '').trim() === category) {
        knowledgeForm.setFieldValue('category', 'pattern_dictionary');
      }
    } catch (e) {
      setKnowledgeCategoryDeleteError(e?.response?.data?.detail || '分类删除失败');
    } finally {
      setKnowledgeCategoryDeleteSubmitting(false);
    }
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
      message.success('知识条目已移入回收站');
      await loadKnowledge();
      setKnowledgeEditing(false);
      await loadKnowledgeCategories();
    } catch {
      message.error('移入回收站失败');
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
      message.success('券商信息已移入回收站');
      await loadBrokers();
      setBrokerEditing(false);
    } catch {
      message.error('移入回收站失败');
    }
  };

  const selectKnowledge = (id) => {
    const next = knowledgeRows.find((x) => x.id === id);
    const nextCategory = (next?.category || '').trim() || 'uncategorized';
    const nextSubCategory = normalizeSubCategory(next?.sub_category);
    if (nextCategory) {
      setKnowledgeExpandedCategory(nextCategory);
      setKnowledgeExpandedSubFolderMap((prev) => ({
        ...prev,
        [nextCategory]: nextSubCategory || null,
      }));
    }
    setSelectedKnowledgeId(id);
    setKnowledgeEditing(false);
  };

  const startEditKnowledge = () => {
    if (!selectedKnowledge) return;
    knowledgeForm.setFieldsValue({
      ...selectedKnowledge,
      sub_category: selectedKnowledge.sub_category || undefined,
      tags: normalizeTagList(selectedKnowledge.tags || selectedKnowledge.tags_text),
      related_note_ids: (selectedKnowledge.related_notes || []).map((note) => note.id),
    });
    setKnowledgeEditing(true);
  };

  const cancelKnowledgeEdit = () => {
    if (selectedKnowledge) {
      knowledgeForm.setFieldsValue({
        ...selectedKnowledge,
        sub_category: selectedKnowledge.sub_category || undefined,
        tags: normalizeTagList(selectedKnowledge.tags || selectedKnowledge.tags_text),
        related_note_ids: (selectedKnowledge.related_notes || []).map((note) => note.id),
      });
      setKnowledgeEditing(false);
      return;
    }
    knowledgeForm.resetFields();
    knowledgeForm.setFieldsValue({
      category: knowledgeFilters.category || 'pattern_dictionary',
      sub_category: undefined,
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
  const selectedKnowledgeRelatedNotes = selectedKnowledge?.related_notes || [];
  const knowledgeReaderStyle = useMemo(() => {
    const scale = Number.isFinite(Number(knowledgeReaderFontLevel))
      ? Number(knowledgeReaderFontLevel)
      : KNOWLEDGE_READER_DEFAULT_SCALE;
    const ratio = scale / 100;
    const fontSize = `${(14 * ratio).toFixed(2)}px`;
    const lineHeight = (1.96 + (ratio - 1) * 0.42).toFixed(2);
    const paragraphSpacing = `${(0.8 + (ratio - 1) * 0.42).toFixed(2)}em`;
    return {
      '--reader-font-size': fontSize,
      '--reader-line-height': lineHeight,
      '--reader-paragraph-spacing': paragraphSpacing,
    };
  }, [knowledgeReaderFontLevel]);
  const selectedKnowledgePath = selectedKnowledge
    ? [mapLabel(KNOWLEDGE_CATEGORY_ZH, selectedKnowledge.category), normalizeSubCategory(selectedKnowledge.sub_category)]
      .filter(Boolean)
      .join(' / ')
    : '--';
  const currentCategoryName = (knowledgeFilters.category || '').trim();
  const resolveScrollTarget = () => document.querySelector('.app-content') || window;

  const renderKnowledgeBadges = (item, variant = 'default') => (
    <Space size={4} wrap>
      <Tag className={`maintain-pill ${variant === 'soft' ? 'maintain-pill-soft' : ''} maintain-pill-status maintain-pill-status-${statusTone(item.status)}`}>
        {mapLabel(KNOWLEDGE_STATUS_ZH, item.status)}
      </Tag>
      <Tag className={`maintain-pill ${variant === 'soft' ? 'maintain-pill-soft' : ''} maintain-pill-priority maintain-pill-priority-${priorityTone(item.priority)}`}>
        {mapLabel(KNOWLEDGE_PRIORITY_ZH, item.priority)}
      </Tag>
    </Space>
  );

  const renderKnowledgeListItem = (item) => {
    const itemTags = normalizeTagList(item.tags || item.tags_text);
    const isActive = item.id === selectedKnowledgeId;
    return (
      <List.Item
        className={`maintain-tree-item ${isActive ? 'active' : ''}`}
        onClick={() => selectKnowledge(item.id)}
      >
        <div className="maintain-tree-item-main">
          <div className="maintain-tree-item-title-row">
            <div className="maintain-tree-item-title" title={item.title || '-'}>{item.title || '-'}</div>
            {isActive ? renderKnowledgeBadges(item, 'soft') : null}
          </div>
          <div className="maintain-tree-item-meta">更新于 {formatDateText(item.updated_at || item.created_at)}</div>
          {isActive && itemTags.length > 0 ? (
            <div className="maintain-tree-item-tags">
              {itemTags.slice(0, 1).map((t) => (
                <Tag key={`${item.id}-${t}`} className="maintain-pill maintain-pill-plain">{t}</Tag>
              ))}
              {itemTags.length > 1 ? <Tag className="maintain-pill maintain-pill-plain">+{itemTags.length - 1}</Tag> : null}
            </div>
          ) : null}
        </div>
      </List.Item>
    );
  };

  const renderTreeSectionTitle = (text, count, opened, onToggle, level = 'category') => (
    <button type="button" className={`maintain-tree-toggle maintain-tree-toggle-${level}`} onClick={onToggle}>
      <span className="maintain-tree-toggle-main">
        <span className="maintain-tree-toggle-icon">{opened ? <DownOutlined /> : <RightOutlined />}</span>
        <span className="maintain-tree-toggle-folder"><FolderOutlined /></span>
        <span className="maintain-tree-toggle-text">{text}</span>
      </span>
      <span className="maintain-tree-toggle-count">{count}</span>
    </button>
  );

  return (
    <div className="maintain-workspace">
      <div className="maintain-header-card maintain-toolbar">
        <div className="maintain-header-main">
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>信息维护工作台</Typography.Title>
            <Typography.Text type="secondary">知识沉淀与券商来源维护统一在同一工作台中，保持一致操作节奏。</Typography.Text>
          </div>
          <div className="maintain-header-actions">
            <Segmented
              value={moduleKey}
              onChange={setModuleKey}
              options={[
                { label: '知识库', value: 'knowledge' },
                { label: '券商来源', value: 'broker' },
              ]}
            />
            <Button
              icon={maintainSidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setMaintainSidebarCollapsed((prev) => !prev)}
            >
              {maintainSidebarCollapsed ? '展开目录' : '收起目录'}
            </Button>
          </div>
        </div>
      </div>

      {moduleKey === 'knowledge' && (
        <>
          <div className="maintain-toolbar-strip">
            <div className="maintain-tool-group">
              <div className="maintain-tool-label">检索</div>
              <div className="maintain-tool-fields">
                <Select
                  size="small"
                  allowClear
                  value={knowledgeFilters.category}
                  options={knowledgeCategoryOptions}
                  placeholder="分类"
                  onChange={(v) => setKnowledgeFilters((p) => ({ ...p, category: v }))}
                />
                <Select
                  size="small"
                  allowClear
                  value={knowledgeFilters.status}
                  options={KNOWLEDGE_STATUS_OPTIONS}
                  placeholder="状态"
                  onChange={(v) => setKnowledgeFilters((p) => ({ ...p, status: v }))}
                />
                <Select
                  size="small"
                  allowClear
                  value={knowledgeFilters.tag}
                  options={knowledgeTagOptions}
                  placeholder="标签"
                  onChange={(v) => setKnowledgeFilters((p) => ({ ...p, tag: v }))}
                />
                <Search
                  size="small"
                  allowClear
                  value={knowledgeFilters.q}
                  placeholder="搜索标题/标签/次级分类/内容"
                  onChange={(e) => {
                    const value = e.target.value;
                    if (!value) setKnowledgeFilters((p) => ({ ...p, q: '' }));
                  }}
                  onSearch={(v) => setKnowledgeFilters((p) => ({ ...p, q: v }))}
                />
              </div>
            </div>
            <div className="maintain-tool-group maintain-tool-group-meta">
              <div className="maintain-tool-label">分类</div>
              <div className="maintain-tool-inline-text">
                当前：{knowledgeFilters.category ? mapLabel(KNOWLEDGE_CATEGORY_ZH, knowledgeFilters.category) : '未选择'}
              </div>
              <Space size={6} wrap className="maintain-category-actions">
                <Button size="small" onClick={openCreateKnowledgeCategoryModal}>新建一级分类</Button>
                <Button size="small" danger disabled={!knowledgeFilters.category} onClick={openDeleteKnowledgeCategoryModal}>删除当前分类</Button>
              </Space>
            </div>
            <div className="maintain-tool-group maintain-tool-group-actions">
              <div className="maintain-tool-label">条目</div>
              <div className="maintain-tool-actions">
                <Button size="small" type="primary" onClick={createKnowledge} icon={<PlusOutlined />}>新建</Button>
                <ReadEditActions
                  editing={knowledgeEditing}
                  saving={knowledgeSaving}
                  onEdit={startEditKnowledge}
                  onSave={saveKnowledge}
                  onCancel={cancelKnowledgeEdit}
                  editDisabled={!selectedKnowledgeId}
                />
                <Popconfirm
                  title={selectedKnowledge ? `确认删除知识条目「${selectedKnowledge.title || '#'+selectedKnowledge.id}」并移入回收站？` : '请先选择知识条目'}
                  onConfirm={deleteKnowledge}
                  disabled={!selectedKnowledgeId}
                >
                  <Button size="small" danger icon={<DeleteOutlined />} disabled={!selectedKnowledgeId}>删除条目</Button>
                </Popconfirm>
              </div>
            </div>
          </div>

          <Row gutter={12} className="maintain-main-row">
            {!maintainSidebarCollapsed ? (
              <Col xs={24} xl={6} xxl={5}>
                <InkSection className="maintain-list-card" loading={knowledgeLoading} title="知识目录">
                  {knowledgeGroupedRows.length === 0 ? (
                    <Empty description="暂无知识条目" />
                  ) : (
                    <div className="maintain-tree-layout">
                      {knowledgeGroupedRows.map((group) => {
                        const categoryOpen = knowledgeExpandedCategory === group.category;
                        return (
                          <section key={group.category} className={`maintain-tree-section ${categoryOpen ? 'open' : ''}`}>
                            {renderTreeSectionTitle(
                              group.label,
                              group.totalCount,
                              categoryOpen,
                              () => setKnowledgeExpandedCategory((prev) => (prev === group.category ? null : group.category)),
                              'category'
                            )}
                            {categoryOpen ? (
                              <div className="maintain-tree-section-body">
                                {group.rootItems.length > 0 ? (
                                  <List
                                    dataSource={group.rootItems}
                                    className="maintain-tree-list"
                                    renderItem={renderKnowledgeListItem}
                                  />
                                ) : null}

                                {group.subGroups.map((subGroup) => {
                                  const activeSubFolder = knowledgeExpandedSubFolderMap[group.category] || null;
                                  const subOpen = activeSubFolder === subGroup.subCategory;
                                  return (
                                    <div key={`${group.category}-${subGroup.subCategory}`} className={`maintain-tree-sub ${subOpen ? 'open' : ''}`}>
                                      {renderTreeSectionTitle(
                                        subGroup.label,
                                        subGroup.items.length,
                                        subOpen,
                                        () => setKnowledgeExpandedSubFolderMap((prev) => ({
                                          ...prev,
                                          [group.category]: subOpen ? null : subGroup.subCategory,
                                        })),
                                        'sub'
                                      )}
                                      {subOpen ? (
                                        <List
                                          dataSource={subGroup.items}
                                          className="maintain-tree-list maintain-tree-list-sub"
                                          renderItem={renderKnowledgeListItem}
                                        />
                                      ) : null}
                                    </div>
                                  );
                                })}
                              </div>
                            ) : null}
                          </section>
                        );
                      })}
                    </div>
                  )}
                </InkSection>
              </Col>
            ) : null}

            <Col xs={24} xl={maintainSidebarCollapsed ? 24 : 18} xxl={maintainSidebarCollapsed ? 24 : 19}>
              <InkSection className="maintain-editor-card">
                {knowledgeEditing ? (
                  <Form form={knowledgeForm} layout="vertical" initialValues={{ category: 'pattern_dictionary', sub_category: undefined, status: 'active', priority: 'medium', tags: [], related_note_ids: [] }}>
                    <div className="maintain-form-section">
                      <div className="maintain-group-header">
                        <span className="maintain-group-name"><ReadOutlined />研究内容</span>
                      </div>
                      <Row gutter={12}>
                        <Col span={16}><Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}><Input placeholder="例如：趋势启动回调判定" /></Form.Item></Col>
                        <Col span={8}><Form.Item name="category" label="分类"><Select showSearch options={knowledgeCategoryOptions} /></Form.Item></Col>
                        <Col span={24}><Form.Item name="summary" label="摘要"><TextArea rows={3} placeholder="用 1-3 句话提炼核心结论" /></Form.Item></Col>
                        <Form.Item name="content" hidden><Input /></Form.Item>
                        <Col span={24}>
                          <Form.Item shouldUpdate noStyle>
                            {() => (
                              <ResearchContentPanel
                                editing
                                title="研究正文"
                                showStandardFields={false}
                                value={knowledgeForm.getFieldValue('content') || ''}
                                onChange={(next) => knowledgeForm.setFieldValue('content', next)}
                              />
                            )}
                          </Form.Item>
                        </Col>
                      </Row>
                    </div>

                    <div className="maintain-form-section">
                      <div className="maintain-group-header">
                        <span className="maintain-group-name"><ShareAltOutlined />知识属性与关联</span>
                      </div>
                      <Row gutter={12}>
                        <Col span={8}>
                          <Form.Item name="sub_category" label="次级分类">
                            <AutoComplete
                              options={knowledgeSubCategoryOptions}
                              placeholder="输入或选择次级分类"
                              filterOption={(inputValue, option) => String(option?.value || '').toLowerCase().includes(inputValue.toLowerCase())}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={8}><Form.Item name="status" label="状态"><Select options={KNOWLEDGE_STATUS_OPTIONS} /></Form.Item></Col>
                        <Col span={8}><Form.Item name="priority" label="优先级"><Select options={KNOWLEDGE_PRIORITY_OPTIONS} /></Form.Item></Col>
                        <Col span={12}>
                          <Form.Item name="source_ref" label="来源引用">
                            <AutoComplete
                              options={knowledgeSourceRefOptions}
                              placeholder="链接/来源（输入或选择历史）"
                              filterOption={(inputValue, option) => String(option?.value || '').toLowerCase().includes(inputValue.toLowerCase())}
                            />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
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
                              filterOption={false}
                              optionFilterProp="label"
                              options={knowledgeDocOptions}
                              onSearch={searchKnowledgeDocs}
                              onChange={(vals) => knowledgeForm.setFieldValue('related_note_ids', normalizeNoteIdList(vals))}
                              placeholder="输入关键字搜索笔记文档并多选"
                              notFoundContent={knowledgeDocSearching ? '搜索中...' : '无匹配文档'}
                            />
                          </Form.Item>
                        </Col>
                      </Row>
                    </div>
                  </Form>
                ) : !selectedKnowledge ? (
                  <Empty description="请选择左侧知识条目或新建" />
                ) : (
                  <div className="maintain-detail-layout">
                    <div className="maintain-reading-toolbar">
                      <Typography.Text type="secondary" className="maintain-reading-title">
                        {selectedKnowledge.title || `知识 #${selectedKnowledge.id}`}
                      </Typography.Text>
                      <Space size={6} className="maintain-reading-actions">
                        <Popover
                          trigger="click"
                          placement="bottomRight"
                          open={knowledgeFontPopoverOpen}
                          onOpenChange={setKnowledgeFontPopoverOpen}
                          overlayClassName="maintain-font-popover"
                          content={(
                            <div className="maintain-font-panel">
                              <div className="maintain-font-panel-head">
                                <Typography.Text className="maintain-font-panel-title">阅读字号</Typography.Text>
                                <Typography.Text type="secondary">{knowledgeReaderFontLevel}%</Typography.Text>
                              </div>
                              <Slider
                                min={KNOWLEDGE_READER_SCALE_MIN}
                                max={KNOWLEDGE_READER_SCALE_MAX}
                                step={KNOWLEDGE_READER_SCALE_STEP}
                                value={knowledgeReaderFontLevel}
                                onChange={setKnowledgeReaderFontLevel}
                                tooltip={{ formatter: (value) => `${value}%` }}
                              />
                              <div className="maintain-font-panel-foot">
                                <Typography.Text type="secondary">95%</Typography.Text>
                                <Button
                                  type="text"
                                  size="small"
                                  onClick={() => setKnowledgeReaderFontLevel(KNOWLEDGE_READER_DEFAULT_SCALE)}
                                >
                                  恢复默认
                                </Button>
                                <Typography.Text type="secondary">135%</Typography.Text>
                              </div>
                            </div>
                          )}
                        >
                          <Button size="small" className="maintain-font-trigger">Aa</Button>
                        </Popover>
                        <Button size="small" onClick={() => setKnowledgeDetailDrawerOpen(true)}>
                          详情
                        </Button>
                      </Space>
                    </div>

                    <div className="maintain-article-paper maintain-article-reading" style={knowledgeReaderStyle}>
                      <ResearchContentPanel showStandardFields={false} value={selectedKnowledge.content} />
                    </div>

                    <Drawer
                      title="知识详情"
                      placement="right"
                      width={440}
                      onClose={() => setKnowledgeDetailDrawerOpen(false)}
                      open={knowledgeDetailDrawerOpen}
                      className="maintain-detail-drawer"
                    >
                      <div className="maintain-drawer-group">
                        <Typography.Text className="maintain-drawer-group-title">基本信息</Typography.Text>
                        <div className="maintain-drawer-block">
                          <Typography.Text className="maintain-drawer-main-title">{selectedKnowledge.title || '-'}</Typography.Text>
                          {selectedKnowledge.summary ? (
                            <Typography.Paragraph className="maintain-drawer-summary">{selectedKnowledge.summary}</Typography.Paragraph>
                          ) : null}
                          <Space size={6} wrap>
                            {renderKnowledgeBadges(selectedKnowledge)}
                          </Space>
                          <dl className="maintain-meta-list">
                            <dt><Typography.Text type="secondary" className="maintain-detail-subtitle">分类路径</Typography.Text></dt>
                            <dd><Typography.Text>{selectedKnowledgePath}</Typography.Text></dd>
                          </dl>
                          <dl className="maintain-meta-list">
                            <dt><Typography.Text type="secondary" className="maintain-detail-subtitle">更新时间</Typography.Text></dt>
                            <dd><Typography.Text>{formatDateText(selectedKnowledge.updated_at || selectedKnowledge.created_at)}</Typography.Text></dd>
                          </dl>
                        </div>
                      </div>

                      <div className="maintain-drawer-group">
                        <Typography.Text className="maintain-drawer-group-title">标签与关联</Typography.Text>
                        <div className="maintain-drawer-block">
                          <dl className="maintain-meta-list">
                            <dt><Typography.Text type="secondary" className="maintain-detail-subtitle">标签</Typography.Text></dt>
                            <dd className="maintain-detail-tags">
                              {selectedKnowledgeTags.length > 0
                                ? selectedKnowledgeTags.map((t) => <Tag key={t} className="maintain-pill maintain-pill-plain">{t}</Tag>)
                                : <Typography.Text type="secondary">-</Typography.Text>}
                            </dd>
                          </dl>
                          <dl className="maintain-meta-list maintain-related-docs">
                            <dt><Typography.Text type="secondary" className="maintain-detail-subtitle">关联文档</Typography.Text></dt>
                            <dd className="maintain-related-list">
                              {selectedKnowledgeRelatedNotes.length > 0 ? selectedKnowledgeRelatedNotes.map((note) => (
                                <a key={note.id} href={`/notes/?tab=doc&noteId=${note.id}`} target="_blank" rel="noreferrer" className="maintain-related-link">
                                  {toDocOption(note, knowledgeNotebookMap).label} (#{note.id})
                                </a>
                              )) : <Typography.Text type="secondary">-</Typography.Text>}
                            </dd>
                          </dl>
                        </div>
                      </div>

                      <div className="maintain-drawer-group">
                        <Typography.Text className="maintain-drawer-group-title">参考来源</Typography.Text>
                        <div className="maintain-drawer-block">
                          <Typography.Paragraph className="maintain-source-text" style={{ marginBottom: 0 }}>
                            {selectedKnowledge.source_ref || '-'}
                          </Typography.Paragraph>
                        </div>
                      </div>
                    </Drawer>
                  </div>
                )}
              </InkSection>
            </Col>
          </Row>
          <div className="maintain-scroll-spacer" aria-hidden />

          <Modal
            title="新增分类"
            open={knowledgeCategoryModalOpen}
            onCancel={() => {
              setKnowledgeCategoryModalOpen(false);
              setKnowledgeCategoryCreateError('');
              knowledgeCategoryForm.resetFields();
            }}
            onOk={submitCreateKnowledgeCategory}
            okText="创建分类"
            cancelText="取消"
            confirmLoading={knowledgeCategorySubmitting}
            destroyOnHidden
          >
            <Form form={knowledgeCategoryForm} layout="vertical">
              <Form.Item label="创建位置">
                <Typography.Text>一级分类</Typography.Text>
              </Form.Item>
              <Form.Item
                label="分类名称"
                name="name"
                validateTrigger={['onSubmit']}
                rules={[
                  { required: true, whitespace: true, message: '请输入分类名称' },
                  {
                    validator: (_, value) => {
                      const text = String(value || '').trim();
                      if (!text) return Promise.reject(new Error('请输入分类名称'));
                      if (text.length > 50) return Promise.reject(new Error('分类名称长度不能超过 50 个字符'));
                      return Promise.resolve();
                    },
                  },
                ]}
              >
                <Input maxLength={50} placeholder="例如：波动结构观察" />
              </Form.Item>
              {knowledgeCategoryCreateError ? (
                <Alert type="error" showIcon message={knowledgeCategoryCreateError} />
              ) : null}
            </Form>
          </Modal>

          <Modal
            title="删除分类"
            open={knowledgeCategoryDeletingOpen}
            onCancel={() => {
              setKnowledgeCategoryDeletingOpen(false);
              setKnowledgeCategoryDeleteError('');
            }}
            onOk={submitDeleteKnowledgeCategory}
            okText="删除分类"
            cancelText="取消"
            okButtonProps={{
              danger: true,
              disabled: !currentCategoryName,
            }}
            confirmLoading={knowledgeCategoryDeleteSubmitting}
            destroyOnHidden
          >
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <div>
                <Typography.Text type="secondary">删除对象</Typography.Text>
                <div><Typography.Text strong>{currentCategoryName || '-'}</Typography.Text></div>
                <div><Typography.Text type="secondary">类型：一级分类</Typography.Text></div>
              </div>
              <Alert
                type="warning"
                showIcon
                message="删除规则"
                description="删除后，该分类下已有知识条目会自动归入“未分类”。"
              />
              {knowledgeCategoryDeleteError ? (
                <Alert type="error" showIcon message={knowledgeCategoryDeleteError} />
              ) : null}
            </Space>
          </Modal>
        </>
      )}

      {moduleKey === 'broker' && (
        <>
          <div className="maintain-toolbar-strip">
            <div className="maintain-tool-group">
              <div className="maintain-tool-label">检索</div>
              <Search
                size="small"
                allowClear
                value={brokerKeyword}
                placeholder="搜索券商名称/账号/备注"
                onChange={(e) => setBrokerKeyword(e.target.value || '')}
                onSearch={(v) => setBrokerKeyword(v || '')}
              />
              <div className="maintain-tool-inline-text">显示 {brokerFilteredRows.length} / {brokerRows.length} 条来源</div>
            </div>
            <div className="maintain-tool-group maintain-tool-group-actions">
              <div className="maintain-tool-label">来源操作</div>
              <div className="maintain-tool-actions">
                <Button size="small" type="primary" onClick={createBroker} icon={<PlusOutlined />}>新建</Button>
                <ReadEditActions
                  editing={brokerEditing}
                  saving={brokerSaving}
                  onEdit={startEditBroker}
                  onSave={saveBroker}
                  onCancel={cancelBrokerEdit}
                  editDisabled={!selectedBrokerId}
                />
                <Popconfirm
                  title={selectedBroker ? `确认删除券商来源「${selectedBroker.name || '#'+selectedBroker.id}」并移入回收站？` : '请先选择券商来源'}
                  onConfirm={deleteBroker}
                  disabled={!selectedBrokerId}
                >
                  <Button size="small" danger icon={<DeleteOutlined />} disabled={!selectedBrokerId}>删除来源</Button>
                </Popconfirm>
              </div>
            </div>
          </div>

          <Row gutter={12} className="maintain-main-row">
            {!maintainSidebarCollapsed ? (
              <Col xs={24} xl={8} xxl={7}>
                <InkSection title="券商来源目录" className="maintain-list-card" loading={brokerLoading}>
                  <List
                    dataSource={brokerFilteredRows}
                    locale={{ emptyText: <Empty description="暂无券商来源" /> }}
                    renderItem={(item) => (
                      <List.Item
                        className={`maintain-tree-item ${item.id === selectedBrokerId ? 'active' : ''}`}
                        onClick={() => selectBroker(item.id)}
                      >
                        <div className="maintain-tree-item-main">
                          <div className="maintain-tree-item-title-row">
                            <div className="maintain-tree-item-title">{item.name || '-'}</div>
                          </div>
                          <div className="maintain-tree-item-meta">账号: {item.account || '--'}</div>
                        </div>
                      </List.Item>
                    )}
                  />
                </InkSection>
              </Col>
            ) : null}

            <Col xs={24} xl={maintainSidebarCollapsed ? 24 : 16} xxl={maintainSidebarCollapsed ? 24 : 17}>
              <InkSection title={selectedBrokerId ? `券商来源 #${selectedBrokerId}` : '新建券商来源'} className="maintain-editor-card">
                {brokerEditing ? (
                  <Form form={brokerForm} layout="vertical">
                    <Row gutter={12}>
                      <Col span={12}><Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}><Input placeholder="例如：宏源期货" /></Form.Item></Col>
                      <Col span={12}><Form.Item label="账号" name="account"><Input placeholder="账号/客户号" /></Form.Item></Col>
                      <Col span={12}><Form.Item label="密码" name="password"><Input.Password placeholder="可留空" /></Form.Item></Col>
                      <Col span={12}><Form.Item label="其他信息" name="extra_info"><TextArea rows={2} placeholder="通道/风控限制等" /></Form.Item></Col>
                      <Col span={24}><Form.Item label="备注" name="notes"><TextArea rows={4} /></Form.Item></Col>
                    </Row>
                  </Form>
                ) : !selectedBroker ? (
                  <Empty description="请选择左侧券商或新建" />
                ) : (
                  <div className="maintain-detail-layout">
                    <div className="maintain-detail-hero">
                      <Typography.Title level={3} className="maintain-detail-title">{selectedBroker.name || '-'}</Typography.Title>
                      <Space wrap className="maintain-detail-hero-meta">
                        <Tag className="maintain-pill maintain-pill-plain">账号: {selectedBroker.account || '--'}</Tag>
                      </Space>
                    </div>
                    <section className="maintain-detail-section">
                      <Descriptions size="small" column={1}>
                        <Descriptions.Item label="密码">{selectedBroker.password || '-'}</Descriptions.Item>
                        <Descriptions.Item label="其他信息">{selectedBroker.extra_info || '-'}</Descriptions.Item>
                        <Descriptions.Item label="备注">
                          <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                            {selectedBroker.notes || '-'}
                          </Typography.Paragraph>
                        </Descriptions.Item>
                      </Descriptions>
                    </section>
                  </div>
                )}
              </InkSection>
            </Col>
          </Row>
        </>
      )}

      <FloatButton.BackTop target={resolveScrollTarget} visibilityHeight={480} />
    </div>
  );
}
