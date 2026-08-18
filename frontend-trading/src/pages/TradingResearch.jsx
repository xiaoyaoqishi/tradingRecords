import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { Button, Empty, Input, Modal, Popconfirm, Segmented, Select, Space, Spin, Tag, Tooltip, message } from 'antd';
import {
  DeleteOutlined,
  EditOutlined,
  FileAddOutlined,
  FileTextOutlined,
  FolderAddOutlined,
  FolderOutlined,
  LinkOutlined,
  PushpinFilled,
  PushpinOutlined,
  SaveOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { researchApi, tradeApi, tradeLinkedPlanApi, tradeReviewApi } from '../api';
import { backendTimeInChina } from '../utils/datetime';
import ResearchEditor, { renderResearchContent } from '../components/ResearchEditor';
import ImageLightbox from '../components/ImageLightbox';
import TradeDetailDrawer from '../features/trading/workspace/TradeDetailDrawer';
import './TradingResearch.css';

const EMPTY_DRAFT = { title: '', folder_id: null, tags: [], content: '', is_pinned: false, trade_ids: [] };

function tradeReferenceLabel(trade) {
  const instrument = [trade.symbol, trade.contract].filter(Boolean).join(' · ') || '未知品种';
  const direction = trade.direction === 'long' ? '多' : trade.direction === 'short' ? '空' : trade.direction || '—';
  const price = trade.open_price == null
    ? ''
    : ` · ${trade.open_price}${trade.close_price == null ? '' : ` → ${trade.close_price}`}`;
  const pnl = trade.pnl == null ? '' : ` · 盈亏 ${Number(trade.pnl).toLocaleString()}`;
  const status = trade.status === 'open' ? '持仓' : trade.status === 'closed' ? '已平仓' : trade.status || '状态未知';
  return `#${trade.trade_id} · ${trade.trade_date || '日期未知'} · ${instrument} · ${direction}${price}${pnl} · ${status}`;
}

function sanitizeResearchHtml(raw) {
  if (typeof window === 'undefined') return raw || '';
  const doc = new DOMParser().parseFromString(raw || '', 'text/html');
  doc.querySelectorAll('script,style,iframe,object,embed').forEach((node) => node.remove());
  doc.querySelectorAll('details[data-research-collapse]').forEach((node) => node.removeAttribute('open'));
  doc.querySelectorAll('*').forEach((node) => {
    Array.from(node.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim().toLowerCase();
      if (name.startsWith('on') || ((name === 'href' || name === 'src') && value.startsWith('javascript:'))) {
        node.removeAttribute(attribute.name);
      }
    });
  });
  return doc.body.innerHTML;
}

function extractWikiLinks(content) {
  const matches = Array.from(String(content || '').matchAll(/\[\[([^\]#|]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]/g));
  return Array.from(new Set(matches.map((item) => item[1].trim()).filter(Boolean)));
}

function ResearchTreeNode({
  folder, folders, documentsByFolder, expanded, activeId, onToggle, onSelect, onCreate,
  onEditFolder, onDeleteFolder, onDeleteDocument, draggedDocumentId, draggedFolderId, dropTarget,
  onDragStart, onFolderDragStart, onDragEnd, onDragOverFolder, onDropOnFolder, onDragOverDocument,
  onDropOnDocument,
}) {
  const children = folders.filter((item) => item.parent_id === folder.id);
  const documents = documentsByFolder[folder.id] || [];
  const isExpanded = expanded[folder.id];
  return (
    <div className="research-tree-node">
      <div
        className={[
          'research-tree-folder',
          draggedFolderId === folder.id ? 'dragging' : '',
          dropTarget?.type === 'folder' && dropTarget.id === folder.id ? `drag-${dropTarget.placement || 'inside'}` : '',
        ].filter(Boolean).join(' ')}
        onClick={() => onToggle(folder.id)}
        title="拖拽可移动资料夹或调整顺序"
        draggable
        onDragStart={(event) => onFolderDragStart(event, folder)}
        onDragEnd={onDragEnd}
        onDragOver={(event) => onDragOverFolder(event, folder)}
        onDrop={(event) => onDropOnFolder(event, folder)}
      >
        <span className="research-tree-label">
          <span className="research-tree-arrow">{children.length || documents.length ? (isExpanded ? '▾' : '▸') : '　'}</span>
          <FolderOutlined /> {folder.name}
        </span>
        <span className="research-tree-actions" onClick={(event) => event.stopPropagation()}>
          <FileAddOutlined title="新建研究" onClick={() => onCreate(folder.id)} />
          <FolderAddOutlined title="新建子资料夹" onClick={() => onEditFolder(null, folder.id)} />
          <EditOutlined title="编辑资料夹" onClick={() => onEditFolder(folder)} />
          <Popconfirm title="确认删除空资料夹？" onConfirm={() => onDeleteFolder(folder.id)}>
            <DeleteOutlined className="danger" />
          </Popconfirm>
        </span>
      </div>
      {isExpanded ? (
        <div className="research-tree-children">
          {children.map((child) => (
            <ResearchTreeNode
              key={child.id}
              folder={child}
              folders={folders}
              documentsByFolder={documentsByFolder}
              expanded={expanded}
              activeId={activeId}
              onToggle={onToggle}
              onSelect={onSelect}
              onCreate={onCreate}
              onEditFolder={onEditFolder}
              onDeleteFolder={onDeleteFolder}
              onDeleteDocument={onDeleteDocument}
              draggedDocumentId={draggedDocumentId}
              draggedFolderId={draggedFolderId}
              dropTarget={dropTarget}
              onDragStart={onDragStart}
              onFolderDragStart={onFolderDragStart}
              onDragEnd={onDragEnd}
              onDragOverFolder={onDragOverFolder}
              onDropOnFolder={onDropOnFolder}
              onDragOverDocument={onDragOverDocument}
              onDropOnDocument={onDropOnDocument}
            />
          ))}
          {documents.map((document) => (
            <div
              key={document.id}
              className={[
                'research-tree-file',
                activeId === document.id ? 'active' : '',
                draggedDocumentId === document.id ? 'dragging' : '',
                dropTarget?.type === 'document' && dropTarget.id === document.id ? `drag-${dropTarget.placement}` : '',
              ].filter(Boolean).join(' ')}
              onClick={() => onSelect(document.id)}
              title="拖拽可移动或排序"
              draggable
              onDragStart={(event) => onDragStart(event, document)}
              onDragEnd={onDragEnd}
              onDragOver={(event) => onDragOverDocument(event, document)}
              onDrop={(event) => onDropOnDocument(event, document)}
            >
              <span className="research-tree-file-name">
                {document.is_pinned ? <PushpinFilled /> : <FileTextOutlined />}
                <span>{document.title || '无标题'}</span>
              </span>
              <span className="research-tree-actions" onClick={(event) => event.stopPropagation()}>
                <Popconfirm title="确认移入研究回收站？" onConfirm={() => onDeleteDocument(document.id)}>
                  <DeleteOutlined className="danger" />
                </Popconfirm>
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function TradingResearch() {
  const [searchParams] = useSearchParams();
  const requestedDocumentId = Number(searchParams.get('document')) || null;
  const [folders, setFolders] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [backlinks, setBacklinks] = useState([]);
  const [keyword, setKeyword] = useState('');
  const [mode, setMode] = useState('active');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [isNew, setIsNew] = useState(false);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [expanded, setExpanded] = useState({});
  const [folderModal, setFolderModal] = useState({ open: false, id: null, name: '', parent_id: null });
  const [draggedDocumentId, setDraggedDocumentId] = useState(null);
  const [draggedFolderId, setDraggedFolderId] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [lightboxImage, setLightboxImage] = useState(null);
  const [tradeSearch, setTradeSearch] = useState('');
  const [tradeOptions, setTradeOptions] = useState([]);
  const [tradeOptionsLoading, setTradeOptionsLoading] = useState(false);
  const [tradeDrawer, setTradeDrawer] = useState({
    open: false,
    tradeId: null,
    loading: false,
    trade: null,
    riskPointHistory: [],
    review: null,
    linkedPlans: [],
    linkedResearch: [],
  });
  const listRequestRef = useRef(0);
  const detailRequestRef = useRef(0);
  const selectedIdRef = useRef(null);
  const selectionRevisionRef = useRef(0);
  const tradeDrawerRequestRef = useRef(0);

  const updateSelectedId = (documentId) => {
    selectedIdRef.current = documentId;
    setSelectedId(documentId);
  };

  const selectDocument = (documentId) => {
    selectionRevisionRef.current += 1;
    updateSelectedId(documentId);
    setEditing(false);
    setIsNew(false);
  };

  const roots = useMemo(() => folders.filter((folder) => !folder.parent_id), [folders]);
  const documentsByFolder = useMemo(() => documents.reduce((result, document) => {
    (result[document.folder_id] ||= []).push(document);
    return result;
  }, {}), [documents]);
  const folderOptions = useMemo(() => {
    const walk = (parentId = null, depth = 0) => folders
      .filter((folder) => (folder.parent_id || null) === parentId)
      .flatMap((folder) => [
        { value: folder.id, label: `${'　'.repeat(depth)}📁 ${folder.name}` },
        ...walk(folder.id, depth + 1),
      ]);
    return walk();
  }, [folders]);

  const loadFolders = async () => {
    const list = (await researchApi.folders.list()).data || [];
    setFolders(list);
    setExpanded((current) => {
      if (Object.keys(current).length) return current;
      return Object.fromEntries(list.filter((folder) => !folder.parent_id).map((folder) => [folder.id, true]));
    });
    return list;
  };

  const loadDocuments = async (requestedMode = mode, requestedKeyword = keyword, preferredId = null) => {
    const requestId = ++listRequestRef.current;
    setLoading(true);
    try {
      const list = requestedMode === 'recycle'
        ? ((await researchApi.recycle.list()).data || [])
        : ((await researchApi.documents.list({
          size: 300,
          order: 'manual',
          ...(requestedKeyword.trim() ? { keyword: requestedKeyword.trim() } : {}),
        })).data?.items || []);
      if (requestId !== listRequestRef.current) return;
      setDocuments(list);
      const currentSelectedId = selectedIdRef.current;
      const nextId = preferredId && list.some((item) => item.id === preferredId)
        ? preferredId
        : list.some((item) => item.id === currentSelectedId) ? currentSelectedId : list[0]?.id || null;
      updateSelectedId(nextId);
      if (!nextId) {
        setSelectedDocument(null);
        setBacklinks([]);
      }
    } catch (error) {
      if (requestId === listRequestRef.current) message.error(error.response?.data?.detail || '研究资料加载失败');
    } finally {
      if (requestId === listRequestRef.current) setLoading(false);
    }
  };

  const loadDocument = async (documentId, requestedMode = mode) => {
    const requestId = ++detailRequestRef.current;
    setSelectedDocument(null);
    setBacklinks([]);
    if (!documentId) return;
    if (requestedMode === 'recycle') {
      const document = documents.find((item) => item.id === documentId) || null;
      if (requestId === detailRequestRef.current) setSelectedDocument(document);
      return;
    }
    try {
      const [documentResult, backlinkResult] = await Promise.all([
        researchApi.documents.get(documentId),
        researchApi.documents.backlinks(documentId),
      ]);
      if (requestId !== detailRequestRef.current) return;
      setSelectedDocument(documentResult.data);
      setBacklinks(backlinkResult.data || []);
    } catch (error) {
      if (requestId === detailRequestRef.current) message.error(error.response?.data?.detail || '研究详情加载失败');
    }
  };

  useEffect(() => { loadFolders().catch(() => message.error('研究资料夹加载失败')); }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => loadDocuments(mode, keyword), 220);
    return () => window.clearTimeout(timer);
  }, [mode, keyword]);
  useEffect(() => {
    if (mode !== 'active' || !requestedDocumentId) return;
    if (documents.some((document) => document.id === requestedDocumentId)) {
      updateSelectedId(requestedDocumentId);
    }
  }, [documents, mode, requestedDocumentId]);
  useEffect(() => { loadDocument(selectedId, mode); }, [selectedId, mode, documents]);
  useEffect(() => {
    if (!editing) return undefined;
    const timer = window.setTimeout(async () => {
      setTradeOptionsLoading(true);
      try {
        const result = await tradeApi.searchOptions({
          limit: 50,
          ...(tradeSearch.trim() ? { q: tradeSearch.trim() } : {}),
          ...(draft.trade_ids?.length ? { include_ids: draft.trade_ids.join(',') } : {}),
        });
        setTradeOptions(result.data?.items || []);
      } catch (error) {
        message.error(error.response?.data?.detail || '交易记录加载失败');
      } finally {
        setTradeOptionsLoading(false);
      }
    }, 220);
    return () => window.clearTimeout(timer);
  }, [editing, tradeSearch, draft.trade_ids]);

  const changeMode = (nextMode) => {
    selectionRevisionRef.current += 1;
    listRequestRef.current += 1;
    detailRequestRef.current += 1;
    setMode(nextMode);
    setDocuments([]);
    updateSelectedId(null);
    setSelectedDocument(null);
    setBacklinks([]);
    setEditing(false);
    setIsNew(false);
    setLoading(true);
  };

  const startNew = (folderId = null) => {
    if (!folders.length) {
      message.warning('请先新建资料夹');
      return;
    }
    const targetFolderId = folderId || roots[0]?.id || folders[0].id;
    setExpanded((current) => ({ ...current, [targetFolderId]: true }));
    selectionRevisionRef.current += 1;
    updateSelectedId(null);
    setSelectedDocument(null);
    setBacklinks([]);
    setIsNew(true);
    setEditing(true);
    setTradeSearch('');
    setTradeOptions([]);
    setDraft({ ...EMPTY_DRAFT, folder_id: targetFolderId });
  };

  const startEdit = () => {
    if (!selectedDocument) return;
    setIsNew(false);
    setEditing(true);
    setTradeSearch('');
    setTradeOptions(selectedDocument.related_trades || []);
    setDraft({
      title: selectedDocument.title || '',
      folder_id: selectedDocument.folder_id,
      tags: selectedDocument.tags || [],
      content: renderResearchContent(selectedDocument.content || ''),
      is_pinned: Boolean(selectedDocument.is_pinned),
      trade_ids: selectedDocument.trade_ids || [],
    });
  };

  const saveDocument = async () => {
    const title = draft.title.trim();
    if (!title || !draft.folder_id) {
      message.warning('标题和资料夹为必填项');
      return;
    }
    const creating = isNew;
    const selectionRevision = selectionRevisionRef.current;
    setSaving(true);
    try {
      const payload = { ...draft, title, content: sanitizeResearchHtml(draft.content) };
      const saved = creating
        ? (await researchApi.documents.create(payload)).data
        : (await researchApi.documents.update(selectedDocument.id, payload)).data;
      if (selectionRevision !== selectionRevisionRef.current) {
        setDocuments((current) => current.map((item) => (item.id === saved.id ? { ...item, ...saved } : item)));
        message.success(creating ? '研究已创建' : '研究已保存');
        return;
      }
      setEditing(false);
      setIsNew(false);
      updateSelectedId(saved.id);
      setExpanded((current) => ({ ...current, [saved.folder_id]: true }));
      await Promise.all([loadFolders(), loadDocuments('active', keyword, saved.id)]);
      await loadDocument(saved.id, 'active');
      message.success(creating ? '研究已创建' : '研究已保存');
    } catch (error) {
      message.error(error.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const deleteDocument = async (documentId) => {
    await researchApi.documents.delete(documentId);
    if (selectedId === documentId) {
      updateSelectedId(null);
      setSelectedDocument(null);
    }
    await Promise.all([loadFolders(), loadDocuments('active', keyword)]);
    message.success('已移入研究回收站');
  };

  const togglePinned = async () => {
    if (!selectedDocument) return;
    const updated = (await researchApi.documents.update(selectedDocument.id, { is_pinned: !selectedDocument.is_pinned })).data;
    setSelectedDocument(updated);
    await loadDocuments('active', keyword, updated.id);
  };

  const openFolderModal = (folder = null, parentId = null) => {
    setFolderModal({
      open: true,
      id: folder?.id || null,
      name: folder?.name || '',
      parent_id: folder?.parent_id || parentId || null,
    });
  };

  const saveFolder = async () => {
    const name = folderModal.name.trim();
    if (!name) return;
    try {
      const payload = { name, parent_id: folderModal.parent_id || null };
      const saved = folderModal.id
        ? (await researchApi.folders.update(folderModal.id, payload)).data
        : (await researchApi.folders.create(payload)).data;
      setFolderModal({ open: false, id: null, name: '', parent_id: null });
      await loadFolders();
      setExpanded((current) => ({ ...current, [saved.id]: true, ...(saved.parent_id ? { [saved.parent_id]: true } : {}) }));
    } catch (error) {
      message.error(error.response?.data?.detail || '资料夹保存失败');
    }
  };

  const deleteFolder = async (folderId) => {
    try {
      await researchApi.folders.delete(folderId);
      await loadFolders();
      message.success('资料夹已删除');
    } catch (error) {
      message.error(error.response?.data?.detail || '请先处理子资料夹或其中的研究');
    }
  };

  const handleDragStart = (event, document) => {
    setDraggedFolderId(null);
    setDraggedDocumentId(document.id);
    setDropTarget(null);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(document.id));
  };

  const handleFolderDragStart = (event, folder) => {
    setDraggedDocumentId(null);
    setDraggedFolderId(folder.id);
    setDropTarget(null);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', `folder:${folder.id}`);
  };

  const handleDragEnd = () => {
    setDraggedDocumentId(null);
    setDraggedFolderId(null);
    setDropTarget(null);
  };

  const handleDragOverFolder = (event, folder) => {
    if (!draggedDocumentId && !draggedFolderId) return;
    if (draggedFolderId === folder.id) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'move';
    if (draggedDocumentId) {
      setDropTarget({ type: 'folder', id: folder.id, placement: 'inside' });
      return;
    }
    const bounds = event.currentTarget.getBoundingClientRect();
    const position = (event.clientY - bounds.top) / bounds.height;
    const placement = position < 0.28 ? 'before' : position > 0.72 ? 'after' : 'inside';
    setDropTarget({ type: 'folder', id: folder.id, placement });
  };

  const handleDragOverDocument = (event, document) => {
    if (!draggedDocumentId || draggedDocumentId === document.id) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = 'move';
    const bounds = event.currentTarget.getBoundingClientRect();
    const placement = event.clientY < bounds.top + bounds.height / 2 ? 'before' : 'after';
    setDropTarget({ type: 'document', id: document.id, placement });
  };

  const submitDragMove = async (targetFolderId, targetDocumentId = null, placement = 'end') => {
    if (!draggedDocumentId) return;
    try {
      const moved = (await researchApi.documents.reorder({
        document_id: draggedDocumentId,
        target_folder_id: targetFolderId,
        target_document_id: targetDocumentId,
        placement,
      })).data;
      if (selectedIdRef.current === moved.id) setSelectedDocument(moved);
      setExpanded((current) => ({ ...current, [targetFolderId]: true }));
      await Promise.all([loadFolders(), loadDocuments('active', '', moved.id)]);
      message.success('研究位置已更新');
    } catch (error) {
      message.error(error.response?.data?.detail || '移动失败');
    } finally {
      handleDragEnd();
    }
  };

  const submitFolderDragMove = async (targetFolder, placement) => {
    if (!draggedFolderId) return;
    const movingInside = placement === 'inside';
    try {
      const moved = (await researchApi.folders.reorder({
        folder_id: draggedFolderId,
        target_parent_id: movingInside ? targetFolder.id : (targetFolder.parent_id || null),
        target_folder_id: movingInside ? null : targetFolder.id,
        placement: movingInside ? 'end' : placement,
      })).data;
      await loadFolders();
      setExpanded((current) => ({
        ...current,
        [moved.id]: true,
        ...(moved.parent_id ? { [moved.parent_id]: true } : {}),
      }));
      message.success('资料夹位置已更新');
    } catch (error) {
      message.error(error.response?.data?.detail || '资料夹移动失败');
    } finally {
      handleDragEnd();
    }
  };

  const handleDropOnFolder = (event, folder) => {
    event.preventDefault();
    event.stopPropagation();
    if (draggedFolderId) {
      submitFolderDragMove(folder, dropTarget?.id === folder.id ? dropTarget.placement : 'inside');
    } else {
      submitDragMove(folder.id);
    }
  };

  const handleDropOnDocument = (event, document) => {
    event.preventDefault();
    event.stopPropagation();
    if (!draggedDocumentId || draggedDocumentId === document.id) {
      handleDragEnd();
      return;
    }
    const bounds = event.currentTarget.getBoundingClientRect();
    const placement = event.clientY < bounds.top + bounds.height / 2 ? 'before' : 'after';
    submitDragMove(document.folder_id, document.id, placement);
  };

  const openDocumentById = async (documentId) => {
    selectionRevisionRef.current += 1;
    setMode('active');
    setEditing(false);
    setIsNew(false);
    updateSelectedId(documentId);
    const target = (await researchApi.documents.get(documentId)).data;
    const path = {};
    let folder = folders.find((item) => item.id === target.folder_id);
    while (folder) {
      path[folder.id] = true;
      folder = folders.find((item) => item.id === folder.parent_id);
    }
    setExpanded((current) => ({ ...current, ...path }));
  };

  const openWikiLink = async (name) => {
    try {
      const target = (await researchApi.documents.resolveLink(name)).data;
      await openDocumentById(target.document_id);
    } catch {
      message.warning(`未找到关联研究：${name}`);
    }
  };

  const loadTradeDrawer = async (tradeId) => {
    const requestId = ++tradeDrawerRequestRef.current;
    setTradeDrawer((current) => ({ ...current, open: true, tradeId, loading: true }));
    try {
      const [tradeResult, reviewResult, linkedPlansResult, riskPointHistoryResult, linkedResearchResult] = await Promise.all([
        tradeApi.get(tradeId),
        tradeReviewApi.get(tradeId).catch((error) => (error.response?.status === 404 ? { data: null } : Promise.reject(error))),
        tradeLinkedPlanApi.get(tradeId).catch(() => ({ data: [] })),
        tradeApi.riskPointHistory(tradeId).catch(() => ({ data: [] })),
        researchApi.documents.forTrade(tradeId).catch(() => ({ data: [] })),
      ]);
      if (requestId !== tradeDrawerRequestRef.current) return;
      setTradeDrawer({
        open: true,
        tradeId,
        loading: false,
        trade: tradeResult.data || null,
        riskPointHistory: Array.isArray(riskPointHistoryResult.data) ? riskPointHistoryResult.data : [],
        review: reviewResult.data || null,
        linkedPlans: Array.isArray(linkedPlansResult.data) ? linkedPlansResult.data : [],
        linkedResearch: Array.isArray(linkedResearchResult.data) ? linkedResearchResult.data : [],
      });
    } catch (error) {
      if (requestId !== tradeDrawerRequestRef.current) return;
      setTradeDrawer((current) => ({ ...current, loading: false, trade: null }));
      message.error(error.response?.data?.detail || '交易详情加载失败');
    }
  };

  const restoreDocument = async () => {
    const restored = (await researchApi.recycle.restore(selectedDocument.id)).data;
    message.success('研究已恢复');
    await Promise.all([loadFolders(), loadDocuments('recycle', '')]);
    setExpanded((current) => ({ ...current, [restored.folder_id]: true }));
  };

  const purgeDocument = async () => {
    await researchApi.recycle.purge(selectedDocument.id);
    message.success('研究已彻底删除');
    await loadDocuments('recycle', '');
  };

  const clearRecycle = async () => {
    await researchApi.recycle.clear();
    setSelectedDocument(null);
    updateSelectedId(null);
    message.success('研究回收站已清空');
    await loadDocuments('recycle', '');
  };

  const wikiLinks = extractWikiLinks(selectedDocument?.content);
  const readHtml = selectedDocument ? sanitizeResearchHtml(renderResearchContent(selectedDocument.content || '')) : '';
  const openReaderImage = (event) => {
    if (event.target.tagName === 'IMG') {
      setLightboxImage({ src: event.target.src, alt: event.target.alt || '' });
    }
  };

  return (
    <div className="research-page">
      <div className="research-workspace">
        <aside className="research-side-panel">
          <div className="research-side-mode">
            <Segmented
              block
              value={mode}
              onChange={changeMode}
              options={[{ label: '研究资料', value: 'active' }, { label: '回收站', value: 'recycle' }]}
            />
          </div>
          {mode === 'active' ? (
            <>
              <div className="research-side-search">
                <Input allowClear size="small" prefix={<SearchOutlined />} value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索研究资料..." />
              </div>
              <div className="research-side-summary">📋 全部研究 <span>{documents.length}</span></div>
              <div className="research-side-create">
                <Button type="primary" icon={<FileAddOutlined />} onClick={() => startNew()}>新建研究</Button>
                <Button icon={<FolderAddOutlined />} onClick={() => openFolderModal()}>新建资料夹</Button>
              </div>
              <Spin spinning={loading} wrapperClassName="research-tree-spin">
                <div className="research-folder-tree">
                  {keyword.trim() ? documents.map((document) => (
                    <div key={document.id} className={`research-search-result${selectedId === document.id ? ' active' : ''}`} onClick={() => selectDocument(document.id)}>
                      <strong>{document.title}</strong>
                      <span>{document.word_count || 0} 字 · {backendTimeInChina(document.updated_at).format('MM-DD HH:mm')}</span>
                    </div>
                  )) : roots.map((folder) => (
                    <ResearchTreeNode
                      key={folder.id}
                      folder={folder}
                      folders={folders}
                      documentsByFolder={documentsByFolder}
                      expanded={expanded}
                      activeId={selectedId}
                      onToggle={(id) => setExpanded((current) => ({ ...current, [id]: !current[id] }))}
                      onSelect={selectDocument}
                      onCreate={startNew}
                      onEditFolder={openFolderModal}
                      onDeleteFolder={deleteFolder}
                      onDeleteDocument={deleteDocument}
                      draggedDocumentId={draggedDocumentId}
                      draggedFolderId={draggedFolderId}
                      dropTarget={dropTarget}
                      onDragStart={handleDragStart}
                      onFolderDragStart={handleFolderDragStart}
                      onDragEnd={handleDragEnd}
                      onDragOverFolder={handleDragOverFolder}
                      onDropOnFolder={handleDropOnFolder}
                      onDragOverDocument={handleDragOverDocument}
                      onDropOnDocument={handleDropOnDocument}
                    />
                  ))}
                </div>
              </Spin>
            </>
          ) : (
            <>
              <div className="research-side-summary">🗑 已删除研究 <span>{documents.length}</span></div>
              <div className="research-recycle-list">
                {documents.map((document) => (
                  <button type="button" key={document.id} className={selectedId === document.id ? 'active' : ''} onClick={() => selectDocument(document.id)}>
                    <strong>{document.title}</strong>
                    <span>{dayjs(document.deleted_at).format('YYYY-MM-DD HH:mm')}</span>
                  </button>
                ))}
                {!loading && !documents.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="回收站为空" /> : null}
              </div>
              <div className="research-side-footer">
                <Popconfirm title="确认清空研究回收站？此操作无法恢复。" onConfirm={clearRecycle}>
                  <Button block danger disabled={!documents.length}>清空回收站</Button>
                </Popconfirm>
              </div>
            </>
          )}
        </aside>

        <main className="research-main-content">
          {editing ? (
            <div className="research-editor-panel">
              <div className="research-editor-header">
                <div className="research-editor-actions">
                  <div />
                  <Space>
                    <Button onClick={() => { setEditing(false); setIsNew(false); }}>取消</Button>
                    <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={saveDocument}>保存</Button>
                  </Space>
                </div>
                <Input className="research-editor-title" variant="borderless" value={draft.title} onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} placeholder="输入研究标题..." />
                <div className="research-editor-fields">
                  <Select value={draft.folder_id} onChange={(value) => setDraft((current) => ({ ...current, folder_id: value }))} options={folderOptions} placeholder="选择资料夹" />
                  <Select mode="tags" value={draft.tags} onChange={(value) => setDraft((current) => ({ ...current, tags: value }))} placeholder="输入标签后回车" />
                  <Select
                    className="research-trade-selector"
                    mode="multiple"
                    allowClear
                    showSearch
                    filterOption={false}
                    loading={tradeOptionsLoading}
                    value={draft.trade_ids}
                    onSearch={setTradeSearch}
                    onChange={(value) => setDraft((current) => ({ ...current, trade_ids: value }))}
                    options={tradeOptions.map((trade) => ({ value: trade.trade_id, label: tradeReferenceLabel(trade) }))}
                    placeholder="搜索并引用交易记录（支持多选）"
                    notFoundContent={tradeOptionsLoading ? <Spin size="small" /> : '没有匹配的交易'}
                  />
                </div>
              </div>
              <ResearchEditor key={isNew ? 'new' : selectedDocument?.id} content={draft.content} onChange={(content) => setDraft((current) => ({ ...current, content }))} />
            </div>
          ) : selectedDocument ? (
            <div className="research-reader-panel">
              <div className="research-reader-header">
                <div className="research-reader-actions">
                  <div className="research-reader-meta">最后编辑：{backendTimeInChina(selectedDocument.updated_at).format('YYYY-MM-DD HH:mm')} · {selectedDocument.word_count || 0} 字</div>
                  {mode === 'active' ? (
                    <Space>
                      <Tooltip title={selectedDocument.is_pinned ? '取消置顶' : '置顶'}><Button icon={selectedDocument.is_pinned ? <PushpinFilled /> : <PushpinOutlined />} onClick={togglePinned} /></Tooltip>
                      <Button icon={<EditOutlined />} onClick={startEdit}>编辑</Button>
                      <Popconfirm title="确认移入研究回收站？" onConfirm={() => deleteDocument(selectedDocument.id)}><Button danger icon={<DeleteOutlined />}>删除</Button></Popconfirm>
                    </Space>
                  ) : (
                    <Space>
                      <Button type="primary" onClick={restoreDocument}>恢复</Button>
                      <Popconfirm title="彻底删除后无法恢复，确认继续？" onConfirm={purgeDocument}><Button danger>彻底删除</Button></Popconfirm>
                    </Space>
                  )}
                </div>
                <h1>{selectedDocument.title}</h1>
                {(selectedDocument.tags || []).length ? <div className="research-reader-tags">{selectedDocument.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}</div> : null}
              </div>
              {mode === 'active' && selectedDocument.related_trades?.length ? (
                <div className="research-pinned-trades">
                  <strong>引用的交易</strong>
                  <div className="research-trade-reference-list">
                    {selectedDocument.related_trades.map((trade) => (
                      <div className="research-trade-reference" key={trade.trade_id}>
                        <span>{tradeReferenceLabel(trade)}</span>
                        <Button type="link" size="small" onClick={() => loadTradeDrawer(trade.trade_id)}>查看交易</Button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              <article className="research-reader-content tiptap" onClick={openReaderImage} dangerouslySetInnerHTML={{ __html: readHtml }} />
              {mode === 'active' && (wikiLinks.length || backlinks.length) ? (
                <div className="research-relations">
                  {wikiLinks.length ? <div><strong>引用的研究</strong><Space wrap>{wikiLinks.map((name) => <Button key={name} type="link" size="small" icon={<LinkOutlined />} onClick={() => openWikiLink(name)}>{name}</Button>)}</Space></div> : null}
                  {backlinks.length ? <div><strong>反向链接</strong><Space wrap>{backlinks.map((item) => <Button key={item.document_id} type="link" size="small" onClick={() => openDocumentById(item.document_id)}>{item.title}</Button>)}</Space></div> : null}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="research-empty"><Empty description={mode === 'recycle' ? '回收站为空' : '选择研究资料，或新建研究'} /></div>
          )}
        </main>
      </div>

      {lightboxImage ? <ImageLightbox {...lightboxImage} onClose={() => setLightboxImage(null)} /> : null}

      <TradeDetailDrawer
        open={tradeDrawer.open}
        tradeId={tradeDrawer.tradeId}
        loading={tradeDrawer.loading}
        trade={tradeDrawer.trade}
        riskPointHistory={tradeDrawer.riskPointHistory}
        review={tradeDrawer.review}
        reviewExists={Boolean(tradeDrawer.review)}
        linkedPlans={tradeDrawer.linkedPlans}
        linkedResearch={tradeDrawer.linkedResearch}
        onClose={() => setTradeDrawer((current) => ({ ...current, open: false }))}
        onReload={() => tradeDrawer.tradeId && loadTradeDrawer(tradeDrawer.tradeId)}
      />

      <Modal title={folderModal.id ? '编辑资料夹' : '新建资料夹'} open={folderModal.open} onOk={saveFolder} onCancel={() => setFolderModal({ open: false, id: null, name: '', parent_id: null })} okText="保存" cancelText="取消">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Input autoFocus value={folderModal.name} onChange={(event) => setFolderModal((current) => ({ ...current, name: event.target.value }))} onPressEnter={saveFolder} placeholder="资料夹名称" />
          <Select allowClear value={folderModal.parent_id} onChange={(value) => setFolderModal((current) => ({ ...current, parent_id: value || null }))} options={folderOptions.filter((item) => item.value !== folderModal.id)} placeholder="上级资料夹（可选）" style={{ width: '100%' }} />
        </Space>
      </Modal>
    </div>
  );
}
