import { useState, useEffect, useMemo } from 'react';
import { noteApi, todoApi } from '../api';
import { getWeather } from '../utils/weather';
import { Lunar, Solar } from 'lunar-javascript';
import dayjs from 'dayjs';

export default function HomePage({ onNavigate }) {
  const PINNED_DOC_KEY = 'notes-home-pinned-docs';
  const [stats, setStats] = useState(null);
  const [weather, setWeather] = useState(null);
  const [todos, setTodos] = useState([]);
  const [diaryTree, setDiaryTree] = useState({});
  const [todayDiaries, setTodayDiaries] = useState([]);
  const [allDocs, setAllDocs] = useState([]);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState({ diary: [], doc: [], todo: [] });
  const [pinnedDocIds, setPinnedDocIds] = useState(() => {
    try {
      const arr = JSON.parse(localStorage.getItem(PINNED_DOC_KEY) || '[]');
      return Array.isArray(arr) ? arr.slice(0, 5) : [];
    } catch {
      return [];
    }
  });
  const [loading, setLoading] = useState({
    stats: true,
    weather: true,
    todos: true,
    diaryTree: true,
    summary: true,
  });

  useEffect(() => {
    let alive = true;
    const todayStr = dayjs().format('YYYY-MM-DD');
    Promise.allSettled([
      noteApi.stats(),
      noteApi.diaryTree(),
      getWeather(),
      todoApi.list(),
      noteApi.list({ note_type: 'diary', note_date: todayStr }),
      noteApi.list({ note_type: 'doc' }),
    ]).then(([statsRes, treeRes, weatherRes, todosRes, todayDiariesRes, docsRes]) => {
      if (!alive) return;
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
      if (treeRes.status === 'fulfilled') setDiaryTree(treeRes.value.data || {});
      if (weatherRes.status === 'fulfilled') setWeather(weatherRes.value || null);
      if (todosRes.status === 'fulfilled') setTodos(todosRes.value.data || []);
      if (todayDiariesRes?.status === 'fulfilled') setTodayDiaries(todayDiariesRes.value.data || []);
      if (docsRes?.status === 'fulfilled') setAllDocs(docsRes.value.data || []);
      setLoading({ stats: false, weather: false, todos: false, diaryTree: false, summary: false });
    });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const q = searchKeyword.trim();
    if (!q) {
      setSearchResults({ diary: [], doc: [], todo: [] });
      setSearchLoading(false);
      return;
    }
    const t = setTimeout(async () => {
      try {
        setSearchLoading(true);
        const [d1, d2, d3] = await Promise.all([
          noteApi.search({ q, note_type: 'diary', limit: 6 }),
          noteApi.search({ q, note_type: 'doc', limit: 6 }),
          todoApi.list({ include_completed: true, keyword: q }),
        ]);
        setSearchResults({
          diary: d1.data || [],
          doc: d2.data || [],
          todo: (d3.data || []).slice(0, 6),
        });
      } catch {
        setSearchResults({ diary: [], doc: [], todo: [] });
      } finally {
        setSearchLoading(false);
      }
    }, 220);
    return () => clearTimeout(t);
  }, [searchKeyword]);

  const now = dayjs();
  const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
  const solar = Solar.fromDate(new Date());
  const lunar = solar.getLunar();
  const lunarStr = `${lunar.getYearInGanZhi()}年 ${lunar.getMonthInChinese()}月${lunar.getDayInChinese()}`;
  const dateStr = `${now.format('YYYY年M月D日')} 星期${weekdays[now.day()]}`;

  const priorityLabel = (p) => {
    if (p === 'high') return '高';
    if (p === 'low') return '低';
    return '中';
  };
  const pendingTodos = todos.filter((t) => !t.is_completed);
  const diaryDates = useMemo(() => {
    const set = new Set();
    Object.values(diaryTree).forEach((months) => {
      Object.values(months).forEach((days) => {
        days.forEach((n) => set.add(n.date));
      });
    });
    return set;
  }, [diaryTree]);
  const streakDays = useMemo(() => {
    let count = 0;
    let d = dayjs();
    while (diaryDates.has(d.format('YYYY-MM-DD'))) {
      count += 1;
      d = d.subtract(1, 'day');
    }
    return count;
  }, [diaryDates]);
  const heatDays = useMemo(() => {
    const arr = [];
    for (let i = 34; i >= 0; i--) {
      const d = dayjs().subtract(i, 'day');
      arr.push({ date: d.format('YYYY-MM-DD'), has: diaryDates.has(d.format('YYYY-MM-DD')) });
    }
    return arr;
  }, [diaryDates]);
  const monthKey = now.format('YYYY-MM-');
  const monthTotalDays = now.daysInMonth();
  const monthWrittenDays = useMemo(
    () => Array.from(diaryDates).filter((d) => d.startsWith(monthKey)).length,
    [diaryDates, monthKey]
  );
  const monthRate = monthTotalDays ? Math.round((monthWrittenDays / monthTotalDays) * 100) : 0;
  const todayStr = now.format('YYYY-MM-DD');
  const todayDiaryWords = useMemo(
    () => (todayDiaries || []).reduce((sum, n) => sum + (n.word_count || 0), 0),
    [todayDiaries]
  );
  const todayNewDocs = useMemo(
    () => (allDocs || []).filter((n) => String(n.created_at || '').startsWith(todayStr)).length,
    [allDocs, todayStr]
  );
  const todoDoneRate = useMemo(() => {
    const total = todos.length;
    if (!total) return 0;
    const done = todos.filter((t) => t.is_completed).length;
    return Math.round((done / total) * 100);
  }, [todos]);
  const sortedRecentDocs = useMemo(() => {
    const arr = stats?.recent_docs || [];
    const order = new Map(pinnedDocIds.map((id, idx) => [id, idx]));
    return [...arr].sort((a, b) => {
      const ap = order.has(a.id);
      const bp = order.has(b.id);
      if (ap && bp) return order.get(a.id) - order.get(b.id);
      if (ap) return -1;
      if (bp) return 1;
      return 0;
    });
  }, [stats, pinnedDocIds]);

  const dueGroups = useMemo(() => {
    const g = { h24: [], d3: [], later: [] };
    const base = dayjs();
    pendingTodos.forEach((t) => {
      if (!t.due_at) {
        g.later.push(t);
        return;
      }
      const due = dayjs(t.due_at);
      if (!due.isValid()) {
        g.later.push(t);
        return;
      }
      const hours = due.diff(base, 'hour', true);
      if (hours <= 24) g.h24.push(t);
      else if (hours <= 72) g.d3.push(t);
      else g.later.push(t);
    });
    return g;
  }, [pendingTodos]);

  const togglePinDoc = (id) => {
    setPinnedDocIds((prev) => {
      const exists = prev.includes(id);
      const next = exists ? prev.filter((x) => x !== id) : [id, ...prev].slice(0, 5);
      try { localStorage.setItem(PINNED_DOC_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  };

  const openFirstSearchResult = () => {
    if (searchResults.diary[0]) {
      onNavigate('diary', searchResults.diary[0].id);
      return;
    }
    if (searchResults.doc[0]) {
      onNavigate('doc', searchResults.doc[0].id);
      return;
    }
    if (searchResults.todo[0]) onNavigate('todo');
  };

  return (
    <div className="home-page">
      <div className="home-header">
        <div className="home-header-left">
          <div className="home-date-primary">今天：</div>
          <div className="home-date-solar">{dateStr}</div>
          <div className="home-date-lunar">{lunarStr}</div>
        </div>
        {!loading.weather && weather && (
          <div className="home-header-weather">
            <div className="weather-location">{weather.province} {weather.city}</div>
            <div className="weather-current">
              <span className="weather-icon-lg">{weather.icon}</span>
              <span className="weather-temp">{weather.temp}°C</span>
              <span className="weather-text">{weather.text}</span>
            </div>
          </div>
        )}
        {!loading.weather && weather?.forecast && (
          <div className="home-header-forecast">
            {weather.forecast.slice(1).map((f, i) => (
              <div key={i} className="forecast-item">
                <span className="forecast-label">{i === 0 ? '明天' : '后天'}：</span>
                <span>{f.wmo.icon} {f.wmo.text} {f.min}°C~{f.max}°C</span>
              </div>
            ))}
          </div>
        )}
        {loading.weather && <div className="home-skeleton-line" style={{ width: 220 }} />}
      </div>

      <div className="home-body">
        <div className="home-section home-quick">
          <h3>快速入口</h3>
          <div className="home-global-search">
            <input
              className="todo-input"
              placeholder="全局搜索（日记/文档/待办）"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') openFirstSearchResult();
              }}
            />
            {searchKeyword.trim() && (
              <div className="home-search-result-panel">
                {searchLoading ? (
                  <div className="empty-hint">搜索中...</div>
                ) : (
                  <>
                    <div className="home-search-group">
                      <div className="home-search-group-title">日记（{searchResults.diary.length}）</div>
                      {searchResults.diary.slice(0, 3).map((n) => (
                        <div key={`d-${n.id}`} className="home-search-item" onClick={() => onNavigate('diary', n.id)}>📔 {n.title || '无标题'}</div>
                      ))}
                    </div>
                    <div className="home-search-group">
                      <div className="home-search-group-title">文档（{searchResults.doc.length}）</div>
                      {searchResults.doc.slice(0, 3).map((n) => (
                        <div key={`n-${n.id}`} className="home-search-item" onClick={() => onNavigate('doc', n.id)}>📄 {n.title || '无标题'}</div>
                      ))}
                    </div>
                    <div className="home-search-group">
                      <div className="home-search-group-title">待办（{searchResults.todo.length}）</div>
                      {searchResults.todo.slice(0, 3).map((t) => (
                        <div key={`t-${t.id}`} className="home-search-item" onClick={() => onNavigate('todo')}>{t.is_completed ? '✅' : '⬜'} {t.content}</div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="home-overview-row">
            {loading.summary ? (
              <div className="home-skeleton-line" />
            ) : (
              <>
                <span>今日日记字数 {todayDiaryWords}</span>
                <span>今日新文档 {todayNewDocs}</span>
                <span>待办完成率 {todoDoneRate}%</span>
              </>
            )}
          </div>
          <div className="home-quick-actions">
            <button className="home-quick-btn" onClick={() => onNavigate('diary', 'today')}>写今日日记</button>
            <button className="home-quick-btn" onClick={() => onNavigate('doc', `new:${Date.now()}`)}>新建文档</button>
            <button className="home-quick-btn" onClick={() => onNavigate('todo', `new:${Date.now()}`)}>新建待办</button>
          </div>
          <div className="home-template-row">
            <button className="home-template-btn" onClick={() => onNavigate('diary', 'today:morning')}>晨间计划</button>
            <button className="home-template-btn" onClick={() => onNavigate('diary', 'today:review')}>交易复盘</button>
            <button className="home-template-btn" onClick={() => onNavigate('diary', 'today:mood')}>情绪记录</button>
          </div>
        </div>

        <div className="home-section home-stats">
          <h3>知识笔记概览</h3>
          <div className="home-streak-card">
            <div className="home-block-title">连续记录</div>
            <div className="home-streak-num">{streakDays} 天</div>
            <div className="home-month-rate">本月记录率 {monthRate}%（{monthWrittenDays}/{monthTotalDays}）</div>
            <div className="home-heat-grid">
              {heatDays.map((d) => (
                <span key={d.date} className={`home-heat-dot ${d.has ? 'active' : ''}`} title={d.date} />
              ))}
            </div>
          </div>

          {!loading.stats && stats && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-num">{stats.diary_count}</div>
                <div className="stat-label">篇日记</div>
                <div className="stat-sub">共 {stats.diary_word_count.toLocaleString()} 字</div>
              </div>
              <div className="stat-card">
                <div className="stat-num">{stats.doc_count}</div>
                <div className="stat-label">篇文档</div>
                <div className="stat-sub">共 {stats.doc_word_count.toLocaleString()} 字</div>
              </div>
            </div>
          )}
          {loading.stats && <div className="home-skeleton-grid"><div className="home-skeleton-card" /><div className="home-skeleton-card" /></div>}
          <h4>最近的文档</h4>
          <div className="recent-docs">
            {sortedRecentDocs.map(doc => (
              <div key={doc.id} className="recent-doc-item" onClick={() => onNavigate('doc', doc.id)}>
                <span>📄 {doc.title}</span>
                <button
                  className={`home-pin-btn ${pinnedDocIds.includes(doc.id) ? 'active' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    togglePinDoc(doc.id);
                  }}
                  title={pinnedDocIds.includes(doc.id) ? '取消固定' : '固定到顶部'}
                >
                  {pinnedDocIds.includes(doc.id) ? '★' : '☆'}
                </button>
              </div>
            ))}
            {(!stats?.recent_docs || stats.recent_docs.length === 0) && (
              <div className="empty-hint">暂无文档</div>
            )}
          </div>
        </div>

        <div className="home-section home-todo">
          <div className="todo-board-head">
            <h3>稍后待办看板</h3>
            <button className="todo-add-btn" onClick={() => onNavigate('todo')}>进入待办模块</button>
          </div>
          {loading.todos ? (
            <div className="home-skeleton-list">
              <div className="home-skeleton-line" />
              <div className="home-skeleton-line" />
              <div className="home-skeleton-line" />
            </div>
          ) : (
            <div className="todo-list">
              {pendingTodos.length > 0 ? (
                <>
                  {[
                    { key: 'h24', title: '24小时内', list: dueGroups.h24 },
                    { key: 'd3', title: '3天内', list: dueGroups.d3 },
                    { key: 'later', title: '更晚/未设置', list: dueGroups.later },
                  ].map((group) => (
                    <div key={group.key} className="home-todo-group">
                      <div className="home-todo-group-title">{group.title}（{group.list.length}）</div>
                      {group.list.slice(0, 4).map((t) => (
                        <div key={t.id} className={`todo-item ${t.is_completed ? 'done' : ''}`}>
                          <div className="todo-row">
                            <span>{t.is_completed ? '✅' : '⬜'} {t.content}</span>
                          </div>
                          <div className="todo-row todo-meta">
                            <span className={`todo-priority priority-${t.priority}`}>优先级: {priorityLabel(t.priority)}</span>
                            {t.due_at && (
                              <span className="todo-due-time">截止 {dayjs(t.due_at).format('YYYY-MM-DD HH:mm')}</span>
                            )}
                            <span className="todo-time">添加于 {dayjs(t.created_at).format('YYYY-MM-DD HH:mm:ss')}</span>
                          </div>
                        </div>
                      ))}
                      {group.list.length === 0 && <div className="empty-hint">暂无</div>}
                    </div>
                  ))}
                </>
              ) : (
                <div className="empty-hint">暂无待办事项</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
