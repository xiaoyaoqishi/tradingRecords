import { Button, DatePicker, Input, Select, Space } from 'antd'
import dayjs from 'dayjs'
import { DIRECTION_OPTIONS, TRANSACTION_TYPE_OPTIONS } from '../utils/enums'

const { RangePicker } = DatePicker

export default function FilterBar({ filters, onChange, onSearch, onReset, accounts, categories, loading }) {
  const dateRange = filters.date_from && filters.date_to ? [dayjs(filters.date_from), dayjs(filters.date_to)] : null

  return (
    <div className="filter-bar">
      <Space wrap>
        <Select
          placeholder="账户"
          value={filters.account_id || undefined}
          style={{ width: 150 }}
          allowClear
          options={(accounts || []).map((x) => ({ label: x.name, value: String(x.id) }))}
          onChange={(v) => onChange({ account_id: v || '' })}
        />
        <Select
          placeholder="分类"
          value={filters.category_id || undefined}
          style={{ width: 220 }}
          allowClear
          options={(categories || []).map((x) => ({ label: x.name, value: String(x.id) }))}
          onChange={(v) => onChange({ category_id: v || '' })}
        />
        <Select
          placeholder="类型"
          value={filters.transaction_type || undefined}
          style={{ width: 140 }}
          allowClear
          options={TRANSACTION_TYPE_OPTIONS}
          onChange={(v) => onChange({ transaction_type: v || '' })}
        />
        <Select
          placeholder="方向"
          value={filters.direction || undefined}
          style={{ width: 120 }}
          allowClear
          options={DIRECTION_OPTIONS}
          onChange={(v) => onChange({ direction: v || '' })}
        />
        <Select
          placeholder="来源"
          value={filters.source || undefined}
          style={{ width: 140 }}
          allowClear
          options={[
            { label: '手工录入', value: 'manual' },
            { label: 'CSV 导入', value: 'import_csv' },
          ]}
          onChange={(v) => onChange({ source: v || '' })}
        />
        <Input
          placeholder="商户/描述/备注关键字"
          value={filters.keyword}
          style={{ width: 220 }}
          allowClear
          onChange={(e) => onChange({ keyword: e.target.value })}
        />
        <RangePicker
          value={dateRange}
          onChange={(values) => {
            if (!values || values.length !== 2) {
              onChange({ date_from: '', date_to: '' })
              return
            }
            onChange({
              date_from: values[0].format('YYYY-MM-DD'),
              date_to: values[1].format('YYYY-MM-DD'),
            })
          }}
        />
        <Button type="primary" loading={loading} onClick={onSearch}>
          查询
        </Button>
        <Button onClick={onReset}>重置</Button>
      </Space>
    </div>
  )
}
