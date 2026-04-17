import { useEffect, useMemo, useState } from 'react';
import { Button, Card, DatePicker, Input, message, Modal, Popconfirm, Select, Space, Table, Tag } from 'antd';
import {
  ArrowLeftOutlined,
  DesktopOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  LogoutOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { authApi, monitorApi, userAdminApi, auditApi } from './api';

const POLL_MS = 3000;

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
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    let timer = null;
    let mounted = true;
    monitorApi
      .history()
      .then((res) => {
        if (mounted) setHistory(Array.isArray(res.data) ? res.data : []);
      })
      .catch(() => {});

    const poll = () => {
      monitorApi
        .realtime()
        .then((res) => {
          if (!mounted) return;
          const next = res.data || {};
          setData(next);
          setHistory((prev) => {
            const row = {
              ts: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
              cpu: next?.cpu?.percent || 0,
              mem: next?.memory?.percent || 0,
            };
            const out = [...prev, row];
            return out.length > 180 ? out.slice(-180) : out;
          });
        })
        .catch(() => {});
    };

    poll();
    timer = setInterval(poll, POLL_MS);
    return () => {
      mounted = false;
      if (timer) clearInterval(timer);
    };
  }, []);

  if (!data) return <Card>加载服务器监控中...</Card>;
  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Card title="系统状态">
        <div>主机: {data.system?.hostname || '-'}</div>
        <div>系统: {data.system?.os || '-'}</div>
        <div>CPU: {data.cpu?.percent || 0}%</div>
        <div>内存: {data.memory?.percent || 0}%</div>
      </Card>
      <Card title="最近采样">
        <Table
          rowKey={(row) => `${row.ts}-${row.cpu}-${row.mem}`}
          dataSource={[...history].reverse().slice(0, 20)}
          size="small"
          pagination={false}
          columns={[
            { title: '时间', dataIndex: 'ts', key: 'ts' },
            { title: 'CPU%', dataIndex: 'cpu', key: 'cpu' },
            { title: '内存%', dataIndex: 'mem', key: 'mem' },
          ]}
        />
      </Card>
    </Space>
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
              title: '状态',
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
  const [editModal, setEditModal] = useState({ open: false, userId: null, username: '', role: 'user', password: '' });

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
              title: '状态',
              key: 'status',
              render: (_, r) => <Tag color={r.is_active ? 'green' : 'red'}>{r.is_active ? '启用' : '停用'}</Tag>,
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
        onCancel={() => setEditModal({ open: false, userId: null, username: '', role: 'user', password: '' })}
        onOk={async () => {
          if (!editModal.userId) return;
          const payload = { role: editModal.role };
          if (editModal.password.trim()) payload.password = editModal.password.trim();
          await userAdminApi.update(editModal.userId, payload);
          message.success('更新成功');
          setEditModal({ open: false, userId: null, username: '', role: 'user', password: '' });
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
  const [filters, setFilters] = useState({
    username: '',
    module: '',
    event_type: '',
    keyword: '',
    date_from: '',
    date_to: '',
  });

  const load = async (next = {}) => {
    const nextPage = next.page ?? page;
    const nextSize = next.size ?? size;
    setLoading(true);
    try {
      const params = { page: nextPage, size: nextSize };
      if (filters.username.trim()) params.username = filters.username.trim();
      if (filters.module.trim()) params.module = filters.module.trim();
      if (filters.event_type) params.event_type = filters.event_type;
      if (filters.keyword.trim()) params.keyword = filters.keyword.trim();
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;

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
        <DatePicker placeholder="开始日期" onChange={(_, text) => setFilters((s) => ({ ...s, date_from: text || '' }))} />
        <DatePicker placeholder="结束日期" onChange={(_, text) => setFilters((s) => ({ ...s, date_to: text || '' }))} />
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
            setFilters({ username: '', module: '', event_type: '', keyword: '', date_from: '', date_to: '' });
            setPage(1);
            await load({ page: 1 });
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
          <ArrowLeftOutlined />
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
