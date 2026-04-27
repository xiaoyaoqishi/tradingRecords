import { useEffect, useMemo, useRef, useState } from 'react';
import dayjs from 'dayjs';
import { Alert, Badge, Button, Card, DatePicker, Empty, Input, message, Modal, Popconfirm, Progress, Select, Space, Switch, Table, Tag, Typography } from 'antd';
import {
  DesktopOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  LogoutOutlined,
  ReloadOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { authApi, monitorApi, userAdminApi, auditApi } from './api';

const POLL_MS = 3000;
const MODULE_OPTIONS = [
  { label: '交易模块', value: 'trading' },
  { label: '笔记模块', value: 'notes' },
  { label: '账务模块', value: 'ledger' },
];
const DEFAULT_MODULES = MODULE_OPTIONS.map((x) => x.value);
const DEFAULT_DATA_PERMISSIONS = { trading: 'read_write', notes: 'read_write', ledger: 'read_write' };
const EMPTY_FILTERS = {
  username: '',
  module: '',
  event_type: '',
  keyword: '',
  date_from: '',
  date_to: '',
};
const { Paragraph } = Typography;

function getUsageLevel(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '暂无数据';
  if (value < 60) return '正常';
  if (value < 80) return '偏高';
  return '危险';
}

function getUsageColor(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '#94a3b8';
  if (value < 60) return '#4f8a5b';
  if (value < 80) return '#c48a36';
  return '#c45c5c';
}

function formatPercent(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '暂无数据';
  return `${Math.round(value)}%`;
}

function formatTime(value) {
  if (!value) return '--';
  if (typeof value === 'string' && /^\d{2}:\d{2}:\d{2}$/.test(value)) return value;
  const parsed = dayjs(value);
  if (!parsed.isValid()) return String(value);
  return parsed.format('YYYY-MM-DD HH:mm:ss');
}

function formatDuration(seconds) {
  if (typeof seconds !== 'number' || Number.isNaN(seconds) || seconds < 0) return '暂无数据';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}天 ${hours}小时 ${minutes}分钟`;
  if (hours > 0) return `${hours}小时 ${minutes}分钟`;
  return `${minutes}分钟`;
}

function useAdminGuard() {
  const [ready, setReady] = useState(false);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    let mounted = true;
    authApi
      .check()
      .then((res) => {
        if (!mounted) return;
        const data = res.data || {};
        if (!data.authenticated || !data.is_admin) {
          window.location.href = '/';
          return;
        }
        setOk(true);
        setReady(true);
      })
      .catch(() => {
        window.location.href = '/login';
      });
    return () => {
      mounted = false;
    };
  }, []);

  return { ready, ok };
}

function ServerPanel() {
  const mountedRef = useRef(false);
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState({ realtime: '', history: '' });
  const [lastRefreshAt, setLastRefreshAt] = useState('');
  const [online, setOnline] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const pushHistoryRow = (next) => {
    const row = {
      ts: next?.sampled_at ? dayjs(next.sampled_at).format('HH:mm:ss') : new Date().toLocaleTimeString('zh-CN', { hour12: false }),
      cpu: Number(next?.cpu?.percent || 0),
      mem: Number(next?.memory?.percent || 0),
    };
    setHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.ts === row.ts && last.cpu === row.cpu && last.mem === row.mem) return prev;
      const out = [...prev, row];
      return out.length > 180 ? out.slice(-180) : out;
    });
  };

  const loadHistory = async () => {
    try {
      const res = await monitorApi.history();
      if (!mountedRef.current) return;
      setHistory(Array.isArray(res.data) ? res.data : []);
      setError((prev) => ({ ...prev, history: '' }));
    } catch (err) {
      if (!mountedRef.current) return;
      setError((prev) => ({ ...prev, history: '最近采样加载失败，请稍后重试。' }));
    }
  };

  const loadRealtime = async () => {
    try {
      const res = await monitorApi.realtime();
      if (!mountedRef.current) return;
      const next = res.data || {};
      setData(next);
      setOnline(true);
      setLastRefreshAt(next.sampled_at || next.system?.time || new Date().toISOString());
      setError((prev) => ({ ...prev, realtime: '' }));
      pushHistoryRow(next);
    } catch (err) {
      if (!mountedRef.current) return;
      setOnline(false);
      setError((prev) => ({ ...prev, realtime: '实时状态获取失败，正在继续自动轮询。' }));
    }
  };

  const loadAll = async ({ withSpinner = false } = {}) => {
    if (withSpinner) setRefreshing(true);
    try {
      await Promise.allSettled([loadHistory(), loadRealtime()]);
    } finally {
      if (mountedRef.current) setRefreshing(false);
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    loadAll();
    const timer = setInterval(() => {
      loadRealtime();
    }, POLL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trendData = useMemo(
    () =>
      history.slice(-30).map((item, index) => ({
        key: `${item.ts || index}-${index}`,
        ts: formatTime(item.ts),
        cpu: Number(item.cpu || 0),
        mem: Number(item.mem || 0),
      })),
    [history]
  );

  const cpuPercent = typeof data?.cpu?.percent === 'number' ? data.cpu.percent : null;
  const memoryPercent = typeof data?.memory?.percent === 'number' ? data.memory.percent : null;
  const diskPercent = typeof data?.disk_percent === 'number'
    ? data.disk_percent
    : typeof data?.disk?.partitions?.[0]?.percent === 'number'
      ? data.disk.partitions[0].percent
      : null;
  const loadRatioPercent =
    typeof data?.load_avg?.['1m'] === 'number' && Number(data?.cpu?.cores_logical || 0) > 0
      ? (data.load_avg['1m'] / Number(data.cpu.cores_logical)) * 100
      : typeof data?.cpu?.load_1 === 'number' && Number(data?.cpu?.cores_logical || 0) > 0
        ? (data.cpu.load_1 / Number(data.cpu.cores_logical)) * 100
        : null;

  const metricItems = [
    {
      key: 'cpu',
      title: 'CPU 使用率',
      value: formatPercent(cpuPercent),
      percent: cpuPercent,
      note: `逻辑核心 ${data?.cpu?.cores_logical || '--'}，${getUsageLevel(cpuPercent)}运行区间`,
    },
    {
      key: 'memory',
      title: '内存使用率',
      value: formatPercent(memoryPercent),
      percent: memoryPercent,
      note: data?.memory?.used_fmt && data?.memory?.total_fmt ? `${data.memory.used_fmt} / ${data.memory.total_fmt}` : '暂未返回内存详情',
    },
    {
      key: 'disk',
      title: '磁盘使用率',
      value: formatPercent(diskPercent),
      percent: diskPercent,
      note:
        typeof data?.disk_used_gb === 'number' && typeof data?.disk_total_gb === 'number'
          ? `${data.disk_used_gb.toFixed(1)} GB / ${data.disk_total_gb.toFixed(1)} GB`
          : '暂无数据',
    },
    {
      key: 'load',
      title: '系统负载',
      value:
        typeof data?.load_avg?.['1m'] === 'number'
          ? data.load_avg['1m'].toFixed(2)
          : typeof data?.cpu?.load_1 === 'number'
            ? data.cpu.load_1.toFixed(2)
            : '暂无数据',
      percent: loadRatioPercent,
      note:
        typeof data?.load_avg?.['5m'] === 'number' && typeof data?.load_avg?.['15m'] === 'number'
          ? `5m ${data.load_avg['5m'].toFixed(2)} / 15m ${data.load_avg['15m'].toFixed(2)}`
          : '暂无数据',
    },
  ];

  const sampleColumns = [
    {
      title: '时间',
      dataIndex: 'ts',
      key: 'ts',
      render: (value) => formatTime(value),
    },
    {
      title: 'CPU%',
      dataIndex: 'cpu',
      key: 'cpu',
      render: (value) => (
        <div className="sample-metric-cell">
          <Progress percent={Math.max(0, Math.min(100, Number(value || 0)))} size="small" strokeColor={getUsageColor(Number(value || 0))} showInfo={false} />
          <Tag bordered={false} color={getUsageLevel(Number(value || 0)) === '危险' ? 'error' : getUsageLevel(Number(value || 0)) === '偏高' ? 'warning' : 'success'}>
            {formatPercent(Number(value || 0))}
          </Tag>
        </div>
      ),
    },
    {
      title: '内存%',
      dataIndex: 'mem',
      key: 'mem',
      render: (value) => (
        <div className="sample-metric-cell">
          <Progress percent={Math.max(0, Math.min(100, Number(value || 0)))} size="small" strokeColor={getUsageColor(Number(value || 0))} showInfo={false} />
          <Tag bordered={false} color={getUsageLevel(Number(value || 0)) === '危险' ? 'error' : getUsageLevel(Number(value || 0)) === '偏高' ? 'warning' : 'success'}>
            {formatPercent(Number(value || 0))}
          </Tag>
        </div>
      ),
    },
  ];

  return (
    <div className="server-monitor-page">
      {error.realtime ? <Alert type="error" showIcon message={error.realtime} style={{ marginBottom: 12 }} /> : null}
      {error.history ? <Alert type="error" showIcon message={error.history} style={{ marginBottom: 12 }} /> : null}

      <Card className="monitor-hero" bordered={false}>
        <div className="monitor-hero-main">
          <span className="monitor-hero-kicker">Operations Console</span>
          <h2>服务器监控</h2>
          <p>实时查看主机运行状态、资源使用率与最近采样趋势</p>
        </div>
        <div className="monitor-hero-actions">
          <div className="hero-badge-row">
            <Badge status={online === false ? 'error' : online ? 'success' : 'processing'} text={online === false ? '离线' : online ? '在线' : '连接中'} />
            <Tag bordered={false} color="blue">
              自动刷新 {POLL_MS / 1000} 秒
            </Tag>
          </div>
          <div className="hero-meta-item">
            <span>最近刷新时间</span>
            <strong>{formatTime(lastRefreshAt || data?.sampled_at || data?.system?.time)}</strong>
          </div>
          <Button type="primary" icon={<ReloadOutlined />} loading={refreshing} onClick={() => loadAll({ withSpinner: true })}>
            手动刷新
          </Button>
          <div className="hero-auto-refresh">自动刷新已开启，轮询间隔 {POLL_MS / 1000} 秒。</div>
        </div>
      </Card>

      <div className="metric-grid">
        {metricItems.map((item) => {
          const level = getUsageLevel(item.percent);
          const color = getUsageColor(item.percent);
          return (
            <Card key={item.key} className="metric-card" bordered={false}>
              <div className="metric-card-header">
                <span>{item.title}</span>
                <Tag bordered={false} color={level === '危险' ? 'error' : level === '偏高' ? 'warning' : level === '正常' ? 'success' : 'default'}>
                  {level}
                </Tag>
              </div>
              <div className="metric-value" style={{ color }}>
                {item.value}
              </div>
              <Progress percent={typeof item.percent === 'number' ? Math.max(0, Math.min(100, Math.round(item.percent))) : 0} strokeColor={color} showInfo={false} />
              <div className="metric-subtitle">{item.note}</div>
            </Card>
          );
        })}
      </div>

      <div className="monitor-main-grid">
        <Card className="trend-card" title="资源使用趋势" bordered={false}>
          <div className="chart-card-header">
            <span>最近 30 条采样中的 CPU / 内存变化</span>
          </div>
          <div className="mini-line-chart">
            {trendData.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={trendData} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dbe3ec" />
                  <XAxis dataKey="ts" tick={{ fill: '#66758a', fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#66758a', fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="cpu" name="CPU" stroke="#4f8a5b" strokeWidth={2.2} dot={false} />
                  <Line type="monotone" dataKey="mem" name="内存" stroke="#5278a6" strokeWidth={2.2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无采样数据" />
            )}
          </div>
        </Card>

        <Card className="host-info-card" title="主机信息" bordered={false}>
          <div className="host-info-grid">
            <div className="host-info-item">
              <span>主机名</span>
              <strong>{data?.system?.hostname || '--'}</strong>
            </div>
            <div className="host-info-item host-info-item-wide">
              <span>操作系统</span>
              <Paragraph ellipsis={{ rows: 2, tooltip: data?.system?.os || '' }}>{data?.system?.os || '--'}</Paragraph>
            </div>
            <div className="host-info-item">
              <span>平台</span>
              <strong>{data?.platform || '--'}</strong>
            </div>
            <div className="host-info-item">
              <span>架构</span>
              <strong>{data?.architecture || data?.system?.arch || '--'}</strong>
            </div>
            <div className="host-info-item">
              <span>当前采样时间</span>
              <strong>{formatTime(data?.sampled_at || data?.system?.time)}</strong>
            </div>
            <div className="host-info-item">
              <span>运行时长</span>
              <strong>{data?.system?.uptime || formatDuration(data?.uptime_seconds || data?.system?.uptime_seconds)}</strong>
            </div>
            <div className="host-info-item host-info-item-wide">
              <span>系统字符串</span>
              <Paragraph ellipsis={{ rows: 2, tooltip: data?.system?.kernel || '' }}>{data?.system?.kernel || '--'}</Paragraph>
            </div>
          </div>
        </Card>
      </div>

      <Card className="sample-table-card" title="最近采样明细" bordered={false}>
        <Table
          rowKey={(row) => `${row.ts}-${row.cpu}-${row.mem}`}
          dataSource={[...history].reverse().slice(0, 20)}
          size="small"
          pagination={false}
          columns={sampleColumns}
          locale={{ emptyText: '暂无采样数据' }}
        />
      </Card>
    </div>
  );
}

function SitePanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', url: '', enabled: true, interval_sec: 60, timeout_sec: 8 });

  const load = async () => {
    setLoading(true);
    try {
      const res = await monitorApi.listSites();
      setRows(Array.isArray(res.data) ? res.data : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const submit = async () => {
    if (!form.name.trim() || !form.url.trim()) {
      message.warning('请填写名称和 URL');
      return;
    }
    if (editing) await monitorApi.updateSite(editing.id, form);
    else await monitorApi.createSite(form);
    setEditing(null);
    setForm({ name: '', url: '', enabled: true, interval_sec: 60, timeout_sec: 8 });
    await load();
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Card title={editing ? '编辑站点' : '新增站点'}>
        <Space wrap>
          <Input
            placeholder="名称"
            value={form.name}
            onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
            style={{ width: 160 }}
          />
          <Input
            placeholder="URL (http/https)"
            value={form.url}
            onChange={(e) => setForm((s) => ({ ...s, url: e.target.value }))}
            style={{ width: 320 }}
          />
          <Input
            type="number"
            placeholder="间隔秒"
            value={form.interval_sec}
            onChange={(e) => setForm((s) => ({ ...s, interval_sec: Number(e.target.value || 60) }))}
            style={{ width: 110 }}
          />
          <Input
            type="number"
            placeholder="超时秒"
            value={form.timeout_sec}
            onChange={(e) => setForm((s) => ({ ...s, timeout_sec: Number(e.target.value || 8) }))}
            style={{ width: 110 }}
          />
          <Space size={6}>
            <span>启用</span>
            <Switch
              checked={!!form.enabled}
              checkedChildren="启用"
              unCheckedChildren="停用"
              onChange={(checked) => setForm((s) => ({ ...s, enabled: checked }))}
            />
          </Space>
          <Button type="primary" onClick={submit}>
            {editing ? '保存' : '创建'}
          </Button>
          {editing && (
            <Button
              onClick={() => {
                setEditing(null);
                setForm({ name: '', url: '', enabled: true, interval_sec: 60, timeout_sec: 8 });
              }}
            >
              取消
            </Button>
          )}
        </Space>
      </Card>
      <Card title="巡检目标">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={rows}
          size="small"
          pagination={false}
          columns={[
            { title: '名称', dataIndex: 'name', key: 'name' },
            { title: 'URL', dataIndex: 'url', key: 'url' },
            {
              title: '启用',
              key: 'enabled',
              render: (_, r) => <Tag color={r.enabled ? 'green' : 'red'}>{r.enabled ? '启用' : '停用'}</Tag>,
            },
            {
              title: '巡检',
              key: 'status',
              render: (_, r) => (
                <Tag color={r.last_ok ? 'green' : r.last_ok === false ? 'red' : 'default'}>
                  {r.last_ok ? '正常' : r.last_ok === false ? '异常' : '未检'}
                </Tag>
              ),
            },
            { title: '状态码', dataIndex: 'last_status_code', key: 'last_status_code' },
            { title: '耗时ms', dataIndex: 'last_response_ms', key: 'last_response_ms' },
            {
              title: '操作',
              key: 'op',
              render: (_, r) => (
                <Space>
                  <Button
                    size="small"
                    onClick={async () => {
                      await monitorApi.updateSite(r.id, { enabled: !r.enabled });
                      message.success(r.enabled ? '已停用站点' : '已启用站点');
                      await load();
                    }}
                  >
                    {r.enabled ? '停用' : '启用'}
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      setEditing(r);
                      setForm({
                        name: r.name,
                        url: r.url,
                        enabled: r.enabled,
                        interval_sec: r.interval_sec,
                        timeout_sec: r.timeout_sec,
                      });
                    }}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title="确认删除该站点？"
                    onConfirm={async () => {
                      await monitorApi.deleteSite(r.id);
                      await load();
                    }}
                  >
                    <Button size="small" danger>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}

function UserPanel() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ username: '', password: '' });
  const [editModal, setEditModal] = useState({
    open: false,
    userId: null,
    username: '',
    role: 'user',
    password: '',
    module_permissions: [...DEFAULT_MODULES],
    data_permissions: { ...DEFAULT_DATA_PERMISSIONS },
  });

  const load = async () => {
    const res = await userAdminApi.list();
    setRows(Array.isArray(res.data) ? res.data : []);
  };
  useEffect(() => {
    load();
  }, []);

  const createUser = async () => {
    if (!form.username.trim() || !form.password.trim()) return;
    await userAdminApi.create(form);
    setForm({ username: '', password: '' });
    message.success('创建成功');
    await load();
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Card title="新增用户">
        <Space>
          <Input
            placeholder="用户名"
            value={form.username}
            onChange={(e) => setForm((s) => ({ ...s, username: e.target.value }))}
          />
          <Input.Password
            placeholder="密码"
            value={form.password}
            onChange={(e) => setForm((s) => ({ ...s, password: e.target.value }))}
          />
          <Button type="primary" onClick={createUser}>
            创建
          </Button>
        </Space>
      </Card>
      <Card title="用户列表">
        <Table
          rowKey="id"
          dataSource={rows}
          size="small"
          pagination={false}
          columns={[
            { title: '用户名', dataIndex: 'username', key: 'username' },
            { title: '角色', dataIndex: 'role', key: 'role' },
            {
              title: '模块可见',
              key: 'module_permissions',
              render: (_, r) => {
                if ((r.role || 'user') === 'admin') return '全部';
                const modules = Array.isArray(r.module_permissions) ? r.module_permissions : [];
                if (!modules.length) return '-';
                return modules.map((m) => MODULE_OPTIONS.find((x) => x.value === m)?.label || m).join(' / ');
              },
            },
            {
              title: '数据权限',
              key: 'data_permissions',
              render: (_, r) => {
                if ((r.role || 'user') === 'admin') return '可读写';
                const perms = r.data_permissions || {};
                return DEFAULT_MODULES.map((m) => {
                  const mode = perms[m] || 'read_write';
                  const label = MODULE_OPTIONS.find((x) => x.value === m)?.label || m;
                  return `${label}:${mode === 'read_only' ? '只读' : '可读写'}`;
                }).join('；');
              },
            },
            {
              title: '状态',
              key: 'status',
              render: (_, r) => {
                return <Tag color={r.is_active ? 'green' : 'red'}>{r.is_active ? '启用' : '停用'}</Tag>;
              },
            },
            {
              title: '操作',
              key: 'op',
              render: (_, r) => (
                <Space>
                  <Button
                    size="small"
                    disabled={r.username === 'xiaoyao'}
                    onClick={async () => {
                      await userAdminApi.toggleActive(r.id);
                      await load();
                    }}
                  >
                    {r.is_active ? '停用' : '启用'}
                  </Button>
                  <Button
                    size="small"
                    onClick={() =>
                      setEditModal({
                        open: true,
                        userId: r.id,
                        username: r.username,
                        role: r.role || 'user',
                        password: '',
                        module_permissions: Array.isArray(r.module_permissions) && r.module_permissions.length
                          ? r.module_permissions
                          : [...DEFAULT_MODULES],
                        data_permissions: {
                          ...DEFAULT_DATA_PERMISSIONS,
                          ...(r.data_permissions || {}),
                        },
                      })
                    }
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title={`确认删除用户 ${r.username}？`}
                    disabled={r.username === 'xiaoyao'}
                    onConfirm={async () => {
                      await userAdminApi.remove(r.id);
                      message.success('删除成功');
                      await load();
                    }}
                  >
                    <Button size="small" danger disabled={r.username === 'xiaoyao'}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Modal
        title="编辑用户"
        open={editModal.open}
        onCancel={() =>
          setEditModal({
            open: false,
            userId: null,
            username: '',
            role: 'user',
            password: '',
            module_permissions: [...DEFAULT_MODULES],
            data_permissions: { ...DEFAULT_DATA_PERMISSIONS },
          })
        }
        onOk={async () => {
          if (!editModal.userId) return;
          const payload = { role: editModal.role };
          if (editModal.password.trim()) payload.password = editModal.password.trim();
          if (editModal.role !== 'admin') {
            payload.module_permissions = editModal.module_permissions;
            payload.data_permissions = editModal.data_permissions;
          }
          await userAdminApi.update(editModal.userId, payload);
          message.success('更新成功');
          setEditModal({
            open: false,
            userId: null,
            username: '',
            role: 'user',
            password: '',
            module_permissions: [...DEFAULT_MODULES],
            data_permissions: { ...DEFAULT_DATA_PERMISSIONS },
          });
          await load();
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={10}>
          <Input value={editModal.username} disabled />
          <Select
            value={editModal.role}
            onChange={(v) => setEditModal((s) => ({ ...s, role: v }))}
            options={[
              { label: '管理员', value: 'admin' },
              { label: '普通用户', value: 'user' },
            ]}
          />
          <Input.Password
            placeholder="新密码（留空则不修改）"
            value={editModal.password}
            onChange={(e) => setEditModal((s) => ({ ...s, password: e.target.value }))}
          />
          <Select
            mode="multiple"
            value={editModal.module_permissions}
            onChange={(vals) => setEditModal((s) => ({ ...s, module_permissions: vals }))}
            options={MODULE_OPTIONS}
            disabled={editModal.role === 'admin'}
            placeholder="模块可见权限"
          />
          <Space direction="vertical" style={{ width: '100%' }} size={6}>
            <div>数据权限</div>
            {DEFAULT_MODULES.map((moduleKey) => (
              <Space key={moduleKey} style={{ width: '100%', justifyContent: 'space-between' }}>
                <span>{MODULE_OPTIONS.find((x) => x.value === moduleKey)?.label || moduleKey}</span>
                <Select
                  value={editModal.data_permissions?.[moduleKey] || 'read_write'}
                  onChange={(v) =>
                    setEditModal((s) => ({
                      ...s,
                      data_permissions: { ...s.data_permissions, [moduleKey]: v },
                    }))
                  }
                  options={[
                    { label: '可读写', value: 'read_write' },
                    { label: '只读', value: 'read_only' },
                  ]}
                  disabled={editModal.role === 'admin'}
                  style={{ width: 160 }}
                />
              </Space>
            ))}
          </Space>
        </Space>
      </Modal>
    </Space>
  );
}

function AuditPanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS });

  const load = async (next = {}) => {
    const nextPage = next.page ?? page;
    const nextSize = next.size ?? size;
    const nextFilters = next.filters ?? filters;
    setLoading(true);
    try {
      const params = { page: nextPage, size: nextSize };
      if (nextFilters.username.trim()) params.username = nextFilters.username.trim();
      if (nextFilters.module.trim()) params.module = nextFilters.module.trim();
      if (nextFilters.event_type) params.event_type = nextFilters.event_type;
      if (nextFilters.keyword.trim()) params.keyword = nextFilters.keyword.trim();
      if (nextFilters.date_from) params.date_from = nextFilters.date_from;
      if (nextFilters.date_to) params.date_to = nextFilters.date_to;

      const res = await auditApi.list(params);
      const data = res?.data || {};
      setRows(Array.isArray(data.items) ? data.items : []);
      setTotal(Number(data.total || 0));
      setPage(Number(data.page || nextPage));
      setSize(Number(data.size || nextSize));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const removeOne = async (id) => {
    await auditApi.remove(id);
    message.success('删除成功');
    setSelectedRowKeys((prev) => prev.filter((x) => x !== id));
    await load();
  };

  const removeBatch = async () => {
    if (!selectedRowKeys.length) return;
    await Promise.all(selectedRowKeys.map((id) => auditApi.remove(id)));
    message.success(`已删除 ${selectedRowKeys.length} 条记录`);
    setSelectedRowKeys([]);
    await load();
  };

  return (
    <Card title="浏览与操作记录">
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          placeholder="按用户筛选"
          value={filters.username}
          onChange={(e) => setFilters((s) => ({ ...s, username: e.target.value }))}
          style={{ width: 140 }}
        />
        <Select
          placeholder="类型"
          value={filters.event_type || undefined}
          onChange={(v) => setFilters((s) => ({ ...s, event_type: v || '' }))}
          allowClear
          style={{ width: 120 }}
          options={[
            { label: '浏览', value: 'page_view' },
            { label: '操作', value: 'action' },
          ]}
        />
        <Select
          placeholder="模块"
          value={filters.module || undefined}
          onChange={(v) => setFilters((s) => ({ ...s, module: v || '' }))}
          allowClear
          style={{ width: 150 }}
          options={[
            { label: '登录认证', value: 'auth' },
            { label: '审计日志', value: 'audit' },
            { label: '网站监控首页', value: 'monitor_home' },
            { label: '站点巡检', value: 'monitor_site' },
            { label: '用户管理', value: 'user_admin' },
            { label: '笔记应用', value: 'notes' },
            { label: '交易记录', value: 'trading' },
          ]}
        />
        <Input
          placeholder="关键词（路径/详情）"
          value={filters.keyword}
          onChange={(e) => setFilters((s) => ({ ...s, keyword: e.target.value }))}
          style={{ width: 180 }}
        />
        <DatePicker
          placeholder="开始日期"
          value={filters.date_from ? dayjs(filters.date_from) : null}
          onChange={(_, text) => setFilters((s) => ({ ...s, date_from: text || '' }))}
        />
        <DatePicker
          placeholder="结束日期"
          value={filters.date_to ? dayjs(filters.date_to) : null}
          onChange={(_, text) => setFilters((s) => ({ ...s, date_to: text || '' }))}
        />
        <Button
          type="primary"
          onClick={async () => {
            setPage(1);
            await load({ page: 1 });
          }}
        >
          筛选
        </Button>
        <Button
          onClick={async () => {
            setFilters({ ...EMPTY_FILTERS });
            setPage(1);
            await load({ page: 1, filters: EMPTY_FILTERS });
          }}
        >
          重置
        </Button>
        <Popconfirm title={`确认删除选中的 ${selectedRowKeys.length} 条记录？`} onConfirm={removeBatch} disabled={!selectedRowKeys.length}>
          <Button danger disabled={!selectedRowKeys.length}>
            批量删除
          </Button>
        </Popconfirm>
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        size="small"
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
        }}
        pagination={{
          current: page,
          pageSize: size,
          total,
          showSizeChanger: true,
          showTotal: (n) => `共 ${n} 条`,
        }}
        onChange={(p) => {
          load({ page: p.current || 1, size: p.pageSize || 20 });
        }}
        columns={[
          {
            title: '时间',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (_, r) => r.created_at_zh || '-',
          },
          { title: '用户', dataIndex: 'username', key: 'username' },
          { title: '角色', dataIndex: 'role', key: 'role' },
          { title: '类型', dataIndex: 'event_type_zh', key: 'event_type_zh' },
          { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
          { title: '模块', dataIndex: 'module_zh', key: 'module_zh' },
          { title: '详情', dataIndex: 'detail_zh', key: 'detail_zh', ellipsis: true },
          {
            title: '操作',
            key: 'op',
            width: 88,
            render: (_, r) => (
              <Popconfirm title="确认删除该记录？" onConfirm={() => removeOne(r.id)}>
                <Button danger size="small">
                  删除
                </Button>
              </Popconfirm>
            ),
          },
        ]}
      />
    </Card>
  );
}

export default function App() {
  const { ready, ok } = useAdminGuard();
  const moduleItems = useMemo(
    () => [
      { key: 'server', label: '服务器监控', icon: <DesktopOutlined />, desc: '查看主机实时状态与采样', content: <ServerPanel /> },
      { key: 'site', label: '站点可用性巡检', icon: <GlobalOutlined />, desc: '管理巡检目标与健康状态', content: <SitePanel /> },
      { key: 'users', label: '用户管理', icon: <TeamOutlined />, desc: '创建账户、启停用与重置密码', content: <UserPanel /> },
      { key: 'audit', label: '浏览记录', icon: <FileSearchOutlined />, desc: '查看页面访问与关键操作审计', content: <AuditPanel /> },
    ],
    [],
  );
  const [activeKey, setActiveKey] = useState('server');

  useEffect(() => {
    if (!ok) return;
    auditApi.track({ path: '/monitor/', module: 'monitor_home', detail: 'open monitor app' }).catch(() => {});
  }, [ok]);

  if (!ready) return <div className="loading">正在验证管理员权限...</div>;

  const activeModule = moduleItems.find((m) => m.key === activeKey) || moduleItems[0];

  return (
    <div className="monitor-layout">
      <aside className="icon-sidebar monitor-icon-sidebar">
        <a href="/" className="icon-sidebar-back" title="返回首页">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8l-4 4 4 4M8 12h8" />
          </svg>
        </a>
        <div className="icon-sidebar-tabs">
          {moduleItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`icon-tab ${activeKey === item.key ? 'active' : ''}`}
              onClick={() => setActiveKey(item.key)}
              title={item.label}
            >
              <span className="icon-tab-icon">{item.icon}</span>
              <span className="icon-tab-label">{item.label.replace('监控', '')}</span>
            </button>
          ))}
        </div>
        <div className="icon-sidebar-bottom">
          <button
            type="button"
            className="icon-tab"
            onClick={async () => {
              await authApi.logout();
              window.location.href = '/login';
            }}
            title="退出登录"
          >
            <span className="icon-tab-icon">
              <LogoutOutlined />
            </span>
            <span className="icon-tab-label">退出</span>
          </button>
        </div>
      </aside>

      <div className="view-container monitor-view-container">
        <main className="main-content">
          <div className="monitor-main-panel">
            <header className="monitor-main-header">
              <div>
                <h1>{activeModule.label}</h1>
                <p>{activeModule.desc}</p>
              </div>
            </header>
            <div className="monitor-main-body">{activeModule.content}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
