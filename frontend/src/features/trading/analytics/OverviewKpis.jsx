import { Card, Col, Row, Statistic } from 'antd';
import { ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons';

export default function OverviewKpis({ overview }) {
  const cards = [
    { title: '总交易数', value: overview.total_trades },
    { title: '已平仓', value: overview.closed_trades },
    { title: '持仓中', value: overview.open_trades },
    { title: '胜率', value: overview.win_rate, suffix: '%' },
    { title: '总盈亏', value: overview.total_pnl, pnl: true },
    { title: '平仓均盈亏', value: overview.avg_pnl_per_closed_trade },
    { title: '平均盈利', value: overview.avg_win },
    { title: '平均亏损', value: overview.avg_loss },
    { title: 'Profit Factor', value: overview.profit_factor },
    { title: '当前持仓品种数', value: overview.open_position_count },
  ];

  return (
    <Row gutter={[12, 12]}>
      {cards.map((c) => (
        <Col key={c.title} xs={12} sm={8} md={6} xl={4}>
          <Card className="analytics-kpi-card">
            <Statistic
              title={c.title}
              value={c.value}
              suffix={c.suffix}
              precision={typeof c.value === 'number' && !Number.isInteger(c.value) ? 2 : 0}
              prefix={
                c.pnl
                  ? c.value >= 0
                    ? <ArrowUpOutlined />
                    : <ArrowDownOutlined />
                  : undefined
              }
              valueStyle={
                c.pnl
                  ? { color: c.value >= 0 ? '#cf1322' : '#3f8600' }
                  : undefined
              }
            />
          </Card>
        </Col>
      ))}
    </Row>
  );
}
