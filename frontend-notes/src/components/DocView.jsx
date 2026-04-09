import { useState, useEffect, useCallback, useRef } from 'react';
import { Input, Modal, Popconfirm, Select, message } from 'antd';
import { SearchOutlined, PlusOutlined, DeleteOutlined, FolderOutlined, FolderAddOutlined, FileTextOutlined, FileAddOutlined, CopyOutlined, SwapOutlined } from '@ant-design/icons';
import { noteApi, notebookApi } from '../api';
import NoteEditor from './NoteEditor';

function FolderNode({ nb, allNotebooks, notesByNb, activeNote, expandedFolders, onToggle, onSelectNote, onDeleteNote, onDeleteFolder, onCreateDoc, onCreateSubfolder, onCopyNote, onMoveNote }) {
  const children = allNotebooks.filter(c => c.parent_id === nb.id);
  const notes = notesByNb[nb.id] || [];
  const isExpanded = expandedFolders[nb.id];

  return (
    <div>
      <div
        className={`tree-folder`}
        onClick={() => onToggle(nb.id)}
      >
        <span>
          {(children.length > 0 || notes.length > 0) ? (isExpanded ? '▾' : '▸') : '　'}
          {' '}<FolderOutlined /> {nb.icon} {nb.name}
        </span>
        <span className="tree-folder-actions" onClick={e => e.stopPropagation()}>
          <FileAddOutlined
            className="tree-action-icon"
            title="新建文档"
            onClick={() => onCreateDoc(nb.id)}
          />
          <FolderAddOutlined
            className="tree-action-icon"
            title="新建子文件夹"
            onClick={() => onCreateSubfolder(nb.id)}
          />
          <Popconfirm
            title="删除文件夹及其所有内容？"
            onConfirm={() => onDeleteFolder(nb.id)}
          >
            <DeleteOutlined className="tree-action-icon danger" />
          </Popconfirm>
        </span>
      </div>
      {isExpanded && (
        <div className="tree-children">
          {children.map(child => (
            <FolderNode
              key={child.id}
              nb={child}
              allNotebooks={allNotebooks}
              notesByNb={notesByNb}
              activeNote={activeNote}
              expandedFolders={expandedFolders}
              onToggle={onToggle}
              onSelectNote={onSelectNote}
              onDeleteNote={onDeleteNote}
              onDeleteFolder={onDeleteFolder}
              onCreateDoc={onCreateDoc}
              onCreateSubfolder={onCreateSubfolder}
              onCopyNote={onCopyNote}
              onMoveNote={onMoveNote}
            />
          ))}
          {notes.map(note => (
            <div
              key={note.id}
              className={`tree-file ${activeNote?.id === note.id ? 'active' : ''}`}
              onClick={() => onSelectNote(note)}
            >
              <span><FileTextOutlined /> {note.title || '无标题'}</span>
              <span className="tree-file-actions" onClick={e => e.stopPropagation()}>
                <CopyOutlined
                  className="tree-action-icon"
                  title="复制到其他文件夹"
                  onClick={() => onCopyNote(note)}
                />
                <SwapOutlined
                  className="tree-action-icon"
                  title="移动到其他文件夹"
                  onClick={() => onMoveNote(note)}
                />
                <Popconfirm
                  title="确定删除？"
                  onConfirm={(e) => { e?.stopPropagation(); onDeleteNote(note.id); }}
                >
                  <DeleteOutlined
                    className="tree-action-icon danger"
                    onClick={e => e.stopPropagation()}
                  />
                </Popconfirm>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DocView({ initialNoteId, initialAnchor, notebooks, onReloadNotebooks }) {
  const HISTORY_KEY = 'notes-doc-search-history';
  const [notes, setNotes] = useState([]);
  const [activeNote, setActiveNote] = useState(null);
  const [keyword, setKeyword] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchHistory, setSearchHistory] = useState(() => {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr.slice(0, 3) : [];
    } catch {
      return [];
    }
  });
  const [addOpen, setAddOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [parentForNewFolder, setParentForNewFolder] = useState(null);
  const [expandedFolders, setExpandedFolders] = useState({});
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferMode, setTransferMode] = useState('copy');
  const [transferNote, setTransferNote] = useState(null);
  const [transferTargetNb, setTransferTargetNb] = useState(null);
  const [backlinks, setBacklinks] = useState([]);
  const [backlinksCollapsed, setBacklinksCollapsed] = useState(true);
  const [backlinksWidth, setBacklinksWidth] = useState(280);
  const [jumpAnchor, setJumpAnchor] = useState(initialAnchor || '');
  const resizingRef = useRef(false);
  const saveTimer = useRef(null);
  const createdFromEntryRef = useRef(false);

  useEffect(() => {
    const onMove = (e) => {
      if (!resizingRef.current) return;
      const panelMin = 220;
      const panelMax = 520;
      const next = Math.max(panelMin, Math.min(panelMax, window.innerWidth - e.clientX));
      setBacklinksWidth(next);
    };
    const onUp = () => { resizingRef.current = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  const loadNotes = useCallback(async () => {
    const params = { note_type: 'doc' };
    if (keyword) params.keyword = keyword;
    try {
      const res = await noteApi.list(params);
      setNotes(res.data);
    } catch {}
  }, [keyword]);

  useEffect(() => { loadNotes(); }, [loadNotes]);

  useEffect(() => {
    const kw = keyword.trim();
    if (!kw) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }
    const t = setTimeout(async () => {
      try {
        setSearchLoading(true);
        const res = await noteApi.search({ q: kw, note_type: 'doc', limit: 80 });
        setSearchResults(res.data || []);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [keyword]);

  useEffect(() => {
    if (typeof initialNoteId === 'string' && initialNoteId.startsWith('new:')) {
      if (!createdFromEntryRef.current) {
        createdFromEntryRef.current = true;
        handleCreateDoc();
      }
      return;
    }
    if (initialNoteId && typeof initialNoteId === 'number') {
      createdFromEntryRef.current = false;
      noteApi.get(initialNoteId).then(r => setActiveNote(r.data)).catch(() => {});
    }
  }, [initialNoteId]);

  useEffect(() => {
    setJumpAnchor(initialAnchor || '');
  }, [initialAnchor, initialNoteId]);

  useEffect(() => {
    const id = activeNote?.id;
    if (!id) {
      setBacklinks([]);
      return;
    }
    noteApi.backlinks(id, { limit: 100 }).then(r => setBacklinks(r.data || [])).catch(() => setBacklinks([]));
  }, [activeNote?.id]);

  const handleCreateDoc = async (nbId) => {
    const targetNb = nbId || notebooks.find(n => !n.parent_id)?.id;
    if (!targetNb) { message.warning('请先创建文件夹'); return; }
    try {
      const res = await noteApi.create({
        notebook_id: targetNb,
        title: '无标题',
        content: '',
        note_type: 'doc',
      });
      setActiveNote({ ...res.data, _justCreated: true });
      setExpandedFolders(prev => ({ ...prev, [targetNb]: true }));
      loadNotes();
    } catch { message.error('创建失败'); }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      await notebookApi.create({
        name: newFolderName.trim(),
        icon: '📁',
        parent_id: parentForNewFolder || null,
      });
      setNewFolderName('');
      setAddOpen(false);
      setParentForNewFolder(null);
      onReloadNotebooks();
    } catch (e) { message.error(e.response?.data?.detail || '创建失败'); }
  };

  const openCreateSubfolder = (parentId) => {
    setParentForNewFolder(parentId);
    setAddOpen(true);
  };

  const openCreateRootFolder = () => {
    setParentForNewFolder(null);
    setAddOpen(true);
  };

  const handleUpdateNote = useCallback(async (id, updates) => {
    const { _flush, ...data } = updates;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    if (_flush) {
      try { await noteApi.update(id, data); } catch {}
      return;
    }
    saveTimer.current = setTimeout(async () => {
      try {
        const res = await noteApi.update(id, data);
        setActiveNote((prev) => {
          if (!prev || prev.id !== res.data.id) return res.data;
          return { ...res.data, _justCreated: prev._justCreated === true };
        });
        loadNotes();
      } catch {}
    }, 800);
  }, [loadNotes]);

  const handleDeleteNote = async (id) => {
    try {
      await noteApi.delete(id);
      if (activeNote?.id === id) setActiveNote(null);
      loadNotes();
      message.success('已移入回收站');
    } catch { message.error('删除失败'); }
  };

  const handleDeleteFolder = async (nbId) => {
    try {
      await notebookApi.delete(nbId);
      onReloadNotebooks();
      loadNotes();
      message.success('已删除');
    } catch { message.error('删除失败'); }
  };

  const saveHistory = (list) => {
    setSearchHistory(list);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(list)); } catch {}
  };

  const pushHistory = (term) => {
    const t = String(term || '').trim();
    if (!t) return;
    const next = [t, ...searchHistory.filter(x => x !== t)].slice(0, 3);
    saveHistory(next);
  };

  const removeHistory = (term) => {
    saveHistory(searchHistory.filter(x => x !== term));
  };

  const expandNotebookPath = (nbId) => {
    const map = new Map(notebooks.map(n => [n.id, n]));
    const next = {};
    let cur = nbId;
    while (cur && map.has(cur)) {
      next[cur] = true;
      cur = map.get(cur).parent_id;
    }
    setExpandedFolders(prev => ({ ...prev, ...next }));
  };

  const openSearchResult = async (item) => {
    if (!item) return;
    pushHistory(keyword);
    expandNotebookPath(item.notebook_id);
    try {
      const res = await noteApi.get(item.id);
      setActiveNote(res.data);
      setJumpAnchor('');
    } catch {}
  };

  const handleOpenWikiLink = async (raw) => {
    const text = String(raw || '').trim();
    if (!text) return;
    const name = text.split('#')[0].trim();
    if (!name) return;
    try {
      const res = await noteApi.resolveLink(name);
      const row = res.data?.matches?.[0];
      if (!row) {
        message.warning(`未找到文档：${name}`);
        return;
      }
      expandNotebookPath(row.notebook_id);
      const noteRes = await noteApi.get(row.id);
      setActiveNote(noteRes.data);
      setJumpAnchor('');
    } catch {
      message.error('链接跳转失败');
    }
  };

  const renderHighlighted = (text, kw) => {
    const source = String(text || '');
    const key = String(kw || '').trim();
    if (!key) return source;
    const low = source.toLowerCase();
    const k = key.toLowerCase();
    const parts = [];
    let i = 0;
    while (i < source.length) {
      const idx = low.indexOf(k, i);
      if (idx < 0) {
        parts.push(source.slice(i));
        break;
      }
      if (idx > i) parts.push(source.slice(i, idx));
      parts.push(<mark key={`${idx}-${k}`}>{source.slice(idx, idx + key.length)}</mark>);
      i = idx + key.length;
    }
    return parts;
  };

  const toggleFolder = (nbId) => {
    setExpandedFolders(prev => ({ ...prev, [nbId]: !prev[nbId] }));
  };

  const openTransfer = (note, mode) => {
    setTransferNote(note);
    setTransferMode(mode);
    setTransferTargetNb(note.notebook_id);
    setTransferOpen(true);
  };

  const handleSubmitTransfer = async () => {
    if (!transferNote || !transferTargetNb) { message.warning('请选择目标文件夹'); return; }
    try {
      if (transferMode === 'copy') {
        const created = await noteApi.create({
          notebook_id: transferTargetNb,
          title: transferNote.title || '无标题',
          content: transferNote.content || '',
          note_type: 'doc',
          word_count: transferNote.word_count || 0,
        });
        setActiveNote(created.data);
        message.success('复制成功');
      } else {
        const updated = await noteApi.update(transferNote.id, {
          notebook_id: transferTargetNb,
        });
        if (activeNote?.id === transferNote.id) setActiveNote(updated.data);
        message.success('移动成功');
      }
      setTransferOpen(false);
      setTransferNote(null);
      loadNotes();
    } catch (e) {
      message.error(e.response?.data?.detail || '操作失败');
    }
  };

  const notesByNb = {};
  for (const note of notes) {
    if (!notesByNb[note.notebook_id]) notesByNb[note.notebook_id] = [];
    notesByNb[note.notebook_id].push(note);
  }

  const rootNotebooks = notebooks.filter(nb => !nb.parent_id);
  const buildNotebookOptions = (parentId = null, depth = 0) => {
    const children = notebooks.filter(n => (n.parent_id || null) === parentId);
    return children.flatMap((n) => ([
      { value: n.id, label: `${'  '.repeat(depth)}${n.icon || '📁'} ${n.name}` },
      ...buildNotebookOptions(n.id, depth + 1),
    ]));
  };
  const notebookOptions = buildNotebookOptions();

  return (
    <div className="view-container">
      <div className="side-panel">
        <div className="side-search">
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索文档..."
            size="small"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onPressEnter={() => {
              if (keyword.trim() && searchResults[0]) openSearchResult(searchResults[0]);
            }}
            allowClear
          />
        </div>
        {!keyword.trim() && searchHistory.length > 0 && (
          <div className="search-history">
            {searchHistory.map(item => (
              <div key={item} className="search-history-item">
                <button className="search-history-text" onClick={() => setKeyword(item)}>{item}</button>
                <button className="search-history-del" onClick={() => removeHistory(item)}>×</button>
              </div>
            ))}
          </div>
        )}

        <div className="side-tags">
          <div className="side-tags-header">标签：</div>
          <div className="tag-item active">
            📋 全部文档 <span className="tag-count">({notes.length})</span>
          </div>
        </div>

        <div className="doc-actions">
          <button className="action-btn" onClick={() => handleCreateDoc()}>
            <PlusOutlined /> 新建文档
          </button>
        </div>

        <div className="folder-tree">
          {keyword.trim() ? (
            <div className="search-result-list">
              {searchLoading ? (
                <div className="empty-hint">搜索中...</div>
              ) : searchResults.length ? (
                searchResults.map(item => (
                  <div
                    key={item.id}
                    className="search-result-item"
                    onClick={() => openSearchResult(item)}
                  >
                    <div className="search-result-title">{renderHighlighted(item.title, keyword)}</div>
                    <div className="search-result-snippet">{renderHighlighted(item.snippet, keyword)}</div>
                  </div>
                ))
              ) : (
                <div className="empty-hint">无匹配结果</div>
              )}
            </div>
          ) : rootNotebooks.map(nb => (
            <FolderNode
              key={nb.id}
              nb={nb}
              allNotebooks={notebooks}
              notesByNb={notesByNb}
              activeNote={activeNote}
              expandedFolders={expandedFolders}
              onToggle={toggleFolder}
              onSelectNote={setActiveNote}
              onDeleteNote={handleDeleteNote}
              onDeleteFolder={handleDeleteFolder}
              onCreateDoc={handleCreateDoc}
              onCreateSubfolder={openCreateSubfolder}
              onCopyNote={(note) => openTransfer(note, 'copy')}
              onMoveNote={(note) => openTransfer(note, 'move')}
            />
          ))}

          {!keyword.trim() && (
            <div className="tree-folder add-folder" onClick={openCreateRootFolder}>
              <PlusOutlined /> 新建文件夹
            </div>
          )}
        </div>
      </div>

      <div className="main-content">
        {activeNote ? (
          <div className="doc-main-split">
            <div className="doc-main-editor">
              <NoteEditor
                note={activeNote}
                onUpdate={handleUpdateNote}
                onOpenWikiLink={handleOpenWikiLink}
                jumpAnchor={jumpAnchor}
                defaultEditing={activeNote?._justCreated === true}
              />
            </div>
            {!backlinksCollapsed && (
              <div
                className="doc-backlinks-resizer"
                onMouseDown={() => { resizingRef.current = true; }}
                title="拖动调整宽度"
              />
            )}
            <div
              className={`doc-backlinks ${backlinksCollapsed ? 'collapsed' : ''}`}
              style={backlinksCollapsed ? undefined : { width: backlinksWidth, minWidth: backlinksWidth }}
            >
              <button
                className="doc-backlinks-toggle"
                onClick={() => setBacklinksCollapsed(v => !v)}
                title={backlinksCollapsed ? '展开反向链接' : '折叠反向链接'}
              >
                {backlinksCollapsed ? '◀ 反向链接' : '▶ 折叠'}
              </button>
              {!backlinksCollapsed && (
                <>
                  <div className="doc-backlinks-title">反向链接</div>
                  {backlinks.length ? backlinks.map((b, idx) => (
                    <div
                      key={`${b.source_note_id}-${idx}`}
                      className="doc-backlink-item"
                      onClick={async () => {
                        try {
                          const res = await noteApi.get(b.source_note_id);
                          expandNotebookPath(res.data.notebook_id);
                          setActiveNote(res.data);
                        } catch {}
                      }}
                    >
                      <div className="doc-backlink-name">{b.source_title || '无标题'}</div>
                      <div className="doc-backlink-snippet">{b.snippet || ''}</div>
                    </div>
                  )) : (
                    <div className="doc-backlink-empty">暂无文档引用此篇</div>
                  )}
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="empty-editor">
            <div className="empty-icon">📄</div>
            <div>选择文档或点击「新建文档」开始写作</div>
          </div>
        )}
      </div>

      <Modal
        title={parentForNewFolder ? '新建子文件夹' : '新建文件夹'}
        open={addOpen}
        onOk={handleCreateFolder}
        onCancel={() => { setAddOpen(false); setParentForNewFolder(null); }}
        okText="创建"
        cancelText="取消"
      >
        <Input
          placeholder="文件夹名称"
          value={newFolderName}
          onChange={e => setNewFolderName(e.target.value)}
          onPressEnter={handleCreateFolder}
        />
      </Modal>

      <Modal
        title={transferMode === 'copy' ? '复制文档到文件夹' : '移动文档到文件夹'}
        open={transferOpen}
        onOk={handleSubmitTransfer}
        onCancel={() => { setTransferOpen(false); setTransferNote(null); }}
        okText={transferMode === 'copy' ? '复制' : '移动'}
        cancelText="取消"
      >
        <div style={{ marginBottom: 10, color: '#666', fontSize: 13 }}>
          文档：{transferNote?.title || '无标题'}
        </div>
        <Select
          style={{ width: '100%' }}
          placeholder="请选择目标文件夹"
          value={transferTargetNb}
          onChange={setTransferTargetNb}
          options={notebookOptions}
        />
      </Modal>
    </div>
  );
}
