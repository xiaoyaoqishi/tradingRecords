import { Layout, Menu } from 'antd';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  OrderedListOutlined,
  FormOutlined,
  FileTextOutlined,
  HomeOutlined,
} from '@ant-design/icons';
import Dashboard from './pages/Dashboard';
import TradeList from './pages/TradeList';
import TradeForm from './pages/TradeForm';
import ReviewList from './pages/ReviewList';

const { Sider, Content } = Layout;

function AppLayout() {
  const location = useLocation();

  const menuItems = [
    { key: 'home', icon: <HomeOutlined />, label: <a href="/">返回首页</a> },
    { key: '/', icon: <DashboardOutlined />, label: <Link to="/">仪表盘</Link> },
    { key: '/trades', icon: <OrderedListOutlined />, label: <Link to="/trades">交易记录</Link> },
    { key: '/trades/new', icon: <FormOutlined />, label: <Link to="/trades/new">新建交易</Link> },
    { key: '/reviews', icon: <FileTextOutlined />, label: <Link to="/reviews">复盘</Link> },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible theme="dark">
        <div className="logo">交易记录系统</div>
        <Menu theme="dark" selectedKeys={[location.pathname]} items={menuItems} />
      </Sider>
      <Layout>
        <Content style={{ margin: 16, padding: 24, background: '#fff', borderRadius: 8, overflow: 'auto' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/trades" element={<TradeList />} />
            <Route path="/trades/new" element={<TradeForm />} />
            <Route path="/trades/:id/edit" element={<TradeForm />} />
            <Route path="/reviews" element={<ReviewList />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter basename="/trading">
      <AppLayout />
    </BrowserRouter>
  );
}
