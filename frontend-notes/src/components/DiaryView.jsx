import { useState, useEffect, useCallback, useRef } from 'react';
import { Input, Popconfirm, message } from 'antd';
import { DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import { noteApi } from '../api';
import { getWeather } from '../utils/weather';
import NoteEditor from './NoteEditor';
import MiniCalendar from './MiniCalendar';
import dayjs from 'dayjs';

export default function DiaryView({ initialNoteId, notebooks }) {
  const [activeNote, setActiveNote] = useState(null);
  const [tree, setTree] = useState({});
  const [expandedYears, setExpandedYears] = useState({});
  const [expandedMonths, setExpandedMonths] = useState({});
  const [keyword, setKeyword] = useState('');
  const [calendarDates, setCalendarDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [summaryTitle, setSummaryTitle] = useState('');
  const [summaries, setSummaries] = useState([]);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const saveTimer = useRef(null);
  const creatingToday = useRef(false);

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
    if (creatingToday.current) return;
    creatingToday.current = true;
    const todayStr = dayjs().format('YYYY-MM-DD');
    try {
      const res = await noteApi.list({ note_type: 'diary', note_date: todayStr });
      if (res.data.length > 0) {
        setActiveNote(res.data[0]);
        setSummaryTitle('');
        setSummaries([]);
      } else {
        const nb = notebooks[0];
        if (!nb) { message.warning('请先创建笔记本'); creatingToday.current = false; return; }
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
        setSummaryTitle('');
        setSummaries([]);
        loadTree();
        loadCalendar(selectedDate);
      }
    } catch { message.error('创建日记失败'); }
    finally { creatingToday.current = false; }
  };

  const handleSelectDate = async (date) => {
    setSelectedDate(date);
    const dateStr = date.format('YYYY-MM-DD');
    try {
      const res = await noteApi.list({ note_type: 'diary', note_date: dateStr });
      if (res.data.length > 0) {
        setActiveNote(res.data[0]);
        setSummaryTitle('');
        setSummaries([]);
      } else {
        setActiveNote(null);
      }
    } catch {}
  };

  const handleSelectTreeNote = async (noteId) => {
    try {
      const res = await noteApi.get(noteId);
      setActiveNote(res.data);
      setSummaryTitle('');
      setSummaries([]);
    } catch {}
  };

  const loadSummary = async (year, month = null, title = '') => {
    setSummaryLoading(true);
    setSummaryTitle(title);
    setActiveNote(null);
    try {
      const res = await noteApi.diarySummaries({ year, month });
      setSummaries(res.data || []);
    } catch {
      setSummaries([]);
      message.error('加载梗概失败');
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleYearClick = (yearLabel) => {
    setExpandedYears(prev => ({ ...prev, [yearLabel]: !prev[yearLabel] }));
    const year = parseInt(String(yearLabel).replace('年', ''), 10);
    if (Number.isFinite(year)) {
      loadSummary(year, null, `${year}年日记梗概`);
    }
  };

  const handleMonthClick = (yearLabel, monthLabel) => {
    setExpandedMonths(prev => ({ ...prev, [`${yearLabel}-${monthLabel}`]: !prev[`${yearLabel}-${monthLabel}`] }));
    const year = parseInt(String(yearLabel).replace('年', ''), 10);
    const month = parseInt(String(monthLabel).replace('月', ''), 10);
    if (Number.isFinite(year) && Number.isFinite(month)) {
      loadSummary(year, month, `${year}年${month}月日记梗概`);
    }
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

        <button className="write-today-btn" onClick={handleWriteToday}>
          ✏️ 写今天的日记
        </button>

        <div className="date-tree">
          {Object.entries(tree).map(([year, months]) => (
            <div key={year}>
              <div
                className="tree-year"
                onClick={() => handleYearClick(year)}
              >
                {expandedYears[year] ? '▾' : '▸'} 📂 {year}
              </div>
              {expandedYears[year] && Object.entries(months).map(([month, days]) => (
                <div key={month} style={{ paddingLeft: 12 }}>
                  <div
                    className="tree-month"
                    onClick={() => handleMonthClick(year, month)}
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
        ) : summaryTitle ? (
          <div className="diary-summary-panel">
            <div className="diary-summary-title">{summaryTitle}</div>
            {summaryLoading ? (
              <div className="empty-hint">加载中...</div>
            ) : summaries.length > 0 ? (
              <div className="diary-summary-list">
                {summaries.map((item) => (
                  <div key={item.id} className="diary-summary-row" onClick={() => handleSelectTreeNote(item.id)}>
                    <span className="diary-summary-date">{item.note_date}</span>
                    <span className="diary-summary-text">{item.summary}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-hint">该范围暂无日记</div>
            )}
          </div>
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
