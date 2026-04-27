import { useMemo } from 'react'
import {
  BarChartOutlined,
  ImportOutlined,
  LogoutOutlined,
  SettingOutlined,
  ShopOutlined,
} from '@ant-design/icons'
import { NavLink, useLocation } from 'react-router-dom'
import { logout } from '../api/auth'

const navs = [
  { key: '/imports', label: '导入中心', icon: <ImportOutlined /> },
  { key: '/analytics', label: '基础分析', icon: <BarChartOutlined /> },
  { key: '/merchants', label: '商户词典', icon: <ShopOutlined /> },
  { key: '/rules', label: '规则管理', icon: <SettingOutlined /> },
]

export default function IconSidebar() {
  const location = useLocation()

  const current = useMemo(() => navs.find((x) => location.pathname.startsWith(x.key))?.key, [location.pathname])

  const handleLogout = async () => {
    try {
      await logout()
    } catch (_) {
      // Ignore logout errors and force redirect.
    } finally {
      window.location.href = '/login'
    }
  }

  return (
    <div className="icon-sidebar ledger-sidebar">
      <a className="icon-sidebar-back" href="/" title="返回工作台">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8l-4 4 4 4M8 12h8" />
        </svg>
      </a>
      <div className="icon-sidebar-tabs">
        {navs.map((item) => {
          const active = current === item.key
          return (
            <NavLink to={item.key} key={item.key} className={`icon-tab ${active ? 'active' : ''}`}>
              <span className="icon-tab-icon">{item.icon}</span>
              <span className="icon-tab-label">{item.label}</span>
            </NavLink>
          )
        })}
      </div>
      <div className="icon-sidebar-bottom">
        <button type="button" className="icon-tab icon-tab-button" onClick={handleLogout} title="退出登录">
          <span className="icon-tab-icon"><LogoutOutlined /></span>
        </button>
      </div>
    </div>
  )
}
