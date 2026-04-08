import { useState, useEffect, useCallback } from 'react';
import IconSidebar from './components/IconSidebar';
import HomePage from './components/HomePage';
import DiaryView from './components/DiaryView';
import DocView from './components/DocView';
import TodoView from './components/TodoView';
import SettingsModal from './components/SettingsModal';
import { notebookApi } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [notebooks, setNotebooks] = useState([]);
  const [navigateTarget, setNavigateTarget] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const loadNotebooks = useCallback(async () => {
    try {
      const res = await notebookApi.list();
      setNotebooks(res.data);
    } catch {}
  }, []);

  useEffect(() => { loadNotebooks(); }, [loadNotebooks]);

  const handleNavigate = (tab, target) => {
    setNavigateTarget(target);
    setActiveTab(tab);
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'home':
        return <HomePage onNavigate={handleNavigate} />;
      case 'diary':
        return (
          <DiaryView
            key={`diary-${navigateTarget}`}
            initialNoteId={navigateTarget}
            notebooks={notebooks}
          />
        );
      case 'doc':
        return (
          <DocView
            key={`doc-${navigateTarget}`}
            initialNoteId={navigateTarget}
            notebooks={notebooks}
            onReloadNotebooks={loadNotebooks}
          />
        );
      case 'todo':
        return <TodoView />;
      default:
        return null;
    }
  };

  return (
    <div className="app-layout">
      <IconSidebar
        activeTab={activeTab}
        onTabChange={(tab) => { setNavigateTarget(null); setActiveTab(tab); }}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="app-content">
        {renderContent()}
      </div>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
