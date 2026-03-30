import { useState, useEffect } from 'react';
import { Table, Button, Space, Tag, Popconfirm, message, DatePicker, Select, Row, Col } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { tradeApi } from '../api';

const { RangePicker } = DatePicker;

export default function TradeList() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({});
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const navigate = useNavigate();

  useEffect(() => { loadTrades(); }, [filters, pagination.current]);

  const loadTrades = async () => {
    setLoading(true);
    try {
      const res = await tradeApi.list({ page: pagination.current, size: pagination.pageSize, ...filters });
      setTrades(res.data);
    } catch { message.error('加载失败'); }
    setLoading(false);
  };

  const handleDelete = async (id) => {
    await tradeApi.delete(id);
    message.success('已删除');
    loadTrades();
  };

  const updateFilter = (key, val) => {
    setFilters(prev => {
      if (val === undefined || val === null) {
        const { [key]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [key]: val };
    });
  };

  const columns = [
    { title: '日期', dataIndex: 'trade_date', width: 110, sorter: (a, b) => a.trade_date.localeCompare(b.trade_date) },
    { title: '类型', dataIndex: 'instrument_type', width: 90 },
    { title: '品种', dataIndex: 'symbol', width: 80 },
    { title: '合约', dataIndex: 'contract', width: 100 },
    {
      title: '方向', dataIndex: 'direction', width: 70,
      render: v => <Tag color={v === '做多' ? 'red' : 'green'}>{v}</Tag>,
    },
    { title: '开仓价', dataIndex: 'open_price', width: 100 },
    { title: '平仓价', dataIndex: 'close_price', width: 100 },
    { title: '数量', dataIndex: 'quantity', width: 70 },
    {
      title: '盈亏', dataIndex: 'pnl', width: 100,
      render: v => v != null
        ? <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322', fontWeight: 'bold' }}>{v.toFixed(2)}</span>
        : '-',
      sorter: (a, b) => (a.pnl || 0) - (b.pnl || 0),
    },
    {
      title: '状态', dataIndex: 'status', width: 70,
      render: v => <Tag color={v === 'closed' ? 'default' : 'processing'}>{v === 'closed' ? '已平' : '持仓'}</Tag>,
    },
    { title: '策略', dataIndex: 'strategy_type', width: 100, ellipsis: true },
    {
      title: '计划内', dataIndex: 'is_planned', width: 70,
      render: v => v === true ? <Tag color="green">是</Tag> : v === false ? <Tag color="red">否</Tag> : '-',
    },
    {
      title: '操作', width: 100, fixed: 'right',
      render: (_, r) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => navigate(`/trades/${r.id}/edit`)} />
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><h2 style={{ margin: 0 }}>交易记录</h2></Col>
        <Col><Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/trades/new')}>新建交易</Button></Col>
      </Row>

      <Space wrap style={{ marginBottom: 16 }}>
        <RangePicker onChange={(dates) => {
          if (dates) {
            setFilters(f => ({ ...f, date_from: dates[0].format('YYYY-MM-DD'), date_to: dates[1].format('YYYY-MM-DD') }));
          } else {
            setFilters(f => { const { date_from, date_to, ...rest } = f; return rest; });
          }
        }} />
        <Select placeholder="交易类型" allowClear style={{ width: 120 }}
          options={['期货', '加密货币', '股票', '外汇'].map(v => ({ label: v, value: v }))}
          onChange={v => updateFilter('instrument_type', v)} />
        <Select placeholder="方向" allowClear style={{ width: 100 }}
          options={[{ label: '做多', value: '做多' }, { label: '做空', value: '做空' }]}
          onChange={v => updateFilter('direction', v)} />
        <Select placeholder="状态" allowClear style={{ width: 100 }}
          options={[{ label: '持仓', value: 'open' }, { label: '已平', value: 'closed' }]}
          onChange={v => updateFilter('status', v)} />
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={trades}
        loading={loading}
        scroll={{ x: 1200 }}
        pagination={{
          ...pagination,
          onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
        }}
        size="middle"
      />
    </div>
  );
}
