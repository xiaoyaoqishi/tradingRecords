import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Empty, DatePicker, Spin } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts';
import { tradeApi } from '../api';

const { RangePicker } = DatePicker;

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({});

  useEffect(() => {
    setLoading(true);
    tradeApi.stats(filters)
      .then(r => setStats(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filters]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!stats || stats.total === 0) return <Empty description="暂无已平仓交易数据" />;

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><h2 style={{ margin: 0 }}>仪表盘</h2></Col>
        <Col>
          <RangePicker onChange={(dates) => {
            if (dates) {
              setFilters({ date_from: dates[0].format('YYYY-MM-DD'), date_to: dates[1].format('YYYY-MM-DD') });
            } else {
              setFilters({});
            }
          }} />
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="总交易数" value={stats.total} /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="胜率" value={stats.win_rate} suffix="%" precision={2}
              valueStyle={{ color: stats.win_rate >= 50 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总盈亏" value={stats.total_pnl} precision={2}
              prefix={stats.total_pnl >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              valueStyle={{ color: stats.total_pnl >= 0 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="盈亏比" value={stats.profit_loss_ratio} precision={2} /></Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="平均盈利" value={stats.avg_win} precision={2} valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="平均亏损" value={stats.avg_loss} precision={2} valueStyle={{ color: '#cf1322' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="最大连胜" value={stats.max_consecutive_wins} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="最大连亏" value={stats.max_consecutive_losses} /></Card>
        </Col>
      </Row>

      {stats.pnl_over_time.length > 0 && (
        <Card title="累计盈亏曲线" style={{ marginBottom: 24 }}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={stats.pnl_over_time}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="cumulative_pnl" name="累计盈亏" stroke="#1890ff" strokeWidth={2} />
              <Line type="monotone" dataKey="daily_pnl" name="日盈亏" stroke="#52c41a" strokeWidth={1} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <Row gutter={16} style={{ marginBottom: 24 }}>
        {stats.pnl_by_symbol.length > 0 && (
          <Col span={12}>
            <Card title="品种盈亏">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={stats.pnl_by_symbol}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="symbol" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="pnl" name="盈亏">
                    {stats.pnl_by_symbol.map((entry, i) => (
                      <Cell key={i} fill={entry.pnl >= 0 ? '#52c41a' : '#f5222d'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        )}
        {stats.error_tag_counts.length > 0 && (
          <Col span={12}>
            <Card title="错误标签统计">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={stats.error_tag_counts} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="tag" type="category" width={100} />
                  <Tooltip />
                  <Bar dataKey="count" name="次数" fill="#f5222d" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        )}
      </Row>

      {stats.pnl_by_strategy.length > 0 && (
        <Card title="策略统计">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={stats.pnl_by_strategy}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="strategy" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="pnl" name="盈亏" fill="#1890ff" />
              <Bar dataKey="count" name="次数" fill="#52c41a" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}
