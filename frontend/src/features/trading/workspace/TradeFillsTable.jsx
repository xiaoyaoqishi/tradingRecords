import { Button, Popconfirm, Rate, Space, Table, Tag } from 'antd';
import { DeleteOutlined, EditOutlined, EyeOutlined, StarFilled, StarOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { formatInstrumentDisplay } from '../display';

export default function TradeFillsTable({
  rows,
  loading,
  pagination,
  selectedRowKeys,
  onSelectionChange,
  onPageChange,
  onOpenDetail,
  onOpenEdit,
  onDelete,
}) {
  const columns = [
    {
      title: '开仓时间',
      dataIndex: 'open_time',
      width: 130,
      render: (v, r) => {
        const d = v || r.trade_date;
        return d ? dayjs(d).format('YYYY-MM-DD') : '-';
      },
      sorter: (a, b) => new Date(a.open_time || 0).getTime() - new Date(b.open_time || 0).getTime(),
    },
    { title: '类型', dataIndex: 'instrument_type', width: 80 },
    {
      title: '品种',
      dataIndex: 'symbol',
      width: 150,
      render: (_, r) => formatInstrumentDisplay(r.symbol, r.contract),
    },
    { title: '合约', dataIndex: 'contract', width: 90 },
    {
      title: '方向',
      dataIndex: 'direction',
      width: 70,
      render: (v) => <Tag color={v === '做多' ? 'red' : 'green'}>{v}</Tag>,
    },
    { title: '开仓价', dataIndex: 'open_price', width: 90 },
    { title: '平仓价', dataIndex: 'close_price', width: 90 },
    {
      title: '平仓时间',
      dataIndex: 'close_time',
      width: 120,
      render: (v, r) => {
        if (v) return dayjs(v).format('YYYY-MM-DD');
        if (r.status === 'closed' && r.trade_date) return dayjs(r.trade_date).format('YYYY-MM-DD');
        return '-';
      },
    },
    { title: '手数', dataIndex: 'quantity', width: 65 },
    {
      title: '盈亏',
      dataIndex: 'pnl',
      width: 95,
      render: (v) =>
        v != null ? (
          <span style={{ color: v >= 0 ? '#cf1322' : '#3f8600', fontWeight: 'bold' }}>{v.toFixed(2)}</span>
        ) : (
          '-'
        ),
      sorter: (a, b) => (a.pnl || 0) - (b.pnl || 0),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 70,
      render: (v) => <Tag color={v === 'closed' ? 'default' : 'processing'}>{v === 'closed' ? '已平' : '持仓'}</Tag>,
    },
    {
      title: '计划情况',
      dataIndex: 'is_planned',
      width: 90,
      render: (v) => (v ? <Tag color="green">已计划</Tag> : <Tag color="default">未计划</Tag>),
    },
    {
      title: '复盘',
      width: 80,
      render: (_, r) => (r.has_trade_review ? <Tag color="green">已录入</Tag> : <Tag>未录入</Tag>),
    },
    {
      title: '收藏',
      width: 70,
      render: (_, r) => (r.is_favorite ? <StarFilled style={{ color: '#f5a623' }} /> : <StarOutlined style={{ color: '#cfcfcf' }} />),
    },
    {
      title: '星级',
      width: 130,
      render: (_, r) => <Rate disabled allowHalf={false} value={r.star_rating || 0} />,
    },
    {
      title: '操作',
      width: 170,
      fixed: 'right',
      render: (_, r) => (
        <Space size={2}>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => onOpenDetail(r.id)}>
            详情
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => onOpenEdit(r.id)} />
          <Popconfirm title="确定删除？" onConfirm={() => onDelete(r.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      rowKey="id"
      columns={columns}
      dataSource={rows}
      rowSelection={{
        selectedRowKeys,
        onChange: onSelectionChange,
      }}
      loading={loading}
      scroll={{ x: 1500 }}
      pagination={{
        ...pagination,
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50', '100'],
        onChange: onPageChange,
        showTotal: (t) => `共 ${t} 条`,
      }}
      size="middle"
    />
  );
}
