import { useState, useEffect } from 'react';
import { Table, Button, Space, Tag, Popconfirm, message, DatePicker, Select, Row, Col, Modal, Input, Alert, Segmented, Card, AutoComplete } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ImportOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { tradeApi } from '../api';
import { formatFuturesSymbol, FUTURES_SYMBOL_OPTIONS } from '../utils/futures';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;

function parseSourceFromNotes(notes = '') {
  const text = String(notes || '');
  const mBroker = text.match(/来源券商:\s*([^|]+)/);
  const mSource = text.match(/来源:\s*([^|]+)/);
  const broker = mBroker ? mBroker[1].trim() : '';
  const source = mSource ? mSource[1].trim() : '';
  if (broker && source) return `${broker} / ${source}`;
  return broker || source || '-';
}

export default function TradeList() {
  const [trades, setTrades] = useState([]);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [filters, setFilters] = useState({});
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [importOpen, setImportOpen] = useState(false);
  const [importBroker, setImportBroker] = useState('宏源期货');
  const [sourceOptions, setSourceOptions] = useState([]);
  const [importText, setImportText] = useState('');
  const [importResult, setImportResult] = useState(null);
  const [viewMode, setViewMode] = useState('fills');
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [batchEditOpen, setBatchEditOpen] = useState(false);
  const [batchPatch, setBatchPatch] = useState({
    status: '',
    strategy_type: '',
    is_planned: '',
    notes: '',
  });
  const navigate = useNavigate();

  useEffect(() => {
    if (viewMode === 'fills') {
      loadTrades();
    } else {
      loadPositions();
    }
  }, [filters, pagination.current, pagination.pageSize, viewMode]);

  useEffect(() => {
    loadSources();
  }, []);

  const loadSources = async () => {
    try {
      const res = await tradeApi.sources();
      const items = res.data?.items || [];
      setSourceOptions(items.map((v) => ({ label: v, value: v })));
    } catch {
      setSourceOptions([]);
    }
  };

  const loadTrades = async () => {
    setLoading(true);
    try {
      const countRes = await tradeApi.count(filters);
      const total = countRes.data?.total || 0;
      const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize));
      const current = Math.min(pagination.current, maxPage);
      const listRes = await tradeApi.list({ page: current, size: pagination.pageSize, ...filters });
      const list = listRes.data || [];
      setTrades(list);
      setPagination((p) => ({ ...p, current, total }));
      setSelectedRowKeys((prev) => prev.filter((id) => list.some((x) => x.id === id)));
    } catch { message.error('加载失败'); }
    setLoading(false);
  };

  const loadPositions = async () => {
    setLoading(true);
    try {
      const res = await tradeApi.positions(filters);
      setPositions(res.data || []);
    } catch {
      message.error('加载持仓失败');
    }
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
        setPagination((p) => ({ ...p, current: 1 }));
        return rest;
      }
      setPagination((p) => ({ ...p, current: 1 }));
      return { ...prev, [key]: val };
    });
  };

  const columns = [
    {
      title: '开仓时间', dataIndex: 'open_time', width: 170,
      render: (v, r) => {
        const d = v || r.trade_date;
        return d ? dayjs(d).format('YYYY-MM-DD') : '-';
      },
      sorter: (a, b) => (new Date(a.open_time || 0).getTime() - new Date(b.open_time || 0).getTime()),
    },
    { title: '类型', dataIndex: 'instrument_type', width: 90 },
    {
      title: '品种', dataIndex: 'symbol', width: 160,
      render: (_, r) => formatFuturesSymbol(r.symbol, r.contract),
    },
    { title: '合约', dataIndex: 'contract', width: 100 },
    {
      title: '方向', dataIndex: 'direction', width: 70,
      render: v => <Tag color={v === '做多' ? 'red' : 'green'}>{v}</Tag>,
    },
    { title: '开仓价', dataIndex: 'open_price', width: 100 },
    { title: '平仓价', dataIndex: 'close_price', width: 100 },
    {
      title: '平仓时间', dataIndex: 'close_time', width: 120,
      render: (v, r) => {
        if (v) return dayjs(v).format('YYYY-MM-DD');
        if (r.status === 'closed' && r.trade_date) return dayjs(r.trade_date).format('YYYY-MM-DD');
        return '-';
      },
    },
    { title: '手数', dataIndex: 'quantity', width: 70 },
    {
      title: '盈亏', dataIndex: 'pnl', width: 100,
      render: v => v != null
        ? <span style={{ color: v >= 0 ? '#cf1322' : '#3f8600', fontWeight: 'bold' }}>{v.toFixed(2)}</span>
        : '-',
      sorter: (a, b) => (a.pnl || 0) - (b.pnl || 0),
    },
    {
      title: '状态', dataIndex: 'status', width: 70,
      render: v => <Tag color={v === 'closed' ? 'default' : 'processing'}>{v === 'closed' ? '已平' : '持仓'}</Tag>,
    },
    {
      title: '券商/来源', dataIndex: 'notes', width: 170,
      render: (v) => parseSourceFromNotes(v),
      ellipsis: true,
    },
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

  const positionColumns = [
    { title: '品种', dataIndex: 'symbol_label', width: 220 },
    {
      title: '方向', dataIndex: 'side', width: 90,
      render: (v) => <Tag color={v === '做多' ? 'red' : 'green'}>{v}</Tag>,
    },
    { title: '净手数', dataIndex: 'net_quantity', width: 100 },
    { title: '持仓均价', dataIndex: 'avg_open_price', width: 120 },
    { title: '开仓起始日', dataIndex: 'open_since', width: 120 },
    { title: '最近成交日', dataIndex: 'last_trade_date', width: 120 },
  ];
  const positionData = positions.map((p, idx) => ({
    key: `${p.symbol}-${p.side}-${idx}`,
    ...p,
    symbol_label: formatFuturesSymbol(p.symbol, p.contract),
  }));

  const handleImport = async () => {
    if (!importText.trim()) {
      message.warning('请先粘贴数据');
      return;
    }
    setImportLoading(true);
    try {
      const res = await tradeApi.importPaste({ raw_text: importText, broker: importBroker });
      setImportResult(res.data || null);
      message.success(`导入完成：新增 ${res.data?.inserted || 0}，跳过 ${res.data?.skipped || 0}`);
      loadTrades();
    } catch (e) {
      message.error(e.response?.data?.detail || '导入失败');
    } finally {
      setImportLoading(false);
    }
  };

  const openImportModal = () => {
    setImportText('');
    setImportResult(null);
    if (!importBroker) setImportBroker('');
    setImportOpen(true);
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return;
    }
    try {
      await Promise.all(selectedRowKeys.map((id) => tradeApi.delete(id)));
      message.success(`已删除 ${selectedRowKeys.length} 条`);
      setSelectedRowKeys([]);
      loadTrades();
    } catch {
      message.error('批量删除失败');
    }
  };

  const openBatchEdit = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return;
    }
    setBatchPatch({ status: '', strategy_type: '', is_planned: '', notes: '' });
    setBatchEditOpen(true);
  };

  const handleBatchEditSubmit = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先勾选交易记录');
      return;
    }
    const patch = {};
    if (batchPatch.status) patch.status = batchPatch.status;
    if (batchPatch.strategy_type.trim()) patch.strategy_type = batchPatch.strategy_type.trim();
    if (batchPatch.is_planned === 'true') patch.is_planned = true;
    if (batchPatch.is_planned === 'false') patch.is_planned = false;
    if (batchPatch.notes.trim()) patch.notes = batchPatch.notes.trim();
    if (Object.keys(patch).length === 0) {
      message.warning('请至少填写一个要批量修改的字段');
      return;
    }
    try {
      await Promise.all(selectedRowKeys.map((id) => tradeApi.update(id, patch)));
      message.success(`已批量更新 ${selectedRowKeys.length} 条`);
      setBatchEditOpen(false);
      loadTrades();
    } catch (e) {
      message.error(e.response?.data?.detail || '批量更新失败');
    }
  };

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><h2 style={{ margin: 0 }}>交易记录</h2></Col>
        <Col>
          <Space>
            <Button icon={<ImportOutlined />} onClick={openImportModal}>粘贴导入</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/trades/new')}>新建交易</Button>
          </Space>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
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
              <Space>
                <Button onClick={openBatchEdit}>批量修改</Button>
                <Popconfirm title={`确认删除已勾选的 ${selectedRowKeys.length} 条记录？`} onConfirm={handleBatchDelete}>
                  <Button danger>批量删除</Button>
                </Popconfirm>
                <span style={{ color: '#888', fontSize: 12 }}>已勾选 {selectedRowKeys.length} 条</span>
              </Space>
            </Col>
          )}
          {viewMode === 'fills' && (
            <Col>
              <Space wrap>
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
                <Select
                  placeholder="品种"
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  style={{ width: 170 }}
                  options={FUTURES_SYMBOL_OPTIONS}
                  onChange={v => updateFilter('symbol', v)}
                />
                <Select
                  placeholder="券商/来源"
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  style={{ width: 170 }}
                  options={sourceOptions}
                  onChange={v => updateFilter('source_keyword', v)}
                />
                <Select placeholder="方向" allowClear style={{ width: 100 }}
                  options={[{ label: '做多', value: '做多' }, { label: '做空', value: '做空' }]}
                  onChange={v => updateFilter('direction', v)} />
                <Select placeholder="状态" allowClear style={{ width: 100 }}
                  options={[{ label: '持仓', value: 'open' }, { label: '已平', value: 'closed' }]}
                  onChange={v => updateFilter('status', v)} />
              </Space>
            </Col>
          )}
        </Row>
      </Card>

      {viewMode === 'fills' ? (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={trades}
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
          }}
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50', '100'],
            onChange: (page, pageSize) => setPagination((p) => ({ ...p, current: page, pageSize })),
            showTotal: (t) => `共 ${t} 条`,
          }}
          size="middle"
        />
      ) : (
        <Table
          rowKey="key"
          columns={positionColumns}
          dataSource={positionData}
          loading={loading}
          pagination={false}
          size="middle"
          locale={{ emptyText: '当前无持仓' }}
        />
      )}

      <Modal
        title="粘贴导入期货交易"
        open={importOpen}
        onCancel={() => setImportOpen(false)}
        onOk={handleImport}
        okText="开始导入"
        cancelText="取消"
        confirmLoading={importLoading}
        width={860}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Alert
            type="info"
            showIcon
            message="直接从 Excel 复制 10 列数据后粘贴即可"
            description="列顺序：交易日期、合约、买/卖、投机（一般）/套保/套利、成交价、手数、成交额、开/平、手续费、平仓盈亏"
          />
          <AutoComplete
            value={importBroker}
            onChange={setImportBroker}
            style={{ width: 260 }}
            options={sourceOptions}
            placeholder="券商名称（支持自定义）"
          />
          <Input.TextArea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder="在 Excel 中选中含表头或不含表头的数据区域，复制后粘贴到这里"
            autoSize={{ minRows: 12, maxRows: 22 }}
          />
          {importResult && (
            <div style={{ fontSize: 13 }}>
              <div>新增：{importResult.inserted}，跳过重复：{importResult.skipped}，错误：{importResult.errors?.length || 0}</div>
              {(importResult.errors?.length || 0) > 0 && (
                <div style={{ marginTop: 8, maxHeight: 180, overflowY: 'auto', background: '#fafafa', border: '1px solid #eee', padding: 8 }}>
                  {importResult.errors.slice(0, 30).map((er, i) => (
                    <div key={i}>第{er.row}行：{er.reason}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Space>
      </Modal>

      <Modal
        title={`批量修改（${selectedRowKeys.length} 条）`}
        open={batchEditOpen}
        onCancel={() => setBatchEditOpen(false)}
        onOk={handleBatchEditSubmit}
        okText="应用修改"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Select
            value={batchPatch.status}
            onChange={(v) => setBatchPatch((p) => ({ ...p, status: v }))}
            placeholder="状态（不改可留空）"
            allowClear
            options={[
              { label: '持仓', value: 'open' },
              { label: '已平', value: 'closed' },
            ]}
          />
          <Input
            value={batchPatch.strategy_type}
            onChange={(e) => setBatchPatch((p) => ({ ...p, strategy_type: e.target.value }))}
            placeholder="策略类型（不改可留空）"
          />
          <Select
            value={batchPatch.is_planned}
            onChange={(v) => setBatchPatch((p) => ({ ...p, is_planned: v }))}
            placeholder="计划内（不改可留空）"
            allowClear
            options={[
              { label: '是', value: 'true' },
              { label: '否', value: 'false' },
            ]}
          />
          <Input.TextArea
            value={batchPatch.notes}
            onChange={(e) => setBatchPatch((p) => ({ ...p, notes: e.target.value }))}
            placeholder="备注（不改可留空）"
            autoSize={{ minRows: 3, maxRows: 6 }}
          />
        </Space>
      </Modal>
    </div>
  );
}
