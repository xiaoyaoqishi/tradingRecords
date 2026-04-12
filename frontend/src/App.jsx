import { BrowserRouter, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  OrderedListOutlined,
  FileTextOutlined,
  LogoutOutlined,
  BankOutlined,
  ProjectOutlined,
} from '@ant-design/icons';
import Dashboard from './pages/Dashboard';
import TradeList from './pages/TradeList';
import TradeForm from './pages/TradeForm';
import ReviewList from './pages/ReviewList';
import InfoMaintain from './pages/BrokerManage';
import TradePlanList from './pages/TradePlanList';
import api from './api';

const tabs = [
  { key: '/trades', icon: <OrderedListOutlined />, label: '记录' },
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/maintain', icon: <BankOutlined />, label: '信息维护' },
  { key: '/reviews', icon: <FileTextOutlined />, label: '复盘会话' },
  { key: '/plans', icon: <ProjectOutlined />, label: '计划' },
];

function IconSidebar() {
  const location = useLocation();
  const current = location.pathname;
  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (_) {
      // Ignore logout failures and continue redirecting to login.
    } finally {
      window.location.href = '/login';
    }
  };

  return (
    <div className="icon-sidebar">
      <a className="icon-sidebar-back" href="/" title="返回系统首页">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 8l-4 4 4 4M8 12h8"/>
        </svg>
      </a>
      <div className="icon-sidebar-tabs">
        {tabs.map((t) => (
          <Link key={t.key} to={t.key} className={`icon-tab ${current === t.key ? 'active' : ''}`}>
            <span className="icon-tab-icon">{t.icon}</span>
            <span className="icon-tab-label">{t.label}</span>
          </Link>
        ))}
      </div>
      <div className="icon-sidebar-bottom">
        <button type="button" className="icon-tab icon-tab-button" onClick={handleLogout} title="退出登录">
          <span className="icon-tab-icon"><LogoutOutlined /></span>
        </button>
      </div>
    </div>
  );
}

function AppLayout() {
  return (
    <div className="app-layout">
      <IconSidebar />
      <div className="app-content">
        <Routes>
          <Route path="/" element={<Navigate to="/trades" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/trades" element={<TradeList />} />
          <Route path="/trades/new" element={<TradeForm />} />
          <Route path="/trades/:id/edit" element={<TradeForm />} />
          <Route path="/maintain" element={<InfoMaintain />} />
          <Route path="/reviews" element={<ReviewList />} />
          <Route path="/plans" element={<TradePlanList />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter basename="/trading">
      <AppLayout />
    </BrowserRouter>
  );
}
