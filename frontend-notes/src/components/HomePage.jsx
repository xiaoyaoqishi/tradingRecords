import { useState, useEffect } from 'react';
import { noteApi, todoApi } from '../api';
import { getWeather } from '../utils/weather';
import { Lunar, Solar } from 'lunar-javascript';
import dayjs from 'dayjs';

export default function HomePage({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [weather, setWeather] = useState(null);
  const [todos, setTodos] = useState([]);

  useEffect(() => {
    noteApi.stats().then(r => setStats(r.data)).catch(() => {});
    getWeather().then(setWeather);
    todoApi.list().then((r) => setTodos(r.data || [])).catch(() => {});
  }, []);

  const now = dayjs();
  const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
  const solar = Solar.fromDate(new Date());
  const lunar = solar.getLunar();
  const lunarStr = `${lunar.getYearInGanZhi()}年 ${lunar.getMonthInChinese()}月${lunar.getDayInChinese()}`;
  const dateStr = `${now.format('YYYY年M月D日')} 星期${weekdays[now.day()]}`;

  const upcoming = [0, 1, 2].map(i => {
    const d = now.add(i, 'day');
    return {
      label: i === 0 ? '今天' : `周${weekdays[d.day()]}`,
      date: d.format('YYYY-MM-DD'),
      weather: weather?.forecast?.[i],
    };
  });

  const priorityLabel = (p) => {
    if (p === 'high') return '高';
    if (p === 'low') return '低';
    return '中';
  };
  const pendingTodos = todos.filter((t) => !t.is_completed);

  return (
    <div className="home-page">
      <div className="home-header">
        <div className="home-header-left">
          <div className="home-date-primary">今天：</div>
          <div className="home-date-solar">{dateStr}</div>
          <div className="home-date-lunar">{lunarStr}</div>
        </div>
        {weather && (
          <div className="home-header-weather">
            <div className="weather-location">{weather.province} {weather.city}</div>
            <div className="weather-current">
              <span className="weather-icon-lg">{weather.icon}</span>
              <span className="weather-temp">{weather.temp}°C</span>
              <span className="weather-text">{weather.text}</span>
            </div>
          </div>
        )}
        {weather?.forecast && (
          <div className="home-header-forecast">
            {weather.forecast.slice(1).map((f, i) => (
              <div key={i} className="forecast-item">
                <span className="forecast-label">{i === 0 ? '明天' : '后天'}：</span>
                <span>{f.wmo.icon} {f.wmo.text} {f.min}°C~{f.max}°C</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="home-body">
        <div className="home-section home-stats">
          <h3>知识笔记概览</h3>
          {stats && (
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
          <div className="home-today-hint">
            <a onClick={() => onNavigate('diary', 'today')}>
              开始写今天的日记 &gt;&gt;
            </a>
          </div>

          <h4>最近的文档</h4>
          <div className="recent-docs">
            {stats?.recent_docs?.map(doc => (
              <div key={doc.id} className="recent-doc-item" onClick={() => onNavigate('doc', doc.id)}>
                📄 {doc.title}
              </div>
            ))}
            {(!stats?.recent_docs || stats.recent_docs.length === 0) && (
              <div className="empty-hint">暂无文档</div>
            )}
          </div>
        </div>

        <div className="home-section home-calendar-memo">
          <h3>日历备忘</h3>
          {upcoming.map(d => (
            <div key={d.date} className="calendar-memo-item">
              <span className="memo-label">{d.label}</span>
              <span className="memo-date">{d.date}</span>
              {d.weather && (
                <span className="memo-weather">{d.weather.wmo.icon} {d.weather.min}~{d.weather.max}°C</span>
              )}
            </div>
          ))}
        </div>

        <div className="home-section home-todo">
          <div className="todo-board-head">
            <h3>稍后待办看板</h3>
            <button className="todo-add-btn" onClick={() => onNavigate('todo')}>进入待办模块</button>
          </div>
          <div className="todo-list">
            {pendingTodos.length > 0 ? pendingTodos.slice(0, 10).map((t) => (
              <div key={t.id} className={`todo-item ${t.is_completed ? 'done' : ''}`}>
                <div className="todo-row">
                  <span>{t.is_completed ? '✅' : '⬜'} {t.content}</span>
                </div>
                <div className="todo-row todo-meta">
                  <span className={`todo-priority priority-${t.priority}`}>优先级: {priorityLabel(t.priority)}</span>
                  <span className="todo-time">添加于 {dayjs(t.created_at).format('YYYY-MM-DD HH:mm:ss')}</span>
                </div>
              </div>
            )) : (
              <div className="empty-hint">暂无待办事项</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
