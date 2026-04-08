import { useState, useEffect, useCallback, useRef } from 'react';
import { Input, Modal, Popconfirm, Select, message } from 'antd';
import { SearchOutlined, PlusOutlined, DeleteOutlined, FolderOutlined, FolderAddOutlined, FileTextOutlined, FileAddOutlined, CopyOutlined, SwapOutlined } from '@ant-design/icons';
import { noteApi, notebookApi } from '../api';
import NoteEditor from './NoteEditor';
import dayjs from 'dayjs';

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

export default function DocView({ initialNoteId, notebooks, onReloadNotebooks }) {
  const [notes, setNotes] = useState([]);
  const [activeNote, setActiveNote] = useState(null);
  const [keyword, setKeyword] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [parentForNewFolder, setParentForNewFolder] = useState(null);
  const [expandedFolders, setExpandedFolders] = useState({});
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferMode, setTransferMode] = useState('copy');
  const [transferNote, setTransferNote] = useState(null);
  const [transferTargetNb, setTransferTargetNb] = useState(null);
  const saveTimer = useRef(null);

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
    if (initialNoteId && typeof initialNoteId === 'number') {
      noteApi.get(initialNoteId).then(r => setActiveNote(r.data)).catch(() => {});
    }
  }, [initialNoteId]);

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
      setActiveNote(res.data);
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
        setActiveNote(res.data);
        loadNotes();
      } catch {}
    }, 800);
  }, [loadNotes]);

  const handleDeleteNote = async (id) => {
    try {
      await noteApi.delete(id);
      if (activeNote?.id === id) setActiveNote(null);
      loadNotes();
      message.success('已删除');
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
            allowClear
          />
        </div>

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
          {rootNotebooks.map(nb => (
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

          <div className="tree-folder add-folder" onClick={openCreateRootFolder}>
            <PlusOutlined /> 新建文件夹
          </div>
        </div>
      </div>

      <div className="main-content">
        {activeNote ? (
          <NoteEditor
            note={activeNote}
            onUpdate={handleUpdateNote}
            defaultEditing={dayjs(activeNote.created_at).format('YYYY-MM-DD') === dayjs().format('YYYY-MM-DD')}
          />
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
