import { useState, useEffect, useCallback, useMemo } from 'react';
import IconSidebar from './components/IconSidebar';
import HomePage from './components/HomePage';
import DiaryView from './components/DiaryView';
import DocView from './components/DocView';
import TodoView from './components/TodoView';
import RecycleView from './components/RecycleView';
import SettingsModal from './components/SettingsModal';
import { notebookApi, noteApi } from './api';

function parseInitialRouteFromUrl() {
  const fallback = { tab: 'home', target: null };
  try {
    const params = new URLSearchParams(window.location.search || '');
    const tab = (params.get('tab') || '').trim();
    if (tab !== 'doc' && tab !== 'diary') return fallback;
    const rawNoteId = (params.get('noteId') || '').trim();
    const anchor = (params.get('anchor') || '').trim();
    if (!rawNoteId) {
      return { tab, target: null };
    }
    const noteId = Number(rawNoteId);
    if (!Number.isInteger(noteId) || noteId <= 0) return fallback;
    if (anchor) {
      return { tab, target: { id: noteId, anchor } };
    }
    return { tab, target: noteId };
  } catch {
    return fallback;
  }
}

export default function App() {
  const initialRoute = useMemo(() => parseInitialRouteFromUrl(), []);
  const [activeTab, setActiveTab] = useState(initialRoute.tab);
  const [notebooks, setNotebooks] = useState([]);
  const [navigateTarget, setNavigateTarget] = useState(initialRoute.target);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const targetId = (t) => (t && typeof t === 'object' ? t.id : t);
  const targetAnchor = (t) => (t && typeof t === 'object' ? (t.anchor || '') : '');

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

  const handleSidebarTabChange = async (tab) => {
    if (tab !== 'diary' && tab !== 'doc') {
      setNavigateTarget(null);
      setActiveTab(tab);
      return;
    }
    try {
      const res = await noteApi.list({ note_type: tab, page: 1, size: 80 });
      const list = Array.isArray(res.data) ? res.data : [];
      if (list.length === 0) {
        setNavigateTarget(null);
        setActiveTab(tab);
        return;
      }
      const latest = [...list].sort((a, b) => {
        const ta = new Date(a.updated_at || 0).getTime();
        const tb = new Date(b.updated_at || 0).getTime();
        return tb - ta || (b.id || 0) - (a.id || 0);
      })[0];
      setNavigateTarget(latest?.id || null);
      setActiveTab(tab);
    } catch {
      setNavigateTarget(null);
      setActiveTab(tab);
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'home':
        return <HomePage onNavigate={handleNavigate} />;
      case 'diary':
        return (
          <DiaryView
            key={`diary-${targetId(navigateTarget)}-${targetAnchor(navigateTarget)}`}
            initialNoteId={targetId(navigateTarget)}
            initialAnchor={targetAnchor(navigateTarget)}
            notebooks={notebooks}
          />
        );
      case 'doc':
        return (
          <DocView
            key={`doc-${targetId(navigateTarget)}-${targetAnchor(navigateTarget)}`}
            initialNoteId={targetId(navigateTarget)}
            initialAnchor={targetAnchor(navigateTarget)}
            notebooks={notebooks}
            onReloadNotebooks={loadNotebooks}
          />
        );
      case 'todo':
        return <TodoView onNavigate={handleNavigate} initialAction={typeof navigateTarget === 'string' ? navigateTarget : ''} />;
      case 'recycle':
        return <RecycleView onNavigate={handleNavigate} />;
      default:
        return null;
    }
  };

  return (
    <div className="app-layout">
      <IconSidebar
        activeTab={activeTab}
        onTabChange={handleSidebarTabChange}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="app-content">
        {renderContent()}
      </div>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
