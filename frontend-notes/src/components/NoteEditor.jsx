import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { message } from 'antd';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import ResizableImage from './ResizableImage';
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
import api, { todoApi } from '../api';

const lowlight = createLowlight(common);
const markdownParser = new MarkdownIt({ html: true, breaks: true, linkify: true });

const SETTINGS_KEY = 'notes-editor-settings';
const DEFAULT_EDITOR_SETTINGS = {
  fontFamily: 'STKaiti, KaiTi, serif',
  fontSize: '20px',
};
export function loadEditorSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY)) || {};
    return { ...DEFAULT_EDITOR_SETTINGS, ...saved };
  }
  catch { return DEFAULT_EDITOR_SETTINGS; }
}
export function saveEditorSettings(s) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...DEFAULT_EDITOR_SETTINGS, ...(s || {}) }));
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
const COLORS = [
  '#000000', '#262626', '#595959', '#8c8c8c', '#bfbfbf', '#ffffff',
  '#f5222d', '#fa541c', '#fa8c16', '#fadb14', '#52c41a', '#13c2c2',
  '#1890ff', '#2f54eb', '#722ed1', '#eb2f96',
  '#a8071a', '#ad2102', '#ad4e00', '#ad8b00', '#389e0d', '#08979c',
  '#096dd9', '#1d39c4', '#531dab', '#c41d7f',
  '#5c0011', '#610b00', '#612500', '#613400', '#135200', '#00474f',
  '#003a8c', '#061178', '#22075e', '#780650',
];
const BG_COLORS = [
  'transparent',
  '#fff1f0', '#fff2e8', '#fff7e6', '#fffbe6', '#f6ffed', '#e6fffb',
  '#e6f7ff', '#f0f5ff', '#f9f0ff', '#fff0f6',
  '#ffccc7', '#ffd8bf', '#ffe7ba', '#fffb8f', '#b7eb8f', '#87e8de',
  '#91d5ff', '#adc6ff', '#d3adf7', '#ffadd2',
  '#ffa39e', '#ffbb96', '#ffd591', '#fff566', '#95de64', '#5cdbd3',
  '#69c0ff', '#85a5ff', '#b37feb', '#ff85c0',
  '#ff4d4f', '#ff7a45', '#ffa940', '#ffec3d', '#73d13d', '#36cfc9',
  '#40a9ff', '#597ef7', '#9254de', '#f759ab',
  '#cf1322', '#d4380d', '#d46b08', '#d4b106', '#3f8600', '#08979c',
  '#096dd9', '#1d39c4', '#531dab', '#c41d7f',
];
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
          <div className="toolbar-dropdown bg-color-dropdown">
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

function renderWikiLinksInDom(container) {
  if (!container) return;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
  const targets = [];
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    if (!parent) continue;
    const tag = parent.tagName;
    if (tag === 'A' || tag === 'CODE' || tag === 'PRE') continue;
    if ((node.nodeValue || '').includes('[[') && (node.nodeValue || '').includes(']]')) {
      targets.push(node);
    }
  }
  const re = /\[\[([^\[\]\n]{1,220})\]\]/g;
  for (const textNode of targets) {
    const text = textNode.nodeValue || '';
    let m;
    let last = 0;
    const frag = document.createDocumentFragment();
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) {
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      }
      const raw = (m[1] || '').trim();
      const a = document.createElement('a');
      a.href = '#';
      a.className = 'wiki-link';
      a.dataset.wiki = raw;
      a.textContent = `[[${raw}]]`;
      frag.appendChild(a);
      last = m.index + m[0].length;
    }
    if (last === 0) continue;
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    textNode.parentNode?.replaceChild(frag, textNode);
  }
}

function clearJumpHighlight(container) {
  if (!container) return;
  container.querySelectorAll('.anchor-jump-highlight').forEach((el) => {
    const text = document.createTextNode(el.textContent || '');
    el.replaceWith(text);
  });
}

function highlightJumpAnchor(container, anchorText) {
  if (!container || !anchorText) return false;
  clearJumpHighlight(container);
  const target = String(anchorText).trim();
  if (!target) return false;
  const key = target.toLowerCase();
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
  let node;
  while ((node = walker.nextNode())) {
    const value = node.nodeValue || '';
    const low = value.toLowerCase();
    const idx = low.indexOf(key);
    if (idx < 0) continue;
    const before = value.slice(0, idx);
    const hit = value.slice(idx, idx + target.length);
    const after = value.slice(idx + target.length);
    const frag = document.createDocumentFragment();
    if (before) frag.appendChild(document.createTextNode(before));
    const mark = document.createElement('mark');
    mark.className = 'anchor-jump-highlight';
    mark.textContent = hit;
    frag.appendChild(mark);
    if (after) frag.appendChild(document.createTextNode(after));
    node.parentNode?.replaceChild(frag, node);
    setTimeout(() => {
      mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 20);
    return true;
  }
  return false;
}

function parseContent(raw) {
  if (!raw) return '';
  if (typeof raw === 'object') return raw;
  try {
    const obj = JSON.parse(raw);
    if (obj && obj.type === 'doc') return obj;
  } catch {}
  return raw;
}

export default function NoteEditor({ note, onUpdate, defaultEditing = false, onOpenWikiLink, jumpAnchor = '' }) {
  const [title, setTitle] = useState(note?.title || '');
  const [mode, setMode] = useState('read');
  const [mdSource, setMdSource] = useState('');
  const [lightboxSrc, setLightboxSrc] = useState(null);
  const contentRef = useRef(null);
  const readViewRef = useRef(null);
  const noteRef = useRef(note);
  const onUpdateRef = useRef(onUpdate);
  const settings = loadEditorSettings();

  noteRef.current = note;
  onUpdateRef.current = onUpdate;

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
      ResizableImage,
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
    content: parseContent(note?.content),
    editable: false,
    onUpdate: ({ editor }) => {
      const json = JSON.stringify(editor.getJSON());
      const text = editor.getText();
      onUpdateRef.current(noteRef.current.id, { content: json, word_count: text.length });
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

  useEffect(() => {
    return () => {
      if (editor && !editor.isDestroyed) {
        const json = JSON.stringify(editor.getJSON());
        const text = editor.getText();
        onUpdateRef.current(noteRef.current.id, { content: json, word_count: text.length, _flush: true });
      }
    };
  }, [editor]);

  const switchMode = useCallback((next) => {
    if (!editor) return;
    if (next === 'edit') {
      editor.setEditable(true);
      editor.chain().focus().run();
    } else {
      editor.setEditable(false);
    }
    setMode(next);
  }, [editor]);

  useEffect(() => {
    setTitle(note?.title || '');
    setMode(defaultEditing ? 'edit' : 'read');
    if (editor) {
      editor.setEditable(defaultEditing);
      editor.commands.setContent(parseContent(note.content));
      if (defaultEditing) {
        setTimeout(() => {
          try { editor.chain().focus().run(); } catch {}
        }, 0);
      }
    }
  }, [note?.id, defaultEditing, editor]);

  useEffect(() => {
    if (mode === 'read' && readViewRef.current) {
      const html = editor?.getHTML() || '';
      readViewRef.current.innerHTML = html;
      renderMdBlocksInDom(readViewRef.current);
      renderWikiLinksInDom(readViewRef.current);
      if (jumpAnchor) {
        highlightJumpAnchor(readViewRef.current, jumpAnchor);
      }
    }
  }, [mode, note?.id, jumpAnchor]);

  const handleReadViewClick = useCallback((e) => {
    if (e.target.tagName === 'IMG') {
      setLightboxSrc(e.target.src);
      return;
    }
    const link = e.target.closest?.('.wiki-link');
    if (link) {
      e.preventDefault();
      onOpenWikiLink?.(link.dataset.wiki || '');
    }
  }, [onOpenWikiLink]);

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

  const isDoc = note?.note_type === 'doc';

  const addSelectionToTodo = async () => {
    if (!(isDiary || isDoc) || !editor) return;
    const { from, to } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to, '\n').trim();
    if (!text) {
      message.warning('请先选中要加入待办的内容');
      return;
    }
    try {
      await todoApi.create({
        content: text,
        priority: 'medium',
        source_note_id: note.id,
        source_anchor_text: text.slice(0, 240),
      });
      message.success('已加入稍后待办');
    } catch (e) {
      message.error(e.response?.data?.detail || '添加待办失败');
    }
  };

  return (
    <div className={`editor-panel ${mode === 'edit' ? '' : 'readonly'}`}>
      <div className="editor-header">
        <div className="editor-header-top">
          {isDiary && dateDisplay && (
            <div className="editor-date-header">📅 {dateDisplay}</div>
          )}
          <div style={{ flex: 1 }} />
          {(isDiary || isDoc) && mode === 'edit' && (
            <button className="todo-capture-btn" onClick={addSelectionToTodo}>
              + 加入稍后待办
            </button>
          )}
          <div className="mode-toggle-group">
            <button className={`mode-btn ${mode === 'read' ? 'active' : ''}`} onClick={() => switchMode('read')} title="阅读模式">📖 阅读</button>
            <button className={`mode-btn ${mode === 'edit' ? 'active' : ''}`} onClick={() => switchMode('edit')} title="编辑模式">✏️ 编辑</button>
          </div>
        </div>
        {mode === 'edit' ? (
          <input className="editor-title-input" placeholder={isDiary ? '日记标题...' : '输入标题...'} value={title} onChange={handleTitleChange} />
        ) : (
          <div className="editor-title-readonly">{title || '无标题'}</div>
        )}
      </div>
      {mode === 'edit' && <Toolbar editor={editor} />}
      <div className="editor-content read-mode-content" style={{ ...editorStyle, display: mode === 'read' ? undefined : 'none' }}>
        <div className="tiptap ProseMirror" ref={readViewRef} onClick={handleReadViewClick} />
      </div>
      <div className="editor-content" style={{ ...editorStyle, display: mode === 'edit' ? undefined : 'none' }} ref={contentRef}>
        <EditorContent editor={editor} />
      </div>
      <div className="editor-footer">
        <span>{note.word_count || 0} 字</span>
        <span>最后编辑: {dayjs(note.updated_at).format('YYYY-MM-DD HH:mm')}</span>
      </div>
      {lightboxSrc && createPortal(
        <div className="image-lightbox" onClick={() => setLightboxSrc(null)}>
          <img src={lightboxSrc} alt="" onClick={e => e.stopPropagation()} />
        </div>,
        document.body
      )}
    </div>
  );
}
