import { useRef, useState } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import Link from '@tiptap/extension-link';
import Highlight from '@tiptap/extension-highlight';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { FontFamily } from '@tiptap/extension-font-family';
import { Table, TableCell, TableHeader, TableRow } from '@tiptap/extension-table';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Subscript from '@tiptap/extension-subscript';
import Superscript from '@tiptap/extension-superscript';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
import { common, createLowlight } from 'lowlight';
import { generateHTML } from '@tiptap/core';
import api from '../api';
import ResearchCollapsible from './ResearchCollapsible';
import ResearchResizableImage from './ResearchResizableImage';

const lowlight = createLowlight(common);
const FONT_SIZES = ['12px', '14px', '16px', '18px', '20px', '24px', '28px', '32px'];
const FONT_FAMILIES = [
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
  '#1890ff', '#2f54eb', '#722ed1', '#eb2f96', '#a8071a', '#ad2102',
  '#ad4e00', '#ad8b00', '#389e0d', '#08979c', '#096dd9', '#1d39c4',
  '#531dab', '#c41d7f', '#5c0011', '#610b00', '#612500', '#613400',
  '#135200', '#00474f', '#003a8c', '#061178', '#22075e', '#780650',
];
const BG_COLORS = [
  'transparent', '#fff1f0', '#fff2e8', '#fff7e6', '#fffbe6', '#f6ffed',
  '#e6fffb', '#e6f7ff', '#f0f5ff', '#f9f0ff', '#fff0f6', '#ffccc7',
  '#ffd8bf', '#ffe7ba', '#fffb8f', '#b7eb8f', '#87e8de', '#91d5ff',
  '#adc6ff', '#d3adf7', '#ffadd2', '#ffa39e', '#ffbb96', '#ffd591',
  '#fff566', '#95de64', '#5cdbd3', '#69c0ff', '#85a5ff', '#b37feb',
  '#ff85c0', '#ff4d4f', '#ff7a45', '#ffa940', '#ffec3d', '#73d13d',
  '#36cfc9', '#40a9ff', '#597ef7', '#9254de', '#f759ab', '#cf1322',
  '#d4380d', '#d46b08', '#d4b106', '#3f8600', '#08979c', '#096dd9',
  '#1d39c4', '#531dab', '#c41d7f',
];
const EMOJIS = [
  '😀', '😂', '🥰', '😎', '🤔', '😢', '😡', '🥳', '👍', '👎',
  '❤️', '🔥', '⭐', '💡', '📌', '✅', '❌', '⚠️', '🎯', '💯',
  '📝', '📖', '💻', '🎨', '🔧', '📊', '🕐', '☀️', '🌙', '🌈',
  '🚀', '💰', '📈', '📉', '🏆', '🎉', '👏', '🤝', '💪', '🧠',
];
const CODE_LANGUAGES = [
  ['纯文本', null], ['JavaScript', 'javascript'], ['TypeScript', 'typescript'],
  ['Python', 'python'], ['Java', 'java'], ['C/C++', 'cpp'], ['Go', 'go'],
  ['Rust', 'rust'], ['SQL', 'sql'], ['HTML', 'xml'], ['CSS', 'css'],
  ['JSON', 'json'], ['Bash', 'bash'], ['Markdown', 'markdown'],
];

const FontSize = TextStyle.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      fontSize: {
        default: null,
        parseHTML: (element) => element.style.fontSize || null,
        renderHTML: (attributes) => attributes.fontSize ? { style: `font-size: ${attributes.fontSize}` } : {},
      },
    };
  },
});

async function uploadImage(file) {
  const form = new FormData();
  form.append('file', file);
  return (await api.post('/upload', form)).data.url;
}

function Toolbar({ editor }) {
  const fileRef = useRef(null);
  const [openDrop, setOpenDrop] = useState(null);
  if (!editor) return null;

  const toggle = (name) => setOpenDrop((current) => current === name ? null : name);
  const run = (action) => { setOpenDrop(null); action(); };
  const button = (label, action, active = false, title = label) => (
    <button type="button" className={`research-toolbar-btn${active ? ' active' : ''}`} onClick={() => run(action)} title={title}>{label}</button>
  );
  const upload = async (event) => {
    for (const file of Array.from(event.target.files || [])) {
      try {
        editor.chain().focus().setImage({ src: await uploadImage(file) }).run();
      } catch {}
    }
    event.target.value = '';
  };

  return (
    <div className="research-rich-toolbar">
      <div className="research-toolbar-dropdown-wrap">
        <button type="button" className="research-toolbar-btn" onClick={() => toggle('font')}>字体 ▾</button>
        {openDrop === 'font' ? <div className="research-toolbar-dropdown font">{FONT_FAMILIES.map((item) => (
          <button type="button" key={item.label} style={{ fontFamily: item.value || 'inherit' }} onClick={() => run(() => item.value ? editor.chain().focus().setFontFamily(item.value).run() : editor.chain().focus().unsetFontFamily().run())}>{item.label}</button>
        ))}</div> : null}
      </div>
      <div className="research-toolbar-dropdown-wrap">
        <button type="button" className="research-toolbar-btn" onClick={() => toggle('size')}>字号 ▾</button>
        {openDrop === 'size' ? <div className="research-toolbar-dropdown size">{FONT_SIZES.map((size) => (
          <button type="button" key={size} onClick={() => run(() => editor.chain().focus().setMark('textStyle', { fontSize: size }).run())}><span style={{ fontSize: size }}>{size.replace('px', '')}</span></button>
        ))}</div> : null}
      </div>
      {button('折叠', () => editor.chain().focus().insertResearchCollapsible().run(), editor.isActive('researchCollapsible'), '插入折叠内容')}
      <i className="research-toolbar-divider" />
      {button('B', () => editor.chain().focus().toggleBold().run(), editor.isActive('bold'), '加粗')}
      {button('I', () => editor.chain().focus().toggleItalic().run(), editor.isActive('italic'), '斜体')}
      {button('U', () => editor.chain().focus().toggleUnderline().run(), editor.isActive('underline'), '下划线')}
      {button('S', () => editor.chain().focus().toggleStrike().run(), editor.isActive('strike'), '删除线')}
      {button('x₂', () => editor.chain().focus().toggleSubscript().run(), editor.isActive('subscript'), '下标')}
      {button('x²', () => editor.chain().focus().toggleSuperscript().run(), editor.isActive('superscript'), '上标')}
      <div className="research-toolbar-dropdown-wrap">
        <button type="button" className="research-toolbar-btn" onClick={() => toggle('color')} title="文字颜色">A▾</button>
        {openDrop === 'color' ? <div className="research-toolbar-dropdown colors">{COLORS.map((color) => <button type="button" aria-label={color} key={color} className="research-color" style={{ background: color }} onClick={() => run(() => editor.chain().focus().setColor(color).run())} />)}</div> : null}
      </div>
      <div className="research-toolbar-dropdown-wrap">
        <button type="button" className="research-toolbar-btn" onClick={() => toggle('background')} title="背景颜色"><mark>A</mark>▾</button>
        {openDrop === 'background' ? <div className="research-toolbar-dropdown colors wide">{BG_COLORS.map((color) => <button type="button" aria-label={color} key={color} className="research-color" style={{ background: color === 'transparent' ? '#fff' : color }} onClick={() => run(() => color === 'transparent' ? editor.chain().focus().unsetHighlight().run() : editor.chain().focus().toggleHighlight({ color }).run())}>{color === 'transparent' ? '×' : ''}</button>)}</div> : null}
      </div>
      <i className="research-toolbar-divider" />
      {button('H1', () => editor.chain().focus().toggleHeading({ level: 1 }).run(), editor.isActive('heading', { level: 1 }))}
      {button('H2', () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive('heading', { level: 2 }))}
      {button('H3', () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive('heading', { level: 3 }))}
      <i className="research-toolbar-divider" />
      {button('•', () => editor.chain().focus().toggleBulletList().run(), editor.isActive('bulletList'), '无序列表')}
      {button('1.', () => editor.chain().focus().toggleOrderedList().run(), editor.isActive('orderedList'), '有序列表')}
      {button('☑', () => editor.chain().focus().toggleTaskList().run(), editor.isActive('taskList'), '任务列表')}
      {button('❝', () => editor.chain().focus().toggleBlockquote().run(), editor.isActive('blockquote'), '引用')}
      <div className="research-toolbar-dropdown-wrap">
        <button type="button" className={`research-toolbar-btn${editor.isActive('codeBlock') ? ' active' : ''}`} onClick={() => toggle('code')}>{'</>'}</button>
        {openDrop === 'code' ? <div className="research-toolbar-dropdown font">{CODE_LANGUAGES.map(([label, language]) => <button type="button" key={label} onClick={() => run(() => editor.chain().focus().toggleCodeBlock({ language }).run())}>{label}</button>)}</div> : null}
      </div>
      <i className="research-toolbar-divider" />
      {button('≡左', () => editor.chain().focus().setTextAlign('left').run(), editor.isActive({ textAlign: 'left' }), '左对齐')}
      {button('≡中', () => editor.chain().focus().setTextAlign('center').run(), editor.isActive({ textAlign: 'center' }), '居中')}
      {button('≡右', () => editor.chain().focus().setTextAlign('right').run(), editor.isActive({ textAlign: 'right' }), '右对齐')}
      <i className="research-toolbar-divider" />
      {button('表格', () => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(), false, '插入表格')}
      {editor.isActive('table') ? <>
        {button('+列', () => editor.chain().focus().addColumnAfter().run())}
        {button('+行', () => editor.chain().focus().addRowAfter().run())}
        {button('-列', () => editor.chain().focus().deleteColumn().run())}
        {button('-行', () => editor.chain().focus().deleteRow().run())}
        {button('×表', () => editor.chain().focus().deleteTable().run())}
      </> : null}
      <i className="research-toolbar-divider" />
      <div className="research-toolbar-dropdown-wrap">
        <button type="button" className="research-toolbar-btn" onClick={() => toggle('emoji')}>😀</button>
        {openDrop === 'emoji' ? <div className="research-toolbar-dropdown emoji">{EMOJIS.map((emoji) => <button type="button" key={emoji} onClick={() => run(() => editor.chain().focus().insertContent(emoji).run())}>{emoji}</button>)}</div> : null}
      </div>
      <button type="button" className="research-toolbar-btn" onClick={() => fileRef.current?.click()} title="上传图片">🖼</button>
      <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={upload} />
      {button('🔗', () => { const url = window.prompt('输入链接 URL'); if (url) editor.chain().focus().setLink({ href: url }).run(); }, editor.isActive('link'), '插入链接')}
      {button('—', () => editor.chain().focus().setHorizontalRule().run(), false, '分割线')}
    </div>
  );
}

function parseContent(raw) {
  if (!raw) return '';
  if (typeof raw === 'object') return raw;
  try {
    const parsed = JSON.parse(raw);
    if (parsed?.type === 'doc') return parsed;
  } catch {}
  return raw;
}

function createExtensions() {
  return [
    StarterKit.configure({ codeBlock: false }),
    CodeBlockLowlight.configure({ lowlight, defaultLanguage: null }),
    Placeholder.configure({ placeholder: '开始记录研究假设、证据与结论……' }),
    Underline,
    FontSize,
    Color,
    FontFamily,
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
    ResearchCollapsible,
    ResearchResizableImage,
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
  ];
}

export function renderResearchContent(raw) {
  const parsed = parseContent(raw);
  return typeof parsed === 'object' ? generateHTML(parsed, createExtensions()) : parsed;
}

export default function ResearchEditor({ content, onChange }) {
  const editorRef = useRef(null);
  const editor = useEditor({
    extensions: createExtensions(),
    content: parseContent(content),
    onUpdate: ({ editor: instance }) => onChange(instance.getHTML()),
    editorProps: {
      handleDrop: (_, event) => {
        const images = Array.from(event.dataTransfer?.files || []).filter((file) => file.type.startsWith('image/'));
        if (!images.length) return false;
        event.preventDefault();
        images.forEach(async (file) => editorRef.current?.chain().focus().setImage({ src: await uploadImage(file) }).run());
        return true;
      },
      handlePaste: (_, event) => {
        const image = Array.from(event.clipboardData?.items || []).find((item) => item.type.startsWith('image/'))?.getAsFile();
        if (!image) return false;
        event.preventDefault();
        uploadImage(image).then((url) => editorRef.current?.chain().focus().setImage({ src: url }).run());
        return true;
      },
    },
  });
  editorRef.current = editor;

  return (
    <div className="research-rich-editor">
      <Toolbar editor={editor} />
      <EditorContent editor={editor} className="research-rich-content" />
    </div>
  );
}
