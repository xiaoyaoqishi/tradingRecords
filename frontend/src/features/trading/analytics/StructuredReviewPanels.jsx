import { Card, Col, Empty, Row } from 'antd';
import { ResponsiveContainer, BarChart, CartesianGrid, XAxis, YAxis, Tooltip, Legend, Bar } from 'recharts';
import { getTaxonomyLabel, TAXONOMY_FIELD_ZH } from '../localization';

const FIELDS = ['opportunity_structure', 'edge_source', 'failure_type', 'review_conclusion'];

export default function StructuredReviewPanels({ byReviewField }) {
  return (
    <Card title="结构化复盘维度（TradeReview）">
      <Row gutter={[12, 12]}>
        {FIELDS.map((field) => {
          const rows = (byReviewField?.[field] || []).map((r) => ({
            ...r,
            label_zh: getTaxonomyLabel(field, r.key),
          }));
          return (
            <Col key={field} xs={24} xl={12}>
              <Card size="small" title={TAXONOMY_FIELD_ZH[field]}>
                {rows.length === 0 ? (
                  <Empty description="暂无结构化数据" />
                ) : (
                  <div className="analytics-chart-box">
                    <ResponsiveContainer width="100%" height={260}>
                      <BarChart data={rows}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="label_zh" interval={0} angle={-18} textAnchor="end" height={72} />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="trade_count" name="交易数" fill="#722ed1" />
                        <Bar dataKey="total_pnl" name="总盈亏" fill="#1677ff" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Card>
            </Col>
          );
        })}
      </Row>
    </Card>
  );
}
