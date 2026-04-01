import { useState } from 'react';
import { Modal } from 'antd';
import { loadEditorSettings, saveEditorSettings, FONT_FAMILIES, FONT_SIZES } from './NoteEditor';

export default function SettingsModal({ open, onClose }) {
  const [settings, setSettings] = useState(() => loadEditorSettings());

  const update = (key, val) => {
    const next = { ...settings, [key]: val };
    setSettings(next);
    saveEditorSettings(next);
  };

  return (
    <Modal
      title="编辑器设置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={420}
    >
      <div className="settings-group">
        <label className="settings-label">默认字体</label>
        <div className="settings-options">
          {FONT_FAMILIES.map(f => (
            <div
              key={f.label}
              className={`settings-option ${(settings.fontFamily || '') === f.value ? 'active' : ''}`}
              style={{ fontFamily: f.value || 'inherit' }}
              onClick={() => update('fontFamily', f.value)}
            >
              {f.label}
            </div>
          ))}
        </div>
      </div>
      <div className="settings-group">
        <label className="settings-label">默认字号</label>
        <div className="settings-options">
          {FONT_SIZES.map(s => (
            <div
              key={s}
              className={`settings-option ${(settings.fontSize || '') === s ? 'active' : ''}`}
              onClick={() => update('fontSize', s)}
            >
              {s.replace('px', '')}
            </div>
          ))}
        </div>
      </div>
      <div className="settings-hint">设置会自动保存，下次打开编辑器即生效</div>
    </Modal>
  );
}
