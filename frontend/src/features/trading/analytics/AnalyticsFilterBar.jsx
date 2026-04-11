import { Card, Col, DatePicker, Row, Select, Space } from 'antd';

const { RangePicker } = DatePicker;

export default function AnalyticsFilterBar({
  symbolOptions,
  sourceOptions,
  filterValues,
  onSetDateRange,
  onSetSymbol,
  onSetSource,
}) {
  return (
    <Card className="analytics-filter-card">
      <Row justify="space-between" align="middle" gutter={[12, 12]}>
        <Col>
          <Space wrap>
            <RangePicker value={filterValues.dateRange} onChange={onSetDateRange} />
            <Select
              placeholder="品种"
              mode="multiple"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: 220 }}
              options={symbolOptions}
              value={filterValues.symbols}
              onChange={onSetSymbol}
            />
            <Select
              placeholder="券商来源"
              mode="multiple"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: 220 }}
              options={sourceOptions}
              value={filterValues.sources}
              onChange={onSetSource}
            />
          </Space>
        </Col>
      </Row>
    </Card>
  );
}
