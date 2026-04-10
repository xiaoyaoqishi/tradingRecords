import { Card, Empty, Table } from 'antd';
import { ResponsiveContainer, BarChart, CartesianGrid, XAxis, YAxis, Tooltip, Legend, Bar } from 'recharts';

export default function DimensionPanel({ title, rows, keyLabel = '维度', keyField = 'key' }) {
  const topRows = (rows || []).slice(0, 10);
  const columns = [
    { title: keyLabel, dataIndex: keyField, key: keyField, width: 180 },
    { title: '交易数', dataIndex: 'trade_count', key: 'trade_count', width: 90 },
    { title: '已平仓', dataIndex: 'closed_trade_count', key: 'closed_trade_count', width: 90 },
    { title: '胜率(%)', dataIndex: 'win_rate', key: 'win_rate', width: 90 },
    { title: '总盈亏', dataIndex: 'total_pnl', key: 'total_pnl', width: 100 },
  ];

  return (
    <Card title={title}>
      {topRows.length === 0 ? (
        <Empty description="暂无数据" />
      ) : (
        <>
          <div className="analytics-chart-box">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topRows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={keyField} interval={0} angle={-20} textAnchor="end" height={64} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="total_pnl" name="总盈亏" fill="#1677ff" />
                <Bar dataKey="trade_count" name="交易数" fill="#13c2c2" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Table
            style={{ marginTop: 12 }}
            size="small"
            rowKey={(r) => String(r[keyField])}
            columns={columns}
            dataSource={topRows}
            pagination={false}
          />
        </>
      )}
    </Card>
  );
}
