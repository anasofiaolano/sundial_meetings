import { useState } from 'react';
import { Bold, Italic, List, ListOrdered, Heading2, Undo2, Redo2 } from 'lucide-react';
import { useEditor, EditorContent, ReactNodeViewRenderer, NodeViewWrapper, NodeViewContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Node, mergeAttributes, textblockTypeInputRule } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

// ── Collapse ProseMirror Plugin ──────────────────────────────────────────────

const collapseKey = new PluginKey('collapse');

const CollapsePlugin = new Plugin({
  key: collapseKey,
  props: {
    decorations(state) {
      const { doc } = state;
      const decos = [];
      let collapseLevel = null;

      doc.forEach((node, offset) => {
        if (node.type.name === 'collapsibleHeading') {
          const lvl = node.attrs.level;
          if (collapseLevel !== null && lvl <= collapseLevel) collapseLevel = null;
          if (collapseLevel !== null) {
            decos.push(Decoration.node(offset, offset + node.nodeSize, { class: 'tiptap-collapsed' }));
          } else if (node.attrs.collapsed) {
            collapseLevel = lvl;
          }
        } else if (collapseLevel !== null) {
          decos.push(Decoration.node(offset, offset + node.nodeSize, { class: 'tiptap-collapsed' }));
        }
      });

      return DecorationSet.create(doc, decos);
    },
  },
});

// ── Heading NodeView ─────────────────────────────────────────────────────────

function HeadingView({ node, updateAttributes }) {
  const { collapsed } = node.attrs;
  return (
    <NodeViewWrapper>
      <div className="collapsible-heading-inner flex items-center gap-2 group/heading cursor-default select-none">
        <button
          contentEditable={false}
          onMouseDown={e => { e.preventDefault(); updateAttributes({ collapsed: !collapsed }); }}
          className="flex-shrink-0 flex items-center justify-center w-4 h-4 text-[#ccc] hover:text-[#888] cursor-pointer border-none bg-transparent p-0 leading-none rounded transition-colors"
          style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}
          aria-label={collapsed ? 'Expand section' : 'Collapse section'}
        >
          {/* Chevron down — clean SVG */}
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <span className="text-[13px] font-semibold text-[#777] group-hover/heading:text-[#444] transition-colors tracking-[-0.01em]">
          <NodeViewContent as="span" />
        </span>
      </div>
    </NodeViewWrapper>
  );
}

// ── CollapsibleHeading Extension ─────────────────────────────────────────────

const CollapsibleHeading = Node.create({
  name: 'collapsibleHeading',
  group: 'block',
  content: 'inline*',
  defining: true,

  addAttributes() {
    return {
      level:     { default: 2 },
      collapsed: { default: false, rendered: false },
    };
  },

  parseHTML() {
    return [
      { tag: 'h1', attrs: { level: 1 } },
      { tag: 'h2', attrs: { level: 2 } },
      { tag: 'h3', attrs: { level: 3 } },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    return [`h${node.attrs.level}`, mergeAttributes(HTMLAttributes), 0];
  },

  addNodeView() {
    return ReactNodeViewRenderer(HeadingView);
  },

  addCommands() {
    return {
      toggleCollapsibleHeading: (attrs) => ({ commands }) =>
        commands.toggleNode(this.name, 'paragraph', attrs),
    };
  },

  // Typing "## " at the start of a line converts it to a collapsible heading
  addInputRules() {
    return [
      textblockTypeInputRule({
        find: /^#{2}\s$/,
        type: this.type,
        getAttributes: () => ({ level: 2 }),
      }),
    ];
  },

  addProseMirrorPlugins() {
    return [CollapsePlugin];
  },
});

// ── Toolbar ──────────────────────────────────────────────────────────────────

function ToolbarBtn({ active, onMouseDown, title, children }) {
  return (
    <button
      onMouseDown={onMouseDown}
      title={title}
      className={`w-6 h-6 flex items-center justify-center rounded text-[12px] border-none cursor-pointer transition-colors font-inherit
        ${active
          ? 'bg-[#1a1a1a] text-white'
          : 'bg-transparent text-[#999] hover:bg-[#f0f0f0] hover:text-[#333]'
        }`}
    >
      {children}
    </button>
  );
}

function Toolbar({ editor }) {
  if (!editor) return null;
  const cmd = (fn) => (e) => { e.preventDefault(); fn(); };

  return (
    <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-[#f0f0f0]">
      {/* Formatting */}
      <ToolbarBtn
        active={editor.isActive('bold')}
        onMouseDown={cmd(() => editor.chain().focus().toggleBold().run())}
        title="Bold (⌘B)"
      >
        <Bold size={13} />
      </ToolbarBtn>
      <ToolbarBtn
        active={editor.isActive('italic')}
        onMouseDown={cmd(() => editor.chain().focus().toggleItalic().run())}
        title="Italic (⌘I)"
      >
        <Italic size={13} />
      </ToolbarBtn>

      <div className="w-px h-3.5 bg-[#e8e8e8] mx-1" />

      {/* Lists */}
      <ToolbarBtn
        active={editor.isActive('bulletList')}
        onMouseDown={cmd(() => editor.chain().focus().toggleBulletList().run())}
        title="Bullet list"
      >
        <List size={13} />
      </ToolbarBtn>
      <ToolbarBtn
        active={editor.isActive('orderedList')}
        onMouseDown={cmd(() => editor.chain().focus().toggleOrderedList().run())}
        title="Numbered list"
      >
        <ListOrdered size={13} />
      </ToolbarBtn>
      <ToolbarBtn
        active={editor.isActive('collapsibleHeading')}
        onMouseDown={cmd(() => editor.chain().focus().toggleCollapsibleHeading({ level: 2 }).run())}
        title="Section heading (or type ## )"
      >
        <Heading2 size={13} />
      </ToolbarBtn>

      <div className="w-px h-3.5 bg-[#e8e8e8] mx-1" />

      {/* History */}
      <ToolbarBtn
        active={false}
        onMouseDown={cmd(() => editor.chain().focus().undo().run())}
        title="Undo (⌘Z)"
      >
        <Undo2 size={13} />
      </ToolbarBtn>
      <ToolbarBtn
        active={false}
        onMouseDown={cmd(() => editor.chain().focus().redo().run())}
        title="Redo (⌘⇧Z)"
      >
        <Redo2 size={13} />
      </ToolbarBtn>
    </div>
  );
}

// ── parseMarkdown ─────────────────────────────────────────────────────────────

export function parseMarkdown(md) {
  if (!md) return { type: 'doc', content: [{ type: 'paragraph' }] };

  const lines = md.split('\n');
  const nodes = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Heading: ## Heading
    const headingMatch = line.match(/^#{1,3}\s+(.+)$/);
    if (headingMatch) {
      const level = (line.match(/^#+/) || [''])[0].length;
      nodes.push({
        type: 'collapsibleHeading',
        attrs: { level: Math.min(level, 3), collapsed: false },
        content: [{ type: 'text', text: headingMatch[1] }],
      });
      i++;
      continue;
    }

    // Bullet list: lines starting with "- " or "* "
    if (/^[-*]\s/.test(line)) {
      const listItems = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        const text = lines[i].replace(/^[-*]\s+/, '');
        // Handle inline bold **text**
        const inlineContent = parseInline(text);
        listItems.push({
          type: 'listItem',
          content: [{ type: 'paragraph', content: inlineContent }],
        });
        i++;
      }
      nodes.push({ type: 'bulletList', content: listItems });
      continue;
    }

    // Blank line — skip
    if (line.trim() === '') {
      i++;
      continue;
    }

    // Paragraph
    const inlineContent = parseInline(line.trim());
    if (inlineContent.length > 0) {
      nodes.push({ type: 'paragraph', content: inlineContent });
    }
    i++;
  }

  if (nodes.length === 0) {
    nodes.push({ type: 'paragraph' });
  }

  return { type: 'doc', content: nodes };
}

function parseInline(text) {
  if (!text) return [];
  const nodes = [];
  // Split on **bold** markers
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  for (const part of parts) {
    if (!part) continue;
    const boldMatch = part.match(/^\*\*([^*]+)\*\*$/);
    if (boldMatch) {
      nodes.push({ type: 'text', text: boldMatch[1], marks: [{ type: 'bold' }] });
    } else {
      nodes.push({ type: 'text', text: part });
    }
  }
  return nodes;
}

// ── NotesEditor ───────────────────────────────────────────────────────────────

export default function NotesEditor({ content, markdown, placeholder = 'Add notes…' }) {
  const [focused, setFocused] = useState(false);

  const resolvedContent = content
    ?? (markdown != null ? parseMarkdown(markdown) : null)
    ?? { type: 'doc', content: [{ type: 'paragraph' }] };

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: false }),
      CollapsibleHeading,
    ],
    content: resolvedContent,
    editorProps: {
      attributes: { 'data-placeholder': placeholder },
    },
    onFocus: () => setFocused(true),
    onBlur:  () => setFocused(false),
  });

  return (
    <div
      className={`tiptap-editor relative rounded-lg border transition-all
        ${focused
          ? 'border-[#d0d0d0] bg-white shadow-sm'
          : 'border-transparent hover:border-[#e8e8e8] hover:bg-white'
        }`}
    >
      {focused && <Toolbar editor={editor} />}

      <div className={focused ? 'px-3 pb-3' : 'px-3 py-2'}>
        <EditorContent editor={editor} />
      </div>

      {/* Edit hint — only in unfocused hover state */}
      {!focused && (
        <div className="absolute top-1.5 right-2 opacity-0 group-hover:opacity-100 pointer-events-none select-none">
          <span className="text-[10px] text-[#bbb] bg-[#f9f9f9] border border-[#eee] px-1.5 py-0.5 rounded">
            Edit
          </span>
        </div>
      )}
    </div>
  );
}
