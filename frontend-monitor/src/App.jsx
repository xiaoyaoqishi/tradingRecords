import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Input, message, Modal, Popconfirm, Space, Table, Tag } from 'antd';
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
  const [pwdModal, setPwdModal] = useState({ open: false, userId: null, password: '' });

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
                  <Button size="small" onClick={() => setPwdModal({ open: true, userId: r.id, password: '' })}>
                    重置密码
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Modal
        title="重置密码"
        open={pwdModal.open}
        onCancel={() => setPwdModal({ open: false, userId: null, password: '' })}
        onOk={async () => {
          if (!pwdModal.userId || !pwdModal.password.trim()) return;
          await userAdminApi.resetPassword(pwdModal.userId, { password: pwdModal.password });
          setPwdModal({ open: false, userId: null, password: '' });
          await load();
        }}
      >
        <Input.Password
          placeholder="新密码"
          value={pwdModal.password}
          onChange={(e) => setPwdModal((s) => ({ ...s, password: e.target.value }))}
        />
      </Modal>
    </Space>
  );
}

function AuditPanel() {
  const [rows, setRows] = useState([]);

  const load = async () => {
    const res = await auditApi.list({ page: 1, size: 100 });
    setRows(Array.isArray(res.data) ? res.data : []);
  };
  useEffect(() => {
    load();
  }, []);

  return (
    <Card title="浏览与操作记录">
      <Table
        rowKey="id"
        dataSource={rows}
        size="small"
        pagination={false}
        columns={[
          {
            title: '时间',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (v) => (v ? String(v).replace('T', ' ').slice(0, 19) : '-'),
          },
          { title: '用户', dataIndex: 'username', key: 'username' },
          { title: '角色', dataIndex: 'role', key: 'role' },
          { title: '类型', dataIndex: 'event_type', key: 'event_type' },
          { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
          { title: '模块', dataIndex: 'module', key: 'module' },
          { title: '详情', dataIndex: 'detail', key: 'detail', ellipsis: true },
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
