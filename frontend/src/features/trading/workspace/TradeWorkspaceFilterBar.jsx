import { Button, Card, Col, DatePicker, Popconfirm, Row, Segmented, Select, Space } from 'antd';
import { FUTURES_SYMBOL_OPTIONS } from '../../../utils/futures';

const { RangePicker } = DatePicker;

export default function TradeWorkspaceFilterBar({
  viewMode,
  setViewMode,
  selectedRowKeys,
  onOpenBatchEdit,
  onOpenBatchStructuredReview,
  onBatchDelete,
  onCreateReviewSessionFromSelected,
  onCreateReviewSessionFromFilter,
  onCreateTradePlanFromSelected,
  onSetDateRange,
  onUpdateFilter,
}) {
  return (
    <Card className="trade-filter-card">
      <Row justify="space-between" align="middle" gutter={[12, 12]}>
        <Col>
          <Segmented
            value={viewMode}
            onChange={setViewMode}
            options={[
              { label: '成交流水', value: 'fills' },
              { label: '当前持仓', value: 'positions' },
            ]}
          />
        </Col>

        {viewMode === 'fills' && (
          <Col>
            <Space wrap>
              <Button onClick={onOpenBatchEdit}>批量修改</Button>
              <Button onClick={onOpenBatchStructuredReview}>多选结构化复盘</Button>
              <Button onClick={onCreateReviewSessionFromSelected}>多选建复盘会话</Button>
              <Button onClick={onCreateReviewSessionFromFilter}>筛选结果建复盘会话</Button>
              <Button onClick={onCreateTradePlanFromSelected}>多选建交易计划</Button>
              <Popconfirm title={`确认删除已勾选的 ${selectedRowKeys.length} 条记录？`} onConfirm={onBatchDelete}>
                <Button danger>批量删除</Button>
              </Popconfirm>
              <span style={{ color: '#888', fontSize: 12 }}>已勾选 {selectedRowKeys.length} 条</span>
            </Space>
          </Col>
        )}

        {viewMode === 'fills' && (
          <Col flex="auto">
            <Space wrap className="trade-filter-controls">
              <RangePicker onChange={onSetDateRange} />
              <Select
                placeholder="交易类型"
                allowClear
                style={{ width: 120 }}
                options={['期货', '加密货币', '股票', '外汇'].map((v) => ({ label: v, value: v }))}
                onChange={(v) => onUpdateFilter('instrument_type', v)}
              />
              <Select
                placeholder="品种"
                allowClear
                showSearch
                optionFilterProp="label"
                style={{ width: 170 }}
                options={FUTURES_SYMBOL_OPTIONS}
                onChange={(v) => onUpdateFilter('symbol', v)}
              />
              <Select
                placeholder="方向"
                allowClear
                style={{ width: 100 }}
                options={[
                  { label: '做多', value: '做多' },
                  { label: '做空', value: '做空' },
                ]}
                onChange={(v) => onUpdateFilter('direction', v)}
              />
              <Select
                placeholder="状态"
                allowClear
                style={{ width: 100 }}
                options={[
                  { label: '持仓', value: 'open' },
                  { label: '已平', value: 'closed' },
                ]}
                onChange={(v) => onUpdateFilter('status', v)}
              />
              <Select
                placeholder="收藏"
                allowClear
                style={{ width: 100 }}
                options={[
                  { label: '已收藏', value: true },
                  { label: '未收藏', value: false },
                ]}
                onChange={(v) => onUpdateFilter('is_favorite', v)}
              />
              <Select
                placeholder="最低星级"
                allowClear
                style={{ width: 110 }}
                options={[1, 2, 3, 4, 5].map((x) => ({ label: `${x} 星`, value: x }))}
                onChange={(v) => onUpdateFilter('min_star_rating', v)}
              />
              <Select
                placeholder="排序"
                allowClear
                style={{ width: 130 }}
                options={[
                  { label: '最近更新', value: 'updated_at' },
                  { label: '星级', value: 'star_rating' },
                ]}
                onChange={(v) => onUpdateFilter('sort_by', v)}
              />
              <Select
                placeholder="顺序"
                style={{ width: 100 }}
                defaultValue="desc"
                options={[
                  { label: '降序', value: 'desc' },
                  { label: '升序', value: 'asc' },
                ]}
                onChange={(v) => onUpdateFilter('sort_order', v)}
              />
            </Space>
          </Col>
        )}
      </Row>
    </Card>
  );
}

