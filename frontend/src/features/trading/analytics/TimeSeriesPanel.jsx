import { useMemo, useState } from 'react';
import { Card, Col, Empty, Row, Segmented } from 'antd';
import {
  ResponsiveContainer,
  LineChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Line,
  BarChart,
  Bar,
} from 'recharts';

export default function TimeSeriesPanel({ series }) {
  const [granularity, setGranularity] = useState('daily');
  const currentData = useMemo(() => series?.[granularity] || [], [series, granularity]);

  return (
    <Card
      title="时间维度（收益与频率）"
      extra={
        <Segmented
          value={granularity}
          onChange={setGranularity}
          options={[
            { label: '日', value: 'daily' },
            { label: '周', value: 'weekly' },
            { label: '月', value: 'monthly' },
          ]}
        />
      }
    >
      {currentData.length === 0 ? (
        <Empty description="暂无时间序列数据" />
      ) : (
        <Row gutter={12}>
          <Col xs={24} lg={14}>
            <div className="analytics-chart-box">
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={currentData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="total_pnl" name="盈亏" stroke="#1677ff" strokeWidth={2} />
                  <Line type="monotone" dataKey="win_rate" name="胜率(%)" stroke="#52c41a" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Col>
          <Col xs={24} lg={10}>
            <div className="analytics-chart-box">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={currentData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="trade_count" name="交易数" fill="#722ed1" />
                  <Bar dataKey="win_count" name="盈利笔数" fill="#52c41a" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Col>
        </Row>
      )}
    </Card>
  );
}
