import { useState, useEffect, useRef, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import ImageExt from '@tiptap/extension-image';
import Link from '@tiptap/extension-link';
import Highlight from '@tiptap/extension-highlight';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { FontFamily } from '@tiptap/extension-font-family';
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Subscript from '@tiptap/extension-subscript';
import Superscript from '@tiptap/extension-superscript';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
import { common, createLowlight } from 'lowlight';
import { Markdown } from 'tiptap-markdown';
import MarkdownIt from 'markdown-it';
import dayjs from 'dayjs';
import api from '../api';

const lowlight = createLowlight(common);
const markdownParser = new MarkdownIt({ html: true, breaks: true, linkify: true });

const SETTINGS_KEY = 'notes-editor-settings';
export function loadEditorSettings() {
  try { return JSON.parse(localStorage.getItem(SETTINGS_KEY)) || {}; }
  catch { return {}; }
}
export function saveEditorSettings(s) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

export const FONT_SIZES = ['12px', '14px', '16px', '18px', '20px', '24px', '28px', '32px'];
export const FONT_FAMILIES = [
  { label: '默认', value: '' },
  { label: '宋体', value: 'SimSun, STSong, serif' },
  { label: '黑体', value: 'SimHei, STHeiti, sans-serif' },
  { label: '楷体', value: 'KaiTi, STKaiti, serif' },
  { label: '仿宋', value: 'FangSong, STFangsong, serif' },
  { label: '华文楷体', value: 'STKaiti, KaiTi, serif' },
  { label: 'Arial', value: 'Arial, Helvetica, sans-serif' },
  { label: 'Georgia', value: 'Georgia, serif' },
  { label: 'Courier', value: 'Courier New, monospace' },
];
const COLORS = ['#000000', '#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db', '#9b59b6', '#95a5a6', '#ffffff'];
const BG_COLORS = ['transparent', '#fef3cd', '#d4edda', '#d1ecf1', '#f8d7da', '#e2d9f3', '#fce4ec', '#fff3e0', '#e8f5e9'];
const EMOJIS = [
  '😀','😂','🥰','😎','🤔','😢','😡','🥳','👍','👎',
  '❤️','🔥','⭐','💡','📌','✅','❌','⚠️','🎯','💯',
  '📝','📖','💻','🎨','🔧','📊','🕐','☀️','🌙','🌈',
  '🚀','💰','📈','📉','🏆','🎉','👏','🤝','💪','🧠',
];
const CODE_LANGUAGES = [
  { label: '纯文本', value: null },
  { label: 'JavaScript', value: 'javascript' },
  { label: 'TypeScript', value: 'typescript' },
  { label: 'Python', value: 'python' },
  { label: 'Java', value: 'java' },
  { label: 'C/C++', value: 'cpp' },
  { label: 'Go', value: 'go' },
  { label: 'Rust', value: 'rust' },
  { label: 'SQL', value: 'sql' },
  { label: 'HTML', value: 'xml' },
  { label: 'CSS', value: 'css' },
  { label: 'JSON', value: 'json' },
  { label: 'Bash', value: 'bash' },
  { label: 'Markdown', value: 'markdown' },
];

async function uploadImage(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post('/upload', form);
  return res.data.url;
}

function Toolbar({ editor }) {
  if (!editor) return null;
  const fileRef = useRef(null);
  const [openDrop, setOpenDrop] = useState(null);

  const toggle = (name) => setOpenDrop(prev => prev === name ? null : name);
  const closeAll = () => setOpenDrop(null);

  const btn = (label, action, isActive, title) => (
    <button
      className={`toolbar-btn ${isActive ? 'is-active' : ''}`}
      onClick={() => { closeAll(); action(); }}
      title={title || label}
    >{label}</button>
  );

  const handleImageUpload = async (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    for (const file of files) {
      try {
        const url = await uploadImage(file);
        editor.chain().focus().setImage({ src: url }).run();
      } catch {}
    }
    e.target.value = '';
  };

  return (
    <div className="editor-toolbar">
      {/* Font family */}
      <div className="toolbar-dropdown-wrap">
        <button className="toolbar-btn" onClick={() => toggle('font')} title="字体">字体 ▾</button>
        {openDrop === 'font' && (
          <div className="toolbar-dropdown font-dropdown">
            {FONT_FAMILIES.map(f => (
              <div key={f.label} className="dropdown-item" style={{ fontFamily: f.value || 'inherit' }}
                onClick={() => { f.value ? editor.chain().focus().setFontFamily(f.value).run() : editor.chain().focus().unsetFontFamily().run(); closeAll(); }}>
                {f.label}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Font size */}
      <div className="toolbar-dropdown-wrap">
        <button className="toolbar-btn" onClick={() => toggle('size')} title="字号">字号 ▾</button>
        {openDrop === 'size' && (
          <div className="toolbar-dropdown">
            {FONT_SIZES.map(s => (
              <div key={s} className="dropdown-item" onClick={() => { editor.chain().focus().setMark('textStyle', { fontSize: s }).run(); closeAll(); }}>
                <span style={{ fontSize: s }}>{s.replace('px', '')}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="toolbar-divider" />

      {btn('B', () => editor.chain().focus().toggleBold().run(), editor.isActive('bold'), '加粗')}
      {btn('I', () => editor.chain().focus().toggleItalic().run(), editor.isActive('italic'), '斜体')}
      {btn('U', () => editor.chain().focus().toggleUnderline().run(), editor.isActive('underline'), '下划线')}
      {btn('S', () => editor.chain().focus().toggleStrike().run(), editor.isActive('strike'), '删除线')}
      {btn('x₂', () => editor.chain().focus().toggleSubscript().run(), editor.isActive('subscript'), '下标')}
      {btn('x²', () => editor.chain().focus().toggleSuperscript().run(), editor.isActive('superscript'), '上标')}

      {/* Text color */}
      <div className="toolbar-dropdown-wrap">
        <button className="toolbar-btn" onClick={() => toggle('color')} title="文字颜色">
          A<span style={{ display: 'block', height: 3, background: editor.getAttributes('textStyle').color || '#000', borderRadius: 1 }} />
        </button>
        {openDrop === 'color' && (
          <div className="toolbar-dropdown color-dropdown">
            {COLORS.map(c => (
              <div key={c} className="color-swatch" style={{ background: c, border: c === '#ffffff' ? '1px solid #ddd' : 'none' }}
                onClick={() => { editor.chain().focus().setColor(c).run(); closeAll(); }} />
            ))}
          </div>
        )}
      </div>

      {/* Background color */}
      <div className="toolbar-dropdown-wrap">
        <button className="toolbar-btn" onClick={() => toggle('bgcolor')} title="背景颜色">
          <span style={{ background: '#fef3cd', padding: '0 3px', borderRadius: 2 }}>A</span>
        </button>
        {openDrop === 'bgcolor' && (
          <div className="toolbar-dropdown color-dropdown">
            {BG_COLORS.map(c => (
              <div key={c} className="color-swatch"
                style={{ background: c === 'transparent' ? '#fff' : c, border: '1px solid #ddd' }}
                onClick={() => {
                  if (c === 'transparent') {
                    editor.chain().focus().unsetHighlight().run();
                  } else {
                    editor.chain().focus().toggleHighlight({ color: c }).run();
                  }
                  closeAll();
                }}
              >
                {c === 'transparent' && <span style={{ fontSize: 10 }}>✕</span>}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="toolbar-divider" />

      {btn('H1', () => editor.chain().focus().toggleHeading({ level: 1 }).run(), editor.isActive('heading', { level: 1 }))}
      {btn('H2', () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive('heading', { level: 2 }))}
      {btn('H3', () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive('heading', { level: 3 }))}
      <div className="toolbar-divider" />

      {btn('•', () => editor.chain().focus().toggleBulletList().run(), editor.isActive('bulletList'), '无序列表')}
      {btn('1.', () => editor.chain().focus().toggleOrderedList().run(), editor.isActive('orderedList'), '有序列表')}
      {btn('☑', () => editor.chain().focus().toggleTaskList().run(), editor.isActive('taskList'), '任务列表')}
      {btn('❝', () => editor.chain().focus().toggleBlockquote().run(), editor.isActive('blockquote'), '引用')}

      {/* Code block */}
      <div className="toolbar-dropdown-wrap">
        <button className={`toolbar-btn ${editor.isActive('codeBlock') ? 'is-active' : ''}`}
          onClick={() => toggle('code')} title="代码块">{'</>'}</button>
        {openDrop === 'code' && (
          <div className="toolbar-dropdown code-lang-dropdown">
            {CODE_LANGUAGES.map(l => (
              <div key={l.label} className="dropdown-item"
                onClick={() => { editor.chain().focus().toggleCodeBlock({ language: l.value }).run(); closeAll(); }}>
                {l.label}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="toolbar-divider" />

      {btn('≡左', () => editor.chain().focus().setTextAlign('left').run(), editor.isActive({ textAlign: 'left' }), '左对齐')}
      {btn('≡中', () => editor.chain().focus().setTextAlign('center').run(), editor.isActive({ textAlign: 'center' }), '居中')}
      {btn('≡右', () => editor.chain().focus().setTextAlign('right').run(), editor.isActive({ textAlign: 'right' }), '右对齐')}
      <div className="toolbar-divider" />

      {btn('表格', () => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(), false, '插入表格')}
      {editor.isActive('table') && (
        <>
          {btn('+列', () => editor.chain().focus().addColumnAfter().run(), false, '添加列')}
          {btn('+行', () => editor.chain().focus().addRowAfter().run(), false, '添加行')}
          {btn('-列', () => editor.chain().focus().deleteColumn().run(), false, '删除列')}
          {btn('-行', () => editor.chain().focus().deleteRow().run(), false, '删除行')}
          {btn('×表', () => editor.chain().focus().deleteTable().run(), false, '删除表格')}
        </>
      )}
      <div className="toolbar-divider" />

      {/* Emoji */}
      <div className="toolbar-dropdown-wrap">
        <button className="toolbar-btn" onClick={() => toggle('emoji')} title="表情">😀</button>
        {openDrop === 'emoji' && (
          <div className="toolbar-dropdown emoji-dropdown">
            {EMOJIS.map(e => (
              <span key={e} className="emoji-item"
                onClick={() => { editor.chain().focus().insertContent(e).run(); closeAll(); }}>
                {e}
              </span>
            ))}
          </div>
        )}
      </div>

      <button className="toolbar-btn" onClick={() => fileRef.current?.click()} title="上传图片">🖼</button>
      <input ref={fileRef} type="file" accept="image/*" multiple style={{ display: 'none' }} onChange={handleImageUpload} />
      {btn('🔗', () => {
        const url = prompt('输入链接 URL');
        if (url) editor.chain().focus().setLink({ href: url }).run();
      }, editor.isActive('link'), '插入链接')}
      {btn('—', () => editor.chain().focus().setHorizontalRule().run(), false, '分割线')}
    </div>
  );
}

const FontSize = TextStyle.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      fontSize: {
        default: null,
        parseHTML: el => el.style.fontSize || null,
        renderHTML: attrs => attrs.fontSize ? { style: `font-size: ${attrs.fontSize}` } : {},
      },
    };
  },
});

function unwrapMarkdownFences(md) {
  return md.replace(/```markdown\n([\s\S]*?)```/g, (_, content) => content.trimEnd());
}

function renderMdBlocksInDom(container) {
  if (!container) return;
  container.querySelectorAll('pre').forEach(pre => {
    const code = pre.querySelector('code');
    if (!code) return;
    if (!(code.className || '').includes('language-markdown')) return;
    const raw = code.textContent || '';
    const html = markdownParser.render(raw);
    const div = document.createElement('div');
    div.className = 'md-rendered-block';
    div.innerHTML = html;
    pre.replaceWith(div);
  });
}

export default function NoteEditor({ note, onUpdate, defaultEditing = false }) {
  const [title, setTitle] = useState(note?.title || '');
  const [mode, setMode] = useState(defaultEditing ? 'edit' : 'read');
  const [mdSource, setMdSource] = useState('');
  const contentRef = useRef(null);
  const settings = loadEditorSettings();

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ codeBlock: false }),
      CodeBlockLowlight.configure({ lowlight, defaultLanguage: null }),
      Markdown.configure({ html: true, transformPastedText: true, transformCopiedText: false }),
      Placeholder.configure({ placeholder: '开始写作...' }),
      Underline,
      FontSize,
      Color,
      FontFamily,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      ImageExt.configure({ allowBase64: true }),
      Link.configure({ openOnClick: false }),
      Highlight.configure({ multicolor: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      TaskList,
      TaskItem.configure({ nested: true }),
      Subscript,
      Superscript,
    ],
    content: note?.content || '',
    editable: defaultEditing,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const text = editor.getText();
      onUpdate(note.id, { content: html, word_count: text.length });
    },
    editorProps: {
      handleDrop: (view, event) => {
        const files = event.dataTransfer?.files;
        if (files?.length) {
          event.preventDefault();
          Array.from(files).forEach(async (file) => {
            if (file.type.startsWith('image/')) {
              const url = await uploadImage(file);
              editor.chain().focus().setImage({ src: url }).run();
            }
          });
          return true;
        }
        return false;
      },
      handlePaste: (view, event) => {
        const items = event.clipboardData?.items;
        if (items) {
          for (const item of items) {
            if (item.type.startsWith('image/')) {
              event.preventDefault();
              const file = item.getAsFile();
              if (file) {
                uploadImage(file).then(url => {
                  editor.chain().focus().setImage({ src: url }).run();
                });
              }
              return true;
            }
          }
        }
        return false;
      },
    },
  });

  const switchMode = useCallback((next) => {
    if (!editor) return;
    if (mode === 'markdown' && next !== 'markdown') {
      const cleaned = unwrapMarkdownFences(mdSource);
      const html = markdownParser.render(cleaned);
      editor.commands.setContent(html);
      const text = editor.getText();
      onUpdate(note.id, { content: editor.getHTML(), word_count: text.length });
    }
    if (next === 'markdown' && mode !== 'markdown') {
      const md = editor.storage.markdown?.getMarkdown?.() || editor.getText();
      setMdSource(md);
    }
    if (next === 'edit') {
      editor.setEditable(true);
      editor.chain().focus().run();
    } else {
      editor.setEditable(false);
    }
    setMode(next);
  }, [mode, editor, mdSource, note?.id, onUpdate]);

  useEffect(() => {
    setTitle(note?.title || '');
    const nextMode = defaultEditing ? 'edit' : 'read';
    setMode(nextMode);
    if (editor) {
      editor.setEditable(defaultEditing);
      const cur = editor.getHTML();
      if (cur !== (note.content || '')) {
        editor.commands.setContent(note.content || '');
      }
    }
  }, [note?.id]);

  useEffect(() => {
    if (mode === 'read') {
      const timer = setTimeout(() => renderMdBlocksInDom(contentRef.current), 50);
      return () => clearTimeout(timer);
    }
  }, [mode, note?.id]);

  const handleTitleChange = (e) => {
    const val = e.target.value;
    setTitle(val);
    onUpdate(note.id, { title: val });
  };

  const isDiary = note?.note_type === 'diary';
  const dateDisplay = note?.note_date
    ? dayjs(note.note_date).format('YYYY年M月D日 dddd')
    : '';

  const editorStyle = {};
  if (settings.fontFamily) editorStyle.fontFamily = settings.fontFamily;
  if (settings.fontSize) editorStyle.fontSize = settings.fontSize;

  return (
    <div className={`editor-panel ${mode === 'edit' ? '' : 'readonly'}`}>
      <div className="editor-header">
        <div className="editor-header-top">
          {isDiary && dateDisplay && (
            <div className="editor-date-header">📅 {dateDisplay}</div>
          )}
          <div style={{ flex: 1 }} />
          <div className="mode-toggle-group">
            <button className={`mode-btn ${mode === 'read' ? 'active' : ''}`} onClick={() => switchMode('read')} title="阅读模式">📖 阅读</button>
            <button className={`mode-btn ${mode === 'edit' ? 'active' : ''}`} onClick={() => switchMode('edit')} title="编辑模式">✏️ 编辑</button>
            <button className={`mode-btn ${mode === 'markdown' ? 'active' : ''}`} onClick={() => switchMode('markdown')} title="Markdown源码">{'</>'}Md</button>
          </div>
        </div>
        {mode === 'edit' ? (
          <input className="editor-title-input" placeholder={isDiary ? '日记标题...' : '输入标题...'} value={title} onChange={handleTitleChange} />
        ) : mode === 'markdown' ? (
          <input className="editor-title-input" placeholder={isDiary ? '日记标题...' : '输入标题...'} value={title} onChange={handleTitleChange} />
        ) : (
          <div className="editor-title-readonly">{title || '无标题'}</div>
        )}
      </div>
      {mode === 'edit' && <Toolbar editor={editor} />}
      {mode === 'markdown' ? (
        <div className="markdown-source-wrap" style={editorStyle}>
          <textarea
            className="markdown-source"
            value={mdSource}
            onChange={e => setMdSource(e.target.value)}
            placeholder="在此输入 Markdown 内容...&#10;&#10;# 标题&#10;**粗体** *斜体* ~~删除线~~&#10;- 列表项&#10;```python&#10;print('代码块')&#10;```"
          />
        </div>
      ) : (
        <div className="editor-content" style={editorStyle} ref={contentRef}>
          <EditorContent editor={editor} />
        </div>
      )}
      <div className="editor-footer">
        <span>{mode === 'markdown' ? mdSource.length : (note.word_count || 0)} 字</span>
        <span>最后编辑: {dayjs(note.updated_at).format('YYYY-MM-DD HH:mm')}</span>
      </div>
    </div>
  );
}
