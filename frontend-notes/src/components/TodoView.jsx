import { useEffect, useMemo, useRef, useState } from 'react';
import { DatePicker, message } from 'antd';
import dayjs from 'dayjs';
import { noteApi, todoApi } from '../api';

const REMINDER_KEY = 'todo-reminded-ids';

function toBackendDatetime(v) {
  if (!v) return null;
  const d = dayjs(v);
  return d.isValid() ? d.format('YYYY-MM-DDTHH:mm:ss') : null;
}

export default function TodoView({ onNavigate, initialAction }) {
  const [todos, setTodos] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [newTodo, setNewTodo] = useState('');
  const [newDueAt, setNewDueAt] = useState(null);
  const [newReminderAt, setNewReminderAt] = useState(null);
  const [keyword, setKeyword] = useState('');
  const [showCompleted, setShowCompleted] = useState(true);
  const [selectedIds, setSelectedIds] = useState([]);
  const createInputRef = useRef(null);

  const loadTodos = async () => {
    try {
      const params = { include_completed: true };
      if (keyword.trim()) params.keyword = keyword.trim();
      const res = await todoApi.list(params);
      const list = res.data || [];
      setTodos(list);
      const nextDrafts = {};
      list.forEach((t) => { nextDrafts[t.id] = t.content; });
      setDrafts(nextDrafts);
      setSelectedIds((prev) => prev.filter((id) => list.some((t) => t.id === id)));
    } catch {
      message.error('加载待办失败');
    }
  };

  useEffect(() => {
    loadTodos();
  }, [keyword]);

  useEffect(() => {
    if (typeof initialAction === 'string' && initialAction.startsWith('new:')) {
      setTimeout(() => {
        createInputRef.current?.focus();
      }, 0);
    }
  }, [initialAction]);

  useEffect(() => {
    const timer = setInterval(() => {
      const now = dayjs();
      let reminded = [];
      try {
        reminded = JSON.parse(localStorage.getItem(REMINDER_KEY) || '[]');
      } catch {
        reminded = [];
      }
      const remindedSet = new Set(reminded);
      let touched = false;
      for (const t of todos) {
        if (t.is_completed || !t.reminder_at) continue;
        const due = dayjs(t.reminder_at);
        if (!due.isValid()) continue;
        if (due.isBefore(now) || due.isSame(now)) {
          if (!remindedSet.has(t.id)) {
            message.info(`待办提醒：${t.content}`);
            remindedSet.add(t.id);
            touched = true;
          }
        }
      }
      if (touched) {
        localStorage.setItem(REMINDER_KEY, JSON.stringify(Array.from(remindedSet)));
      }
    }, 30000);
    return () => clearInterval(timer);
  }, [todos]);

  const visibleTodos = useMemo(() => {
    if (showCompleted) return todos;
    return todos.filter((t) => !t.is_completed);
  }, [todos, showCompleted]);

  const createTodo = async () => {
    const content = newTodo.trim();
    if (!content) return;
    try {
      await todoApi.create({
        content,
        priority: 'medium',
        due_at: toBackendDatetime(newDueAt),
        reminder_at: toBackendDatetime(newReminderAt),
      });
      setNewTodo('');
      setNewDueAt(null);
      setNewReminderAt(null);
      loadTodos();
    } catch (e) {
      message.error(e.response?.data?.detail || '创建失败');
    }
  };

  const updateTodo = async (id, patch) => {
    try {
      await todoApi.update(id, patch);
      loadTodos();
    } catch (e) {
      message.error(e.response?.data?.detail || '更新失败');
    }
  };

  const deleteTodo = async (id) => {
    try {
      await todoApi.delete(id);
      loadTodos();
    } catch {
      message.error('删除失败');
    }
  };

  const jumpToSource = async (todo) => {
    if (!todo?.source_note_id) {
      message.warning('该待办没有来源');
      return;
    }
    try {
      const res = await noteApi.get(todo.source_note_id);
      const n = res.data;
      const tab = n.note_type === 'diary' ? 'diary' : 'doc';
      onNavigate?.(tab, { id: n.id, anchor: todo.source_anchor_text || '' });
    } catch {
      message.error('来源笔记不存在或已删除');
    }
  };

  const toggleSelect = (id, checked) => {
    setSelectedIds((prev) => {
      if (checked) return prev.includes(id) ? prev : [...prev, id];
      return prev.filter((x) => x !== id);
    });
  };

  const selectAllVisible = () => {
    setSelectedIds((prev) => {
      const set = new Set(prev);
      visibleTodos.forEach((t) => set.add(t.id));
      return Array.from(set);
    });
  };

  const clearSelected = () => setSelectedIds([]);

  const bulkSetCompleted = async (isCompleted) => {
    if (selectedIds.length === 0) {
      message.warning('请先勾选待办');
      return;
    }
    try {
      await Promise.all(selectedIds.map((id) => todoApi.update(id, { is_completed: isCompleted })));
      message.success(isCompleted ? '批量标记完成' : '批量标记未完成');
      setSelectedIds([]);
      loadTodos();
    } catch {
      message.error('批量更新失败');
    }
  };

  return (
    <div className="view-container">
      <div className="side-panel todo-side-panel">
        <div className="side-search">
          <input
            className="todo-input"
            placeholder="搜索待办..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>

        <div className="side-search">
          <input
            ref={createInputRef}
            className="todo-input"
            placeholder="输入待办事项，回车创建"
            value={newTodo}
            onChange={(e) => setNewTodo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') createTodo();
            }}
          />
          <div className="todo-date-grid">
            <label>截止</label>
            <DatePicker
              className="todo-datetime-picker"
              popupClassName="todo-time-picker-popup"
              showTime
              format="YYYY-MM-DD HH:mm"
              value={newDueAt}
              onChange={(v) => setNewDueAt(v)}
              placeholder="选择截止时间"
            />
            <label>提醒</label>
            <DatePicker
              className="todo-datetime-picker"
              popupClassName="todo-time-picker-popup"
              showTime
              format="YYYY-MM-DD HH:mm"
              value={newReminderAt}
              onChange={(v) => setNewReminderAt(v)}
              placeholder="选择提醒时间"
            />
          </div>
        </div>

        <div className="doc-actions">
          <button className="action-btn" onClick={createTodo}>+ 新建待办</button>
        </div>

        <div className="side-tags">
          <div className="side-tags-header">显示：</div>
          <div className={`tag-item ${showCompleted ? 'active' : ''}`} onClick={() => setShowCompleted(true)}>
            全部 ({todos.length})
          </div>
          <div className={`tag-item ${!showCompleted ? 'active' : ''}`} onClick={() => setShowCompleted(false)}>
            未完成 ({todos.filter((t) => !t.is_completed).length})
          </div>
        </div>
      </div>

      <div className="main-content">
        <div className="todo-view-main">
          <div className="todo-view-title">稍后待办管理</div>
          <div className="todo-bulk-bar">
            <button className="todo-bulk-btn" onClick={selectAllVisible}>全选当前</button>
            <button className="todo-bulk-btn" onClick={clearSelected}>清空勾选</button>
            <button className="todo-bulk-btn primary" onClick={() => bulkSetCompleted(true)}>批量完成</button>
            <button className="todo-bulk-btn" onClick={() => bulkSetCompleted(false)}>批量未完成</button>
            <span className="todo-bulk-count">已选 {selectedIds.length} 条</span>
          </div>
          <div className="todo-list">
            {visibleTodos.length > 0 ? visibleTodos.map((t) => (
              <div key={t.id} className={`todo-item ${t.is_completed ? 'done' : ''}`}>
                <div className="todo-row">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(t.id)}
                    onChange={(e) => toggleSelect(t.id, e.target.checked)}
                    title="勾选用于批量操作"
                  />
                  <input
                    type="checkbox"
                    checked={t.is_completed}
                    onChange={(e) => updateTodo(t.id, { is_completed: e.target.checked })}
                  />
                  <input
                    className="todo-content-input"
                    value={drafts[t.id] || ''}
                    onChange={(e) => setDrafts((prev) => ({ ...prev, [t.id]: e.target.value }))}
                    onBlur={() => {
                      const val = (drafts[t.id] || '').trim();
                      if (val && val !== t.content) updateTodo(t.id, { content: val });
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') e.currentTarget.blur();
                    }}
                  />
                </div>

                <div className="todo-row todo-meta">
                  <select
                    className={`todo-priority priority-${t.priority}`}
                    value={t.priority}
                    onChange={(e) => updateTodo(t.id, { priority: e.target.value })}
                  >
                    <option value="high">高优先级</option>
                    <option value="medium">中优先级</option>
                    <option value="low">低优先级</option>
                  </select>
                  <span className="todo-priority-text">添加于 {dayjs(t.created_at).format('YYYY-MM-DD HH:mm:ss')}</span>
                  <button className="todo-del-btn" onClick={() => jumpToSource(t)}>回跳来源</button>
                  <button className="todo-del-btn" onClick={() => deleteTodo(t.id)}>删除</button>
                </div>

                <div className="todo-row todo-date-row">
                  <span className="todo-date-label">截止</span>
                  <DatePicker
                    className="todo-datetime-picker row"
                    popupClassName="todo-time-picker-popup"
                    showTime
                    format="YYYY-MM-DD HH:mm"
                    value={t.due_at ? dayjs(t.due_at) : null}
                    onChange={(v) => updateTodo(t.id, { due_at: toBackendDatetime(v) })}
                  />
                  <span className="todo-date-label">提醒</span>
                  <DatePicker
                    className="todo-datetime-picker row"
                    popupClassName="todo-time-picker-popup"
                    showTime
                    format="YYYY-MM-DD HH:mm"
                    value={t.reminder_at ? dayjs(t.reminder_at) : null}
                    onChange={(v) => updateTodo(t.id, { reminder_at: toBackendDatetime(v) })}
                  />
                </div>
              </div>
            )) : <div className="empty-hint">暂无待办事项</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
