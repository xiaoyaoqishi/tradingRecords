import { Card, Col, Progress, Row, Statistic, Table, Tag } from 'antd';
import { formatFuturesSymbol } from '../../../utils/futures';

export default function CoverageAndPositions({ coverage, positions }) {
  const positionColumns = [
    {
      title: '品种',
      dataIndex: 'symbol',
      key: 'symbol',
      render: (_, r) => formatFuturesSymbol(r.symbol, r.contract),
    },
    {
      title: '方向',
      dataIndex: 'side',
      key: 'side',
      render: (v) => <Tag color={v === '做多' ? 'red' : 'green'}>{v}</Tag>,
    },
    { title: '净手数', dataIndex: 'net_quantity', key: 'net_quantity', width: 100 },
    { title: '均价', dataIndex: 'avg_open_price', key: 'avg_open_price', width: 100 },
    { title: '开仓起始日', dataIndex: 'open_since', key: 'open_since', width: 120 },
  ];

  const positionRows = (positions?.open_positions || []).map((x, idx) => ({ ...x, key: `${x.symbol}-${x.side}-${idx}` }));

  return (
    <Row gutter={[12, 12]}>
      <Col xs={24} xl={8}>
        <Card title="数据覆盖率">
          <Statistic title="TradeReview 覆盖率" value={coverage?.trade_review_rate || 0} suffix="%" precision={2} />
          <Progress percent={coverage?.trade_review_rate || 0} showInfo={false} />
          <Statistic style={{ marginTop: 12 }} title="SourceMetadata 覆盖率" value={coverage?.source_metadata_rate || 0} suffix="%" precision={2} />
          <Progress percent={coverage?.source_metadata_rate || 0} showInfo={false} />
          <div style={{ marginTop: 12, color: '#666' }}>
            <div>结构化复盘记录: {coverage?.trade_review_count || 0}</div>
            <div>显式来源记录: {coverage?.source_metadata_count || 0}</div>
            <div>Legacy来源仅回退: {coverage?.legacy_source_only_count || 0}</div>
            <div>来源缺失: {coverage?.source_missing_count || 0}</div>
          </div>
        </Card>
      </Col>
      <Col xs={24} xl={16}>
        <Card title="当前持仓视角">
          <Table
            rowKey="key"
            columns={positionColumns}
            dataSource={positionRows}
            pagination={false}
            size="small"
            locale={{ emptyText: '当前无持仓' }}
          />
        </Card>
      </Col>
    </Row>
  );
}
