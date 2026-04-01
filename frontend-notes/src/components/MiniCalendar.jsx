import { useState } from 'react';
import dayjs from 'dayjs';

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];
const MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

export default function MiniCalendar({ value, onChange, markedDates = [] }) {
  const [viewDate, setViewDate] = useState(value || dayjs());

  const year = viewDate.year();
  const month = viewDate.month();
  const today = dayjs().format('YYYY-MM-DD');
  const selectedStr = value?.format('YYYY-MM-DD');

  const firstDay = viewDate.startOf('month');
  let startWeekday = firstDay.day() - 1;
  if (startWeekday < 0) startWeekday = 6;
  const daysInMonth = viewDate.daysInMonth();

  const cells = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const prevMonth = () => { const nd = viewDate.subtract(1, 'month'); setViewDate(nd); };
  const nextMonth = () => { const nd = viewDate.add(1, 'month'); setViewDate(nd); };

  const handleClick = (day) => {
    if (!day) return;
    const d = dayjs(new Date(year, month, day));
    onChange?.(d);
  };

  return (
    <div className="mc">
      <div className="mc-header">
        <button className="mc-nav" onClick={prevMonth}>&lt;</button>
        <span className="mc-title">{year} 年 {MONTHS[month]}</span>
        <button className="mc-nav" onClick={nextMonth}>&gt;</button>
      </div>
      <div className="mc-weekdays">
        {WEEKDAYS.map(w => <div key={w} className="mc-wd">{w}</div>)}
      </div>
      <div className="mc-days">
        {cells.map((day, i) => {
          if (!day) return <div key={`e-${i}`} className="mc-cell" />;
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const isToday = dateStr === today;
          const isSelected = dateStr === selectedStr;
          const hasNote = markedDates.includes(dateStr);
          return (
            <div
              key={day}
              className={`mc-cell mc-day ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''}`}
              onClick={() => handleClick(day)}
            >
              {day}
              {hasNote && <span className="mc-dot" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
