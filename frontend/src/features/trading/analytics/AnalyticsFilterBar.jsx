import { Card, Col, DatePicker, Row, Select, Space } from 'antd';
import { FUTURES_SYMBOL_OPTIONS } from '../../../utils/futures';

const { RangePicker } = DatePicker;

export default function AnalyticsFilterBar({ sourceOptions, onSetDateRange, onSetSymbol, onSetSource }) {
  return (
    <Card className="analytics-filter-card">
      <Row justify="space-between" align="middle" gutter={[12, 12]}>
        <Col>
          <Space wrap>
            <RangePicker onChange={onSetDateRange} />
            <Select
              placeholder="品种"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: 170 }}
              options={FUTURES_SYMBOL_OPTIONS}
              onChange={onSetSymbol}
            />
            <Select
              placeholder="券商/来源"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: 190 }}
              options={sourceOptions}
              onChange={onSetSource}
            />
          </Space>
        </Col>
      </Row>
    </Card>
  );
}
