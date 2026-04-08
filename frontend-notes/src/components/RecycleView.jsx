import { useEffect, useState } from 'react';
import { Popconfirm, message } from 'antd';
import dayjs from 'dayjs';
import { noteApi } from '../api';

export default function RecycleView({ onNavigate }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState('all');

  const load = async () => {
    try {
      const params = filter === 'all' ? {} : { note_type: filter };
      const res = await noteApi.recycleList(params);
      setItems(res.data || []);
    } catch {
      message.error('加载回收站失败');
    }
  };

  useEffect(() => {
    load();
  }, [filter]);

  const restore = async (id) => {
    try {
      await noteApi.restore(id);
      message.success('已还原');
      load();
    } catch {
      message.error('还原失败');
    }
  };

  const restoreAndOpen = async (note) => {
    try {
      await noteApi.restore(note.id);
      message.success('已还原');
      onNavigate(note.note_type === 'diary' ? 'diary' : 'doc', note.id);
    } catch {
      message.error('还原失败');
    }
  };

  const purge = async (id) => {
    try {
      await noteApi.purge(id);
      message.success('已彻底删除');
      load();
    } catch {
      message.error('删除失败');
    }
  };

  return (
    <div className="view-container">
      <div className="side-panel">
        <div className="side-tags">
          <div className="side-tags-header">筛选：</div>
          <div className={`tag-item ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>全部</div>
          <div className={`tag-item ${filter === 'diary' ? 'active' : ''}`} onClick={() => setFilter('diary')}>日记</div>
          <div className={`tag-item ${filter === 'doc' ? 'active' : ''}`} onClick={() => setFilter('doc')}>文档</div>
        </div>
      </div>

      <div className="main-content">
        <div className="todo-view-main">
          <div className="todo-view-title">回收站</div>
          <div className="todo-list">
            {items.length > 0 ? items.map((n) => (
              <div key={n.id} className="todo-item">
                <div className="todo-row" style={{ justifyContent: 'space-between' }}>
                  <span>
                    {n.note_type === 'diary' ? '📔' : '📄'} {n.title || '无标题'}
                  </span>
                  <span className="todo-time">删除于 {n.deleted_at ? dayjs(n.deleted_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</span>
                </div>
                <div className="todo-row todo-meta">
                  {n.note_date && <span>日期：{n.note_date}</span>}
                  <button className="todo-bulk-btn" onClick={() => restoreAndOpen(n)}>还原并打开</button>
                  <button className="todo-bulk-btn" onClick={() => restore(n.id)}>仅还原</button>
                  <Popconfirm title="彻底删除后无法恢复，确认继续？" onConfirm={() => purge(n.id)}>
                    <button className="todo-del-btn">彻底删除</button>
                  </Popconfirm>
                </div>
              </div>
            )) : <div className="empty-hint">回收站为空</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
