import {
  HomeOutlined,
  EditOutlined,
  FileTextOutlined,
  CheckSquareOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons';

const tabs = [
  { key: 'home', icon: <HomeOutlined />, label: '首页' },
  { key: 'diary', icon: <EditOutlined />, label: '日记' },
  { key: 'doc', icon: <FileTextOutlined />, label: '文档' },
  { key: 'todo', icon: <CheckSquareOutlined />, label: '待办' },
];

export default function IconSidebar({ activeTab, onTabChange, onOpenSettings }) {
  return (
    <div className="icon-sidebar">
      <a className="icon-sidebar-back" href="/" title="返回工作台">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 8l-4 4 4 4M8 12h8"/>
        </svg>
      </a>
      <div className="icon-sidebar-tabs">
        {tabs.map(t => (
          <div
            key={t.key}
            className={`icon-tab ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => onTabChange(t.key)}
          >
            <span className="icon-tab-icon">{t.icon}</span>
            <span className="icon-tab-label">{t.label}</span>
          </div>
        ))}
      </div>
      <div className="icon-sidebar-bottom">
        <div className="icon-tab" onClick={onOpenSettings} title="设置">
          <span className="icon-tab-icon"><SettingOutlined /></span>
        </div>
        <a className="icon-tab" href="/" title="退出">
          <span className="icon-tab-icon"><LogoutOutlined /></span>
        </a>
      </div>
    </div>
  );
}
