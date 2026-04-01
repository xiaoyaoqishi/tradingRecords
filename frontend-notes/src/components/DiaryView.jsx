import { useState, useEffect, useCallback, useRef } from 'react';
import { Input, Popconfirm, message } from 'antd';
import { DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import { noteApi } from '../api';
import { getWeather } from '../utils/weather';
import NoteEditor from './NoteEditor';
import MiniCalendar from './MiniCalendar';
import dayjs from 'dayjs';

const DIARY_TAGS = [
  { key: 'all', label: '全部日记', icon: '📒' },
  { key: '工作笔记', label: '工作笔记', icon: '💼' },
  { key: '生活杂记', label: '生活杂记', icon: '🏠' },
  { key: '心情随笔', label: '心情随笔', icon: '💭' },
];

export default function DiaryView({ initialNoteId, notebooks }) {
  const [activeNote, setActiveNote] = useState(null);
  const [tree, setTree] = useState({});
  const [expandedYears, setExpandedYears] = useState({});
  const [expandedMonths, setExpandedMonths] = useState({});
  const [activeTag, setActiveTag] = useState('all');
  const [keyword, setKeyword] = useState('');
  const [calendarDates, setCalendarDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const saveTimer = useRef(null);

  const loadTree = useCallback(async () => {
    try {
      const res = await noteApi.diaryTree();
      setTree(res.data);
      const years = Object.keys(res.data);
      if (years.length > 0) {
        const ey = { [years[0]]: true };
        const em = {};
        const months = Object.keys(res.data[years[0]]);
        if (months.length > 0) em[`${years[0]}-${months[0]}`] = true;
        setExpandedYears(ey);
        setExpandedMonths(em);
      }
    } catch {}
  }, []);

  const loadCalendar = useCallback(async (date) => {
    try {
      const res = await noteApi.calendar(date.year(), date.month() + 1);
      setCalendarDates(res.data);
    } catch {}
  }, []);

  useEffect(() => { loadTree(); }, [loadTree]);
  useEffect(() => { loadCalendar(selectedDate); }, [selectedDate, loadCalendar]);

  useEffect(() => {
    if (initialNoteId === 'today') {
      handleWriteToday();
    } else if (initialNoteId && typeof initialNoteId === 'number') {
      noteApi.get(initialNoteId).then(r => setActiveNote(r.data)).catch(() => {});
    }
  }, [initialNoteId]);

  const handleWriteToday = async () => {
    const todayStr = dayjs().format('YYYY-MM-DD');
    try {
      const res = await noteApi.list({ note_type: 'diary', note_date: todayStr });
      if (res.data.length > 0) {
        setActiveNote(res.data[0]);
      } else {
        const nb = notebooks[0];
        if (!nb) { message.warning('请先创建笔记本'); return; }
        const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
        const now = dayjs();
        let weatherIcon = '';
        try {
          const w = await getWeather();
          if (w) weatherIcon = w.icon + ' ';
        } catch {}
        const title = `${weatherIcon}${now.format('YYYY年M月D日')} 星期${weekdays[now.day()]} ${now.format('HH:mm')}`;
        const newNote = await noteApi.create({
          notebook_id: nb.id,
          title,
          content: '',
          note_type: 'diary',
          note_date: todayStr,
        });
        setActiveNote(newNote.data);
        loadTree();
        loadCalendar(selectedDate);
      }
    } catch { message.error('创建日记失败'); }
  };

  const handleSelectDate = async (date) => {
    setSelectedDate(date);
    const dateStr = date.format('YYYY-MM-DD');
    try {
      const res = await noteApi.list({ note_type: 'diary', note_date: dateStr });
      if (res.data.length > 0) {
        setActiveNote(res.data[0]);
      } else {
        setActiveNote(null);
      }
    } catch {}
  };

  const handleSelectTreeNote = async (noteId) => {
    try {
      const res = await noteApi.get(noteId);
      setActiveNote(res.data);
    } catch {}
  };

  const handleUpdateNote = useCallback(async (id, updates) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try {
        const res = await noteApi.update(id, updates);
        setActiveNote(res.data);
      } catch {}
    }, 800);
  }, []);

  const handleDeleteNote = async (id) => {
    try {
      await noteApi.delete(id);
      if (activeNote?.id === id) setActiveNote(null);
      loadTree();
      loadCalendar(selectedDate);
      message.success('已删除');
    } catch { message.error('删除失败'); }
  };

  let totalCount = 0;
  for (const months of Object.values(tree)) {
    for (const days of Object.values(months)) {
      totalCount += days.length;
    }
  }

  return (
    <div className="view-container">
      <div className="side-panel">
        <div className="side-search">
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索日记..."
            size="small"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            allowClear
          />
        </div>

        <div className="mini-calendar-wrap">
          <MiniCalendar
            value={selectedDate}
            onChange={handleSelectDate}
            markedDates={calendarDates}
          />
        </div>

        <div className="side-tags">
          <div className="side-tags-header">标签：</div>
          {DIARY_TAGS.map(t => (
            <div
              key={t.key}
              className={`tag-item ${activeTag === t.key ? 'active' : ''}`}
              onClick={() => setActiveTag(t.key)}
            >
              {t.icon} {t.label}
              {t.key === 'all' && <span className="tag-count">({totalCount})</span>}
            </div>
          ))}
        </div>

        <button className="write-today-btn" onClick={handleWriteToday}>
          ✏️ 写今天的日记
        </button>

        <div className="date-tree">
          {Object.entries(tree).map(([year, months]) => (
            <div key={year}>
              <div
                className="tree-year"
                onClick={() => setExpandedYears(prev => ({ ...prev, [year]: !prev[year] }))}
              >
                {expandedYears[year] ? '▾' : '▸'} 📂 {year}
              </div>
              {expandedYears[year] && Object.entries(months).map(([month, days]) => (
                <div key={month} style={{ paddingLeft: 12 }}>
                  <div
                    className="tree-month"
                    onClick={() => setExpandedMonths(prev => ({ ...prev, [`${year}-${month}`]: !prev[`${year}-${month}`] }))}
                  >
                    {expandedMonths[`${year}-${month}`] ? '▾' : '▸'} 📁 {month}
                  </div>
                  {expandedMonths[`${year}-${month}`] && days.map(note => (
                    <div
                      key={note.id}
                      className={`tree-day ${activeNote?.id === note.id ? 'active' : ''}`}
                      onClick={() => handleSelectTreeNote(note.id)}
                    >
                      📝 {note.day}
                      <Popconfirm
                        title="确定删除？"
                        onConfirm={(e) => { e?.stopPropagation(); handleDeleteNote(note.id); }}
                      >
                        <DeleteOutlined
                          className="tree-delete"
                          onClick={e => e.stopPropagation()}
                        />
                      </Popconfirm>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="main-content">
        {activeNote ? (
          <NoteEditor
            note={activeNote}
            onUpdate={handleUpdateNote}
            defaultEditing={activeNote.note_date === dayjs().format('YYYY-MM-DD')}
          />
        ) : (
          <div className="empty-editor">
            <div className="empty-icon">📝</div>
            <div>选择日期或点击「写今天的日记」开始记录</div>
          </div>
        )}
      </div>
    </div>
  );
}
