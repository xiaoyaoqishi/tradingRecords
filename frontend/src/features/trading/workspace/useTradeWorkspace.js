import { useEffect, useState } from 'react';
import { message } from 'antd';
import dayjs from 'dayjs';
import { reviewSessionApi, tradeApi, tradePlanApi, tradeReviewApi, tradeSourceApi } from '../../../api';
import {
  EMPTY_REVIEW,
  EMPTY_REVIEW_TAXONOMY,
  EMPTY_SOURCE,
  REVIEW_FIELD_KEYS,
  normalizeText,
} from './constants';
import { taxonomyCanonicalValues } from '../localization';
import { normalizeTagList } from '../display';
import { normalizeSourceLabelForDisplay } from '../sourceDisplay';

export function useTradeWorkspace() {
  const [trades, setTrades] = useState([]);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [filters, setFilters] = useState({});
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [viewMode, setViewMode] = useState('fills');
  const [sourceOptions, setSourceOptions] = useState([]);

  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [batchEditOpen, setBatchEditOpen] = useState(false);
  const [batchPatch, setBatchPatch] = useState({ status: '', strategy_type: '', is_planned: '', notes: '' });
  const [batchReviewOpen, setBatchReviewOpen] = useState(false);
  const [batchReviewSaving, setBatchReviewSaving] = useState(false);
  const [batchReviewPatch, setBatchReviewPatch] = useState({ ...EMPTY_REVIEW, tags: [] });

  const [importOpen, setImportOpen] = useState(false);
  const [importBroker, setImportBroker] = useState('宏源期货');
  const [importText, setImportText] = useState('');
  const [importResult, setImportResult] = useState(null);

  const [reviewTaxonomy, setReviewTaxonomy] = useState(EMPTY_REVIEW_TAXONOMY);
  const [detailOpen, setDetailOpen] = useState(false);
  const [activeTradeId, setActiveTradeId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailSavingReview, setDetailSavingReview] = useState(false);
  const [detailSavingSource, setDetailSavingSource] = useState(false);
  const [detailSavingLegacy, setDetailSavingLegacy] = useState(false);
  const [detailTrade, setDetailTrade] = useState(null);
  const [detailReview, setDetailReview] = useState(EMPTY_REVIEW);
  const [detailReviewExists, setDetailReviewExists] = useState(false);
  const [detailSource, setDetailSource] = useState(EMPTY_SOURCE);
  const [detailLegacy, setDetailLegacy] = useState({ review_note: '', notes: '' });

  useEffect(() => {
    if (viewMode === 'fills') loadTrades();
    else loadPositions();
  }, [filters, pagination.current, pagination.pageSize, viewMode]);

  useEffect(() => {
    loadSources();
    loadReviewTaxonomy();
  }, []);

  const loadSources = async () => {
    try {
      const res = await tradeApi.sources();
      const items = res.data?.items || [];
      setSourceOptions(items.map((v) => ({ label: v, value: v })));
    } catch {
      setSourceOptions([]);
    }
  };

  const loadReviewTaxonomy = async () => {
    try {
      const res = await tradeReviewApi.taxonomy();
      setReviewTaxonomy({
        opportunity_structure: res.data?.opportunity_structure || [],
        edge_source: res.data?.edge_source || [],
        failure_type: res.data?.failure_type || [],
        review_conclusion: res.data?.review_conclusion || [],
      });
    } catch {
      setReviewTaxonomy({
        ...EMPTY_REVIEW_TAXONOMY,
        opportunity_structure: taxonomyCanonicalValues('opportunity_structure'),
        edge_source: taxonomyCanonicalValues('edge_source'),
        failure_type: taxonomyCanonicalValues('failure_type'),
        review_conclusion: taxonomyCanonicalValues('review_conclusion'),
      });
    }
  };

  const loadTrades = async () => {
    setLoading(true);
    try {
      const countRes = await tradeApi.count(filters);
      const total = countRes.data?.total || 0;
      const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize));
      const current = Math.min(pagination.current, maxPage);
      const listRes = await tradeApi.list({ page: current, size: pagination.pageSize, ...filters });
      const list = listRes.data || [];
      setTrades(list);
      setPagination((p) => ({ ...p, current, total }));
      setSelectedRowKeys((prev) => prev.filter((id) => list.some((x) => x.id === id)));
    } catch {
      message.error('加载失败');
    }
    setLoading(false);
  };

  const loadPositions = async () => {
    setLoading(true);
    try {
      const res = await tradeApi.positions(filters);
      setPositions(res.data || []);
    } catch {
      message.error('加载持仓失败');
    }
    setLoading(false);
  };

  const updateFilter = (key, val) => {
    setFilters((prev) => {
      if (val === undefined || val === null) {
        const { [key]: _omit, ...rest } = prev;
        setPagination((p) => ({ ...p, current: 1 }));
        return rest;
      }
      setPagination((p) => ({ ...p, current: 1 }));
      return { ...prev, [key]: val };
    });
  };

  const setDateRange = (dates) => {
    if (dates) {
      setFilters((f) => ({
        ...f,
        date_from: dates[0].format('YYYY-MM-DD'),
        date_to: dates[1].format('YYYY-MM-DD'),
      }));
      return;
    }
    setFilters((f) => {
      const { date_from, date_to, ...rest } = f;
      return rest;
    });
  };

  const loadTradeDetail = async (tradeId) => {
    setDetailLoading(true);
    try {
      const [tradeRes, reviewRes, sourceRes] = await Promise.all([
        tradeApi.get(tradeId),
        tradeReviewApi.get(tradeId).catch((e) => (e.response?.status === 404 ? { data: null } : Promise.reject(e))),
        tradeSourceApi.get(tradeId),
      ]);
      const tradeData = tradeRes.data || null;
      setDetailTrade(tradeData);
      setDetailLegacy({ review_note: tradeData?.review_note || '', notes: tradeData?.notes || '' });

      const reviewData = reviewRes.data || {};
      const normalizedReview = { ...EMPTY_REVIEW };
      REVIEW_FIELD_KEYS.forEach((k) => {
        normalizedReview[k] = reviewData?.[k] || '';
      });
      normalizedReview.tags = Array.isArray(reviewData?.tags)
        ? normalizeTagList(reviewData.tags)
        : normalizeTagList(String(reviewData?.review_tags || ''));
      setDetailReview(normalizedReview);
      setDetailReviewExists(!!reviewRes.data);

      const sourceData = sourceRes.data || {};
      setDetailSource({
        ...EMPTY_SOURCE,
        ...sourceData,
        broker_name: sourceData?.broker_name || '',
        source_label: normalizeSourceLabelForDisplay(sourceData?.source_label),
        import_channel: sourceData?.import_channel || '',
        parser_version: sourceData?.parser_version || '',
        source_note_snapshot: sourceData?.source_note_snapshot || '',
      });
    } catch {
      message.error('详情加载失败');
    }
    setDetailLoading(false);
  };

  const openTradeDetail = async (tradeId) => {
    setActiveTradeId(tradeId);
    setDetailOpen(true);
    await loadTradeDetail(tradeId);
  };

  const handleDeleteTrade = async (id) => {
    await tradeApi.delete(id);
    message.success('已删除');
    if (activeTradeId === id) {
      setDetailOpen(false);
      setActiveTradeId(null);
    }
    loadTrades();
  };

  const handleSaveDetailReview = async () => {
    if (!activeTradeId) return;
    setDetailSavingReview(true);
    try {
      const payload = {};
      REVIEW_FIELD_KEYS.forEach((k) => {
        payload[k] = normalizeText(detailReview[k]);
      });
      payload.tags = Array.isArray(detailReview.tags)
        ? normalizeTagList(detailReview.tags)
        : [];
      const hasReviewData = Object.entries(payload).some(([k, v]) => (k === 'tags' ? (v || []).length > 0 : v !== null));
      if (hasReviewData) {
        await tradeReviewApi.upsert(activeTradeId, payload);
        setDetailReviewExists(true);
        message.success('结构化复盘已保存');
      } else if (detailReviewExists) {
        await tradeReviewApi.delete(activeTradeId);
        setDetailReviewExists(false);
        message.success('结构化复盘已清空');
      } else {
        message.info('未检测到可保存的结构化复盘内容');
      }
      await loadTradeDetail(activeTradeId);
      await loadTrades();
    } catch (e) {
      message.error(e.response?.data?.detail || '结构化复盘保存失败');
    }
    setDetailSavingReview(false);
  };

  const handleSaveDetailSource = async () => {
    if (!activeTradeId) return;
    setDetailSavingSource(true);
    try {
      const payload = {
        broker_name: normalizeText(detailSource.broker_name),
        source_label: normalizeText(detailSource.source_label),
        import_channel: normalizeText(detailSource.import_channel),
        parser_version: normalizeText(detailSource.parser_version),
        source_note_snapshot: normalizeText(detailSource.source_note_snapshot) || normalizeText(detailLegacy.notes),
        derived_from_notes: false,
      };
      const hasSourceData = Object.values(payload).some((v) => v !== null && v !== false);
      if (!hasSourceData && !detailSource.exists_in_db) {
        message.info('来源元数据为空，无需保存');
        return;
      }
      await tradeSourceApi.upsert(activeTradeId, payload);
      message.success('来源元数据已保存');
      await Promise.all([loadTradeDetail(activeTradeId), loadSources(), loadTrades()]);
    } catch (e) {
      message.error(e.response?.data?.detail || '来源元数据保存失败');
    }
    setDetailSavingSource(false);
  };

  const handleSaveDetailLegacy = async () => {
    if (!activeTradeId) return;
    setDetailSavingLegacy(true);
    try {
      await tradeApi.update(activeTradeId, {
        review_note: normalizeText(detailLegacy.review_note),
        notes: normalizeText(detailLegacy.notes),
      });
      message.success('兼容字段已保存');
      await loadTradeDetail(activeTradeId);
      await loadTrades();
    } catch (e) {
      message.error(e.response?.data?.detail || '兼容字段保存失败');
    }
    setDetailSavingLegacy(false);
  };

  const handleUpdateTradeSignal = async (patch) => {
    if (!activeTradeId) return;
    try {
      await tradeApi.update(activeTradeId, patch);
      await Promise.all([loadTradeDetail(activeTradeId), loadTrades()]);
    } catch (e) {
      message.error(e.response?.data?.detail || '交易信号更新失败');
    }
  };

  const handleImportTrades = async () => {
    if (!importText.trim()) {
      message.warning('请先粘贴数据');
      return;
    }
    setImportLoading(true);
    try {
      const res = await tradeApi.importPaste({ raw_text: importText, broker: importBroker });
      setImportResult(res.data || null);
      message.success(`导入完成：新增 ${res.data?.inserted || 0}，跳过 ${res.data?.skipped || 0}`);
      await Promise.all([loadTrades(), loadSources()]);
    } catch (e) {
      message.error(e.response?.data?.detail || '导入失败');
    } finally {
      setImportLoading(false);
    }
  };

  const openImportModal = () => {
    setImportText('');
    setImportResult(null);
    if (!importBroker) setImportBroker('');
    setImportOpen(true);
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return;
    }
    try {
      await Promise.all(selectedRowKeys.map((id) => tradeApi.delete(id)));
      message.success(`已删除 ${selectedRowKeys.length} 条`);
      setSelectedRowKeys([]);
      loadTrades();
    } catch {
      message.error('批量删除失败');
    }
  };

  const handleBatchEditSubmit = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return;
    }
    const patch = {};
    if (batchPatch.status) patch.status = batchPatch.status;
    if (batchPatch.strategy_type.trim()) patch.strategy_type = batchPatch.strategy_type.trim();
    if (batchPatch.is_planned === 'true') patch.is_planned = true;
    if (batchPatch.is_planned === 'false') patch.is_planned = false;
    if (batchPatch.notes.trim()) patch.notes = batchPatch.notes.trim();
    if (Object.keys(patch).length === 0) {
      message.warning('请至少填写一个要批量修改的字段');
      return;
    }
    try {
      await Promise.all(selectedRowKeys.map((id) => tradeApi.update(id, patch)));
      message.success(`已批量更新 ${selectedRowKeys.length} 条`);
      setBatchEditOpen(false);
      loadTrades();
    } catch (e) {
      message.error(e.response?.data?.detail || '批量更新失败');
    }
  };

  const openBatchEdit = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return false;
    }
    setBatchPatch({ status: '', strategy_type: '', is_planned: '', notes: '' });
    setBatchEditOpen(true);
    return true;
  };

  const openBatchStructuredReview = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return false;
    }
    setBatchReviewPatch({ ...EMPTY_REVIEW, tags: [] });
    setBatchReviewOpen(true);
    return true;
  };

  const handleBatchStructuredReviewSubmit = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return;
    }
    const payload = {};
    REVIEW_FIELD_KEYS.forEach((k) => {
      payload[k] = normalizeText(batchReviewPatch[k]);
    });
    payload.tags = Array.isArray(batchReviewPatch.tags)
      ? normalizeTagList(batchReviewPatch.tags)
      : [];
    const hasReviewData = Object.entries(payload).some(([k, v]) => (k === 'tags' ? (v || []).length > 0 : v !== null));
    if (!hasReviewData) {
      message.warning('请至少填写一个结构化复盘字段');
      return;
    }
    setBatchReviewSaving(true);
    try {
      await Promise.all(
        selectedRowKeys.map((tradeId) => tradeReviewApi.upsert(Number(tradeId), payload))
      );
      message.success(`已批量保存 ${selectedRowKeys.length} 条结构化复盘`);
      setBatchReviewOpen(false);
      await loadTrades();
    } catch (e) {
      message.error(e.response?.data?.detail || '批量保存结构化复盘失败');
    } finally {
      setBatchReviewSaving(false);
    }
  };

  const createReviewSessionFromSelected = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易');
      return null;
    }
    try {
      const payload = {
        title: `手动多选复盘会话 ${dayjs().format('YYYY-MM-DD HH:mm')}`,
        review_kind: 'custom',
        review_scope: 'custom',
        selection_mode: 'manual',
        selection_basis: `交易工作台手动多选 ${selectedRowKeys.length} 笔交易`,
        review_goal: '识别该样本中的重复执行模式与质量偏差',
        trade_ids: selectedRowKeys.map((x) => Number(x)),
      };
      const res = await reviewSessionApi.createFromSelection(payload);
      message.success('已从多选交易创建复盘会话');
      return res.data;
    } catch (e) {
      message.error(e.response?.data?.detail || '创建复盘会话失败');
      return null;
    }
  };

  const createReviewSessionFromCurrentFilter = async () => {
    try {
      const payload = {
        title: `筛选结果复盘会话 ${dayjs().format('YYYY-MM-DD HH:mm')}`,
        review_kind: 'theme',
        review_scope: 'themed',
        selection_mode: 'filter_snapshot',
        selection_target: 'full_filtered',
        selection_basis: '基于当前交易工作台筛选条件生成',
        review_goal: '评估同一筛选切片下的一致性与边际质量',
        filter_params: { ...filters },
      };
      const res = await reviewSessionApi.createFromSelection(payload);
      message.success('已从当前筛选结果创建复盘会话');
      return res.data;
    } catch (e) {
      message.error(e.response?.data?.detail || '创建复盘会话失败');
      return null;
    }
  };

  const createTradePlanFromSelected = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易');
      return null;
    }
    try {
      const selectedTrades = trades.filter((x) => selectedRowKeys.includes(x.id));
      const first = selectedTrades[0] || {};
      const plan = (
        await tradePlanApi.create({
          title: `多选交易计划 ${dayjs().format('MM-DD HH:mm')}`,
          plan_date: dayjs().format('YYYY-MM-DD'),
          status: 'draft',
          symbol: first.symbol || null,
          contract: first.contract || null,
          direction_bias: first.direction || null,
          setup_type: first.strategy_type || null,
          thesis: '基于交易工作台当前多选样本草拟',
          trade_links: [],
        })
      ).data;
      await tradePlanApi.upsertTradeLinks(plan.id, {
        trade_links: selectedRowKeys.map((tradeId, idx) => ({
          trade_id: Number(tradeId),
          sort_order: idx,
          note: null,
        })),
      });
      await Promise.all(
        selectedRowKeys.map((tradeId) => tradeApi.update(Number(tradeId), { is_planned: true }))
      );
      await loadTrades();
      message.success('已创建并关联交易计划');
      return plan;
    } catch (e) {
      message.error(e.response?.data?.detail || '创建交易计划失败');
      return null;
    }
  };

  return {
    // core data
    trades,
    positions,
    loading,
    filters,
    pagination,
    viewMode,
    sourceOptions,
    // batch
    selectedRowKeys,
    batchEditOpen,
    batchPatch,
    batchReviewOpen,
    batchReviewSaving,
    batchReviewPatch,
    // import
    importOpen,
    importLoading,
    importBroker,
    importText,
    importResult,
    // detail
    reviewTaxonomy,
    detailOpen,
    activeTradeId,
    detailLoading,
    detailSavingReview,
    detailSavingSource,
    detailSavingLegacy,
    detailTrade,
    detailReview,
    detailReviewExists,
    detailSource,
    detailLegacy,
    // setters for UI wiring
    setViewMode,
    setSelectedRowKeys,
    setPagination,
    setDetailOpen,
    setDetailReview,
    setDetailSource,
    setDetailLegacy,
    setImportBroker,
    setImportText,
    setImportOpen,
    setBatchEditOpen,
    setBatchPatch,
    setBatchReviewOpen,
    setBatchReviewPatch,
    // actions
    updateFilter,
    setDateRange,
    openTradeDetail,
    loadTradeDetail,
    handleDeleteTrade,
    handleSaveDetailReview,
    handleSaveDetailSource,
    handleSaveDetailLegacy,
    handleUpdateTradeSignal,
    handleImportTrades,
    openImportModal,
    handleBatchDelete,
    handleBatchEditSubmit,
    openBatchEdit,
    openBatchStructuredReview,
    handleBatchStructuredReviewSubmit,
    createReviewSessionFromSelected,
    createReviewSessionFromCurrentFilter,
    createTradePlanFromSelected,
  };
}

