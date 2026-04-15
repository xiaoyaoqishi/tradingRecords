import { useMemo, useRef, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Image,
  Input,
  InputNumber,
  Modal,
  Row,
  Slider,
  Space,
  Typography,
  message,
} from 'antd';
import {
  BgColorsOutlined,
  BoldOutlined,
  DeleteOutlined,
  ItalicOutlined,
  PictureOutlined,
} from '@ant-design/icons';
import api from '../../../api';

const { TextArea } = Input;
const IMG_TAG_RE = /<img[^>]+src=["']([^"']+)["'][^>]*>/gi;
const IMAGE_MD_RE = /!\[[^\]]*]\(([^)\s]+)\)/g;
const FORMAT_KIND = 'research_v2';
const HIGHLIGHT_PRESETS = [
  { label: '黄', value: '#fff59d' },
  { label: '绿', value: '#d9f7be' },
  { label: '蓝', value: '#bae7ff' },
  { label: '粉', value: '#ffd6e7' },
];
const STANDARD_FIELD_DEFS = [
  { key: 'entry_thesis', label: '入场论点', placeholder: '记录本次入场的核心论点' },
  { key: 'invalidation_valid_evidence', label: '有效证据', placeholder: '哪些证据支持当前判断' },
  { key: 'invalidation_trigger_evidence', label: '失效证据', placeholder: '哪些证据出现时判断失效' },
  { key: 'invalidation_boundary', label: '边界', placeholder: '相似但不同的边界条件' },
  { key: 'management_actions', label: '管理动作', placeholder: '仓位、加减仓、保护动作等' },
  { key: 'exit_reason', label: '离场原因', placeholder: '最终离场的触发原因' },
];

function normalizeStandardFields(input) {
  const source = input && typeof input === 'object' ? input : {};
  const out = {};
  STANDARD_FIELD_DEFS.forEach(({ key }) => {
    out[key] = String(source[key] || '').trim();
  });
  return out;
}

function stripHtmlToText(html) {
  const withBreak = String(html || '')
    .replace(/<br\s*\/?\s*>/gi, '\n')
    .replace(/<\/p>\s*<p[^>]*>/gi, '\n\n')
    .replace(/<\/div>\s*<div[^>]*>/gi, '\n');
  return withBreak
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function plainTextToHtml(text) {
  return escapeHtml(text).replace(/\n/g, '<br>');
}

function isHtmlLike(text) {
  return /<[a-z][\s\S]*>/i.test(String(text || ''));
}

function sanitizeInlineStyle(styleText) {
  const out = [];
  const rules = String(styleText || '')
    .split(';')
    .map((x) => x.trim())
    .filter(Boolean);
  for (const rule of rules) {
    const idx = rule.indexOf(':');
    if (idx <= 0) continue;
    const prop = rule.slice(0, idx).trim().toLowerCase();
    const val = rule.slice(idx + 1).trim();
    if (!val) continue;
    if (prop === 'background-color') {
      if (/^(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\)|[a-z]+)$/i.test(val)) {
        out.push(`background-color: ${val}`);
      }
      continue;
    }
    if (prop === 'font-weight') {
      if (/^(normal|bold|[1-9]00)$/i.test(val)) out.push(`font-weight: ${val}`);
      continue;
    }
    if (prop === 'font-style') {
      if (/^(normal|italic)$/i.test(val)) out.push(`font-style: ${val}`);
    }
  }
  return out.join('; ');
}

function sanitizeRichTextHtml(rawHtml) {
  const source = String(rawHtml || '');
  if (!source.trim()) return '';
  if (typeof document === 'undefined') return plainTextToHtml(stripHtmlToText(source));

  try {
    const allowedTags = new Set(['STRONG', 'B', 'EM', 'I', 'SPAN', 'P', 'DIV', 'BR']);
    const template = document.createElement('template');
    template.innerHTML = source;

    const cleanContainer = document.createElement('div');
    const TEXT_NODE = 3;
    const ELEMENT_NODE = 1;

    const walk = (node, parent) => {
      if (node.nodeType === TEXT_NODE) {
        parent.appendChild(document.createTextNode(node.nodeValue || ''));
        return;
      }
      if (node.nodeType !== ELEMENT_NODE) return;

      const tag = (node.tagName || '').toUpperCase();
      if (!allowedTags.has(tag)) {
        Array.from(node.childNodes || []).forEach((child) => walk(child, parent));
        return;
      }

      const normalizedTag = tag === 'B' ? 'strong' : tag === 'I' ? 'em' : tag.toLowerCase();
      const el = document.createElement(normalizedTag);
      const styleText = sanitizeInlineStyle(node.getAttribute('style') || '');
      if (styleText) el.setAttribute('style', styleText);

      Array.from(node.childNodes || []).forEach((child) => walk(child, el));
      parent.appendChild(el);
    };

    Array.from(template.content.childNodes || []).forEach((child) => walk(child, cleanContainer));
    return cleanContainer.innerHTML.trim();
  } catch {
    return plainTextToHtml(stripHtmlToText(source));
  }
}

function normalizeBodyForEditor(raw) {
  const text = String(raw || '');
  if (!text.trim()) return '';
  return isHtmlLike(text) ? sanitizeRichTextHtml(text) : plainTextToHtml(text);
}

function normalizeBodyForStorage(raw) {
  const html = sanitizeRichTextHtml(raw);
  return stripHtmlToText(html) ? html : '';
}

function extractImageUrls(raw) {
  const source = String(raw || '');
  const urls = [];
  if (/<[a-z][\s\S]*>/i.test(source)) {
    let m = IMG_TAG_RE.exec(source);
    while (m) {
      if (m[1]) urls.push(m[1]);
      m = IMG_TAG_RE.exec(source);
    }
  }
  let md = IMAGE_MD_RE.exec(source);
  while (md) {
    if (md[1]) urls.push(md[1]);
    md = IMAGE_MD_RE.exec(source);
  }
  return Array.from(new Set(urls));
}

function normalizeImage(item, idx) {
  const width = Number(item?.width);
  return {
    id: String(item?.id || `${Date.now()}-${idx}`),
    url: String(item?.url || '').trim(),
    width: Number.isFinite(width) ? Math.max(120, Math.min(1200, Math.round(width))) : 120,
    caption: String(item?.caption || '').trim(),
  };
}

function parseResearchValue(raw) {
  const text = String(raw || '').trim();
  if (!text) return { body: '', images: [], standardFields: normalizeStandardFields() };

  try {
    const parsed = JSON.parse(text);
    if (parsed && parsed.kind === FORMAT_KIND) {
      return {
        body: String(parsed.body || ''),
        images: Array.isArray(parsed.images)
          ? parsed.images.map((x, i) => normalizeImage(x, i)).filter((x) => x.url)
          : [],
        standardFields: normalizeStandardFields(parsed.standard_fields || parsed.standardFields),
      };
    }
  } catch {
    // fall back to legacy parsing
  }

  const legacyImages = extractImageUrls(text).map((url, i) => ({
    id: `legacy-${i}`,
    url,
    width: 120,
    caption: '',
  }));
  const body = /<[a-z][\s\S]*>/i.test(text)
    ? stripHtmlToText(text)
    : text.replace(IMAGE_MD_RE, '').trim();
  return { body, images: legacyImages, standardFields: normalizeStandardFields() };
}

function serializeResearchValue(model) {
  const body = String(model?.body || '').trim();
  const images = (Array.isArray(model?.images) ? model.images : [])
    .map((x, i) => normalizeImage(x, i))
    .filter((x) => x.url);
  const standardFields = normalizeStandardFields(model?.standardFields);

  const hasStandardField = Object.values(standardFields).some((x) => String(x || '').trim());
  if (!body && images.length === 0 && !hasStandardField) return '';

  return JSON.stringify({
    kind: FORMAT_KIND,
    version: 3,
    body,
    images,
    standard_fields: standardFields,
  });
}

export default function ResearchContentPanel({
  value,
  editing = false,
  title = '图文研究记录',
  showStandardFields = true,
  onChange,
  standardFieldsValue,
  onStandardFieldsChange,
}) {
  const parsed = useMemo(() => parseResearchValue(value), [value]);
  const mergedStandardFields = useMemo(() => {
    if (!showStandardFields) return normalizeStandardFields();
    return normalizeStandardFields({ ...parsed.standardFields, ...standardFieldsValue });
  }, [parsed.standardFields, showStandardFields, standardFieldsValue]);
  const [modalOpen, setModalOpen] = useState(false);
  const [draft, setDraft] = useState({ ...parsed, standardFields: mergedStandardFields });
  const [uploading, setUploading] = useState(false);
  const uploadRef = useRef(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewIndex, setPreviewIndex] = useState(0);
  const editorRef = useRef(null);
  const editorBodyRef = useRef('');
  const [editorSeed, setEditorSeed] = useState(0);
  const [editorInitialHtml, setEditorInitialHtml] = useState('');

  const openModal = () => {
    const latest = parseResearchValue(value);
    editorBodyRef.current = String(latest.body || '');
    setEditorInitialHtml(normalizeBodyForEditor(latest.body));
    setEditorSeed((n) => n + 1);
    setDraft({
      ...latest,
      standardFields: showStandardFields
        ? normalizeStandardFields({ ...latest.standardFields, ...standardFieldsValue })
        : normalizeStandardFields(),
    });
    setModalOpen(true);
  };

  const saveModal = () => {
    const editorBody = editorRef.current ? editorRef.current.innerHTML : editorBodyRef.current;
    const nextDraft = { ...draft, body: normalizeBodyForStorage(editorBody) };
    onChange?.(serializeResearchValue(nextDraft));
    if (showStandardFields) {
      onStandardFieldsChange?.(normalizeStandardFields(nextDraft.standardFields));
    }
    setModalOpen(false);
  };

  const updateImage = (idx, patch) => {
    setDraft((prev) => {
      const next = [...(prev.images || [])];
      next[idx] = { ...next[idx], ...patch };
      return { ...prev, images: next };
    });
  };

  const removeImage = (idx) => {
    setDraft((prev) => ({ ...prev, images: (prev.images || []).filter((_, i) => i !== idx) }));
  };

  const updateStandardField = (key, val) => {
    setDraft((prev) => ({
      ...prev,
      standardFields: {
        ...(prev.standardFields || {}),
        [key]: val,
      },
    }));
  };

  const uploadImages = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const uploaded = [];
      for (const file of files) {
        const form = new FormData();
        form.append('file', file);
        const res = await api.post('/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        const url = String(res.data?.url || '').trim();
        if (url) uploaded.push(url);
      }
      if (uploaded.length > 0) {
        setDraft((prev) => ({
          ...prev,
          images: [
            ...(prev.images || []),
            ...uploaded.map((url, i) => ({ id: `${Date.now()}-${i}`, url, width: 120, caption: '' })),
          ],
        }));
      }
      message.success('图片已添加到研究内容');
    } catch {
      message.error('图片上传失败');
    } finally {
      setUploading(false);
      if (uploadRef.current) uploadRef.current.value = '';
    }
  };

  const handlePasteImage = async (e) => {
    const items = Array.from(e.clipboardData?.items || []);
    const imageFiles = items
      .filter((item) => item.kind === 'file' && item.type && item.type.startsWith('image/'))
      .map((item) => item.getAsFile())
      .filter(Boolean);
    if (imageFiles.length === 0) return;
    e.preventDefault();
    await uploadImages(imageFiles);
  };

  const applyEditorCommand = (command, value = null) => {
    const editor = editorRef.current;
    if (!editor) return;
    editor.focus();
    try {
      if (command === 'hiliteColor') {
        document.execCommand('styleWithCSS', false, 'true');
        const ok = document.execCommand('hiliteColor', false, value);
        if (!ok) document.execCommand('backColor', false, value);
      } else {
        document.execCommand(command, false, value);
      }
    } catch {
      message.warning('当前浏览器对该格式命令支持有限');
    }
    editorBodyRef.current = editor.innerHTML;
  };

  const readonlyData = { ...parsed, standardFields: mergedStandardFields };
  const readonlyBodyHtml = useMemo(() => normalizeBodyForEditor(readonlyData.body), [readonlyData.body]);

  if (!editing) {
    const hasText = stripHtmlToText(readonlyBodyHtml).length > 0;
    const hasImages = (readonlyData.images || []).length > 0;
    const hasStandardFields = showStandardFields && Object.values(readonlyData.standardFields || {}).some((x) => String(x || '').trim());
    if (!hasText && !hasImages && !hasStandardFields) {
      return <Empty description="暂无图文研究记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }

    return (
      <div>
        <Typography.Text type="secondary">{title}</Typography.Text>
        <div
          style={{
            marginTop: 6,
            border: '1px solid #f0f0f0',
            borderRadius: 8,
            background: '#fafafa',
            padding: 12,
          }}
        >
          {hasText ? (
            <div
              style={{ marginBottom: hasImages ? 12 : 0, lineHeight: 1.7 }}
              dangerouslySetInnerHTML={{ __html: readonlyBodyHtml }}
            />
          ) : null}
          {hasStandardFields ? (
            <div style={{ marginBottom: hasImages ? 12 : 0 }}>
              {STANDARD_FIELD_DEFS.map((field) => {
                const v = String(readonlyData.standardFields?.[field.key] || '').trim();
                if (!v) return null;
                return (
                  <div key={field.key} style={{ marginBottom: 8 }}>
                    <Typography.Text type="secondary">{field.label}</Typography.Text>
                    <Typography.Paragraph style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>
                      {v}
                    </Typography.Paragraph>
                  </div>
                );
              })}
            </div>
          ) : null}

          {hasImages ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              {readonlyData.images.map((img, idx) => (
                <div key={img.id || idx} style={{ width: `${img.width || 120}px`, maxWidth: '100%' }}>
                  <img
                    src={img.url}
                    alt={img.caption || `research-${idx + 1}`}
                    style={{
                      width: '100%',
                      borderRadius: 8,
                      display: 'block',
                      cursor: 'zoom-in',
                    }}
                    onClick={() => {
                      setPreviewIndex(idx);
                      setPreviewOpen(true);
                    }}
                  />
                  {img.caption ? (
                    <Typography.Text type="secondary" style={{ marginTop: 6, display: 'inline-block' }}>
                      {img.caption}
                    </Typography.Text>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <Image.PreviewGroup
          preview={{
            visible: previewOpen,
            current: previewIndex,
            onVisibleChange: (visible) => setPreviewOpen(visible),
            onChange: (current) => setPreviewIndex(current),
          }}
        >
          <div style={{ position: 'fixed', left: -99999, top: -99999, opacity: 0 }}>
            {(readonlyData.images || []).map((img, idx) => (
              <Image key={`${img.url}-${idx}`} src={img.url} alt={`research-${idx + 1}`} />
            ))}
          </div>
        </Image.PreviewGroup>
      </div>
    );
  }

  return (
    <>
      <Space>
        <Button onClick={openModal}>图文录入</Button>
        <Typography.Text type="secondary">稳定模式：文本 + 图片卡片，支持逐图宽度调节</Typography.Text>
      </Space>

      <Modal
        title={title}
        centered
        width={920}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={saveModal}
        okText="应用内容"
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {showStandardFields ? (
            <div>
              <Typography.Text type="secondary">标准字段</Typography.Text>
              <Row gutter={12} style={{ marginTop: 8 }}>
                {STANDARD_FIELD_DEFS.map((field) => (
                  <Col key={field.key} span={field.key.includes('evidence') ? 12 : 24}>
                    <Typography.Text type="secondary">{field.label}</Typography.Text>
                    <TextArea
                      rows={2}
                      placeholder={field.placeholder}
                      value={draft.standardFields?.[field.key] || ''}
                      onChange={(e) => updateStandardField(field.key, e.target.value)}
                    />
                  </Col>
                ))}
              </Row>
            </div>
          ) : null}

          <div>
            <Typography.Text type="secondary">研究文本</Typography.Text>
            <Space wrap style={{ margin: '8px 0' }}>
              <Button size="small" icon={<BoldOutlined />} onMouseDown={(e) => e.preventDefault()} onClick={() => applyEditorCommand('bold')}>加粗</Button>
              <Button size="small" icon={<ItalicOutlined />} onMouseDown={(e) => e.preventDefault()} onClick={() => applyEditorCommand('italic')}>斜体</Button>
              <Button size="small" icon={<BgColorsOutlined />} onMouseDown={(e) => e.preventDefault()} onClick={() => applyEditorCommand('removeFormat')}>清除格式</Button>
              {HIGHLIGHT_PRESETS.map((preset) => (
                <Button
                  key={preset.value}
                  size="small"
                  style={{ background: preset.value, borderColor: '#d9d9d9' }}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => applyEditorCommand('hiliteColor', preset.value)}
                >
                  {preset.label}
                </Button>
              ))}
            </Space>
            <div
              key={editorSeed}
              ref={editorRef}
              contentEditable
              suppressContentEditableWarning
              dangerouslySetInnerHTML={{ __html: editorInitialHtml }}
              onInput={(e) => { editorBodyRef.current = e.currentTarget.innerHTML; }}
              onPaste={handlePasteImage}
              style={{
                minHeight: 160,
                maxHeight: 360,
                overflowY: 'auto',
                border: '1px solid #d9d9d9',
                borderRadius: 8,
                padding: '10px 12px',
                lineHeight: 1.7,
                outline: 'none',
                background: '#fff',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            />
            <Typography.Text type="secondary" style={{ marginTop: 6, display: 'inline-block' }}>
              选中文字后可加粗、斜体、背景色；支持 Ctrl+V 粘贴截图
            </Typography.Text>
          </div>

          <div>
            <Space style={{ marginBottom: 8 }}>
              <Button
                icon={<PictureOutlined />}
                loading={uploading}
                onClick={() => uploadRef.current?.click()}
              >
                上传图片
              </Button>
              <Typography.Text type="secondary">可多选；每张图可独立设置宽度与说明</Typography.Text>
            </Space>
            <input
              ref={uploadRef}
              type="file"
              accept="image/*"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => uploadImages(Array.from(e.target.files || []))}
            />

            {(draft.images || []).length === 0 ? (
              <Empty description="还没有图片" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size={10}>
                {draft.images.map((img, idx) => (
                  <Card
                    key={img.id || idx}
                    size="small"
                    title={`图片 ${idx + 1}`}
                    extra={
                      <Button type="text" danger icon={<DeleteOutlined />} onClick={() => removeImage(idx)}>
                        移除
                      </Button>
                    }
                  >
                    <img
                      src={img.url}
                      alt={`draft-${idx + 1}`}
                      style={{
                        width: `${img.width || 120}px`,
                        maxWidth: '100%',
                        borderRadius: 8,
                        display: 'block',
                        marginBottom: 10,
                      }}
                    />
                    <Space wrap style={{ width: '100%' }}>
                      <Typography.Text type="secondary">宽度</Typography.Text>
                      <Slider
                        min={120}
                        max={1200}
                        step={1}
                        value={img.width || 120}
                        onChange={(v) => updateImage(idx, { width: Number(v) || 120 })}
                        style={{ width: 220, margin: '0 8px' }}
                      />
                      <InputNumber
                        min={120}
                        max={1200}
                        value={img.width || 120}
                        onChange={(v) => updateImage(idx, { width: Number(v) || 120 })}
                        style={{ width: 100 }}
                      />
                      <Input
                        placeholder="图片说明（可选）"
                        value={img.caption || ''}
                        onChange={(e) => updateImage(idx, { caption: e.target.value })}
                        style={{ width: 320 }}
                      />
                    </Space>
                  </Card>
                ))}
              </Space>
            )}
          </div>
        </Space>
      </Modal>
    </>
  );
}
