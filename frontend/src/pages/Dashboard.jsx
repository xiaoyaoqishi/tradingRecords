import { useState, useEffect, useMemo } from 'react';
import { Card, Row, Col, Statistic, Empty, DatePicker, Spin, Table, Tag, Select, Space } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts';
import { tradeApi } from '../api';
import { formatFuturesSymbol, FUTURES_SYMBOL_OPTIONS } from '../utils/futures';

const { RangePicker } = DatePicker;
export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({});
  const [sourceOptions, setSourceOptions] = useState([]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      tradeApi.stats(filters),
      tradeApi.positions({ symbol: filters.symbol, source_keyword: filters.source_keyword }),
    ])
      .then(([s, p]) => {
        setStats(s.data);
        setPositions(p.data || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    tradeApi.sources()
      .then((res) => setSourceOptions((res.data?.items || []).map((v) => ({ label: v, value: v }))))
      .catch(() => setSourceOptions([]));
  }, []);

  const symbolPnlData = useMemo(() => {
    if (!stats?.pnl_by_symbol) return [];
    return stats.pnl_by_symbol.map((x) => ({
      ...x,
      symbol_label: formatFuturesSymbol(x.symbol),
    }));
  }, [stats]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!stats) return <Empty description="暂无数据" />;

  const positionColumns = [
    { title: '品种', dataIndex: 'symbol_label', width: 200 },
    {
      title: '方向', dataIndex: 'side', width: 90,
      render: (v) => <Tag color={v === '做多' ? 'red' : 'green'}>{v}</Tag>,
    },
    { title: '持仓手数', dataIndex: 'net_quantity', width: 100 },
    { title: '持仓均价', dataIndex: 'avg_open_price', width: 120 },
    { title: '开仓起始日', dataIndex: 'open_since', width: 120 },
    { title: '最近成交日', dataIndex: 'last_trade_date', width: 120 },
  ];
  const positionData = positions.map((p, i) => ({
    key: `${p.symbol}-${p.side}-${i}`,
    ...p,
    symbol_label: formatFuturesSymbol(p.symbol, p.contract),
  }));

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><h2 style={{ margin: 0 }}>仪表盘</h2></Col>
        <Col>
          <Space wrap>
            <RangePicker onChange={(dates) => {
              setFilters((prev) => {
                if (dates) {
                  return { ...prev, date_from: dates[0].format('YYYY-MM-DD'), date_to: dates[1].format('YYYY-MM-DD') };
                }
                const { date_from, date_to, ...rest } = prev;
                return rest;
              });
            }} />
            <Select
              placeholder="品种"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: 170 }}
              options={FUTURES_SYMBOL_OPTIONS}
              onChange={(v) => setFilters((prev) => {
                if (!v) {
                  const { symbol, ...rest } = prev;
                  return rest;
                }
                return { ...prev, symbol: v };
              })}
            />
            <Select
              placeholder="券商/来源"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: 170 }}
              options={sourceOptions}
              onChange={(v) => setFilters((prev) => {
                if (!v) {
                  const { source_keyword, ...rest } = prev;
                  return rest;
                }
                return { ...prev, source_keyword: v };
              })}
            />
          </Space>
        </Col>
      </Row>

      {stats.total > 0 && (
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
                valueStyle={{ color: stats.total_pnl >= 0 ? '#cf1322' : '#3f8600' }} />
            </Card>
          </Col>
          <Col span={6}>
            <Card><Statistic title="盈亏比" value={stats.profit_loss_ratio} precision={2} /></Card>
          </Col>
        </Row>
      )}

      {stats.total > 0 && (
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="平均盈利" value={stats.avg_win} precision={2} valueStyle={{ color: '#cf1322' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="平均亏损" value={stats.avg_loss} precision={2} valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="最大连胜" value={stats.max_consecutive_wins} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="最大连亏" value={stats.max_consecutive_losses} /></Card>
        </Col>
      </Row>
      )}

      <Card title="当前持仓（每品种唯一）" style={{ marginBottom: 24 }}>
        <Table
          rowKey="key"
          columns={positionColumns}
          dataSource={positionData}
          pagination={false}
          locale={{ emptyText: '当前无持仓' }}
          size="small"
        />
      </Card>

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
              <Line type="monotone" dataKey="daily_pnl" name="日盈亏" stroke="#cf1322" strokeWidth={1} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <Row gutter={16} style={{ marginBottom: 24 }}>
        {symbolPnlData.length > 0 && (
          <Col span={12}>
            <Card title="品种盈亏">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={symbolPnlData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="symbol_label" interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis />
                  <Tooltip formatter={(value, name, payload) => [value, payload?.payload?.symbol_label || name]} />
                  <Bar dataKey="pnl" name="盈亏">
                    {symbolPnlData.map((entry, i) => (
                      <Cell key={i} fill={entry.pnl >= 0 ? '#cf1322' : '#3f8600'} />
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
