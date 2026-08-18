import { mergeAttributes, Node } from '@tiptap/core';
import { NodeViewContent, NodeViewWrapper, ReactNodeViewRenderer } from '@tiptap/react';
import { useState } from 'react';

function CollapsibleView({ node, updateAttributes }) {
  const [expanded, setExpanded] = useState(true);

  const finishTitleEdit = (event) => {
    const title = event.target.value.trim() || '折叠内容';
    updateAttributes({ title });
  };

  return (
    <NodeViewWrapper
      as="div"
      className={`research-collapsible research-collapsible-editor${expanded ? ' expanded' : ' collapsed'}`}
    >
      <div className="research-collapsible-editor-header" contentEditable={false}>
        <button
          type="button"
          className="research-collapse-toggle"
          onClick={() => setExpanded((current) => !current)}
          aria-label={expanded ? '收起折叠内容' : '展开折叠内容'}
          title={expanded ? '收起' : '展开'}
        >
          {expanded ? '▾' : '▸'}
        </button>
        <input
          className="research-collapse-title-input"
          value={node.attrs.title || ''}
          onChange={(event) => updateAttributes({ title: event.target.value })}
          onBlur={finishTitleEdit}
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              event.currentTarget.blur();
            }
          }}
          aria-label="折叠名称"
        />
      </div>
      <NodeViewContent
        as="div"
        className="research-collapse-content"
        data-collapse-content=""
        style={{ display: expanded ? undefined : 'none' }}
      />
    </NodeViewWrapper>
  );
}

const ResearchCollapsible = Node.create({
  name: 'researchCollapsible',
  group: 'block',
  content: 'block+',
  defining: true,
  isolating: true,

  addAttributes() {
    return {
      title: {
        default: '折叠内容',
        parseHTML: (element) => element.getAttribute('data-title') || element.querySelector('summary')?.textContent?.trim() || '折叠内容',
        renderHTML: (attributes) => ({ 'data-title': attributes.title || '折叠内容' }),
      },
    };
  },

  parseHTML() {
    return [{ tag: 'details[data-research-collapse]', contentElement: '[data-collapse-content]' }];
  },

  renderHTML({ HTMLAttributes, node }) {
    return [
      'details',
      mergeAttributes(HTMLAttributes, { 'data-research-collapse': 'true' }),
      ['summary', node.attrs.title || '折叠内容'],
      ['div', { 'data-collapse-content': '' }, 0],
    ];
  },

  addCommands() {
    return {
      insertResearchCollapsible: (options = {}) => ({ commands }) => commands.insertContent({
        type: this.name,
        attrs: { title: options.title?.trim() || '折叠内容' },
        content: [{ type: 'paragraph' }],
      }),
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer(CollapsibleView);
  },
});

export default ResearchCollapsible;
