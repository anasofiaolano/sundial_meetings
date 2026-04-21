import { useState, useRef, useEffect, useCallback } from 'react';
import { marked } from 'marked';
import { Sparkles, X, RotateCcw, ArrowUp, Plus, ChevronLeft, MessageSquare, Trash2, Check, Search } from 'lucide-react';
import { chatStream, fetchThreads, createThread, deleteThread, fetchThreadMessages, saveThreadMessages, fetchCalls, fetchFiles } from '../../api/index';

marked.setOptions({ breaks: true, gfm: true });

// ── Drag-to-resize ─────────────────────────────────────────────────────────

function useDragResize(defaultWidth, { min = 300, max = 700 } = {}) {
  const [width, setWidth] = useState(defaultWidth);
  const dragging = useRef(false);
  const startX   = useRef(0);
  const startW   = useRef(0);

  const onMouseDown = useCallback((e) => {
    dragging.current = true;
    startX.current   = e.clientX;
    startW.current   = width;
    e.preventDefault();
  }, [width]);

  useEffect(() => {
    function onMove(e) {
      if (!dragging.current) return;
      const delta = startX.current - e.clientX;
      setWidth(Math.max(min, Math.min(max, startW.current + delta)));
    }
    function onUp() { dragging.current = false; }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [min, max]);

  return { width, onMouseDown };
}

// ── Message bubbles ────────────────────────────────────────────────────────

function UserBubble({ content }) {
  return (
    <div className="flex justify-end">
      <div className="bg-[#1a1a1a] text-white text-[13px] leading-[1.6] px-3.5 py-2.5 rounded-2xl rounded-tr-sm max-w-[88%] whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}

function AssistantBubble({ content, usage, isStreaming }) {
  const html = content ? marked.parse(content) : '';
  return (
    <div className="flex flex-col gap-1">
      <div
        className={`text-[13px] leading-[1.65] text-[#222] max-w-[96%] assistant-prose ${!content && isStreaming ? 'text-[#aaa] italic' : ''}`}
        dangerouslySetInnerHTML={content ? { __html: html } : undefined}
      >
        {!content && isStreaming ? '…' : undefined}
      </div>
      {usage && (
        <div className="text-[10.5px] text-[#ccc] flex gap-2">
          <span>↑ {usage.input_tokens?.toLocaleString()}</span>
          <span>↓ {usage.output_tokens?.toLocaleString()}</span>
          <span>{usage.cost_str}</span>
        </div>
      )}
    </div>
  );
}

// ── Context chips ──────────────────────────────────────────────────────────

function ContextChip({ item, onRemove }) {
  const label = item.type === 'call'
    ? (item.name || item.id).replace(/^\d{6,8}[_\s]+/, '').replace(/_/g, ' ').trim()
    : item.rel || item.id;
  return (
    <div className="flex items-center gap-1 bg-[#eef0ff] text-[#4a6cf7] text-[11px] font-medium px-2 py-0.5 rounded-full">
      <span className="truncate max-w-[120px]">{label}</span>
      <button onClick={() => onRemove(item)} className="opacity-50 hover:opacity-100 transition-opacity cursor-pointer border-none bg-transparent p-0 leading-none text-inherit">
        <X size={10} />
      </button>
    </div>
  );
}

// ── Context picker modal ───────────────────────────────────────────────────

function ContextPicker({ clientId, selectedItems, onDone, onClose }) {
  const [query, setQuery] = useState('');
  const [calls, setCalls] = useState([]);
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(new Map(selectedItems.map(i => [itemKey(i), i])));
  const [loading, setLoading] = useState(true);

  function itemKey(item) {
    return item.type === 'call' ? `call:${item.id}` : `file:${item.rel}`;
  }

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchCalls(clientId).catch(() => []),
      fetchFiles(clientId).catch(() => ({})),
    ]).then(([callsData, filesData]) => {
      setCalls(callsData);
      setFiles(Object.keys(filesData).map(rel => ({ type: 'file', rel })));
    }).finally(() => setLoading(false));
  }, [clientId]);

  function toggle(item) {
    const key = itemKey(item);
    setSelected(prev => {
      const next = new Map(prev);
      if (next.has(key)) next.delete(key);
      else next.set(key, item);
      return next;
    });
  }

  function isSelected(item) {
    return selected.has(itemKey(item));
  }

  const q = query.toLowerCase();
  const filteredCalls = calls.filter(c => {
    const name = (c.transcript_name || c.id || '').toLowerCase();
    return !q || name.includes(q);
  });
  const filteredFiles = files.filter(f => !q || f.rel.toLowerCase().includes(q));

  return (
    <div className="absolute inset-0 z-20 flex flex-col bg-white rounded-[10px] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#f0f0f0] flex-shrink-0">
        <span className="text-[13px] font-semibold text-[#1a1a1a]">Add context</span>
        <button onClick={onClose} className="text-[#ccc] hover:text-[#666] border-none bg-transparent cursor-pointer p-1 rounded-md hover:bg-[#f5f5f5]">
          <X size={14} />
        </button>
      </div>

      <div className="px-3 py-2 border-b border-[#f0f0f0] flex-shrink-0">
        <div className="flex items-center gap-2 bg-[#f5f5f5] rounded-lg px-3 py-1.5">
          <Search size={12} className="text-[#bbb] flex-shrink-0" />
          <input
            autoFocus
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search calls and files…"
            className="flex-1 text-[12px] bg-transparent outline-none placeholder-[#ccc] text-[#333]"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="text-[12px] text-[#aaa] text-center py-8">Loading…</div>
        ) : (
          <>
            {filteredCalls.length > 0 && (
              <>
                <div className="px-4 py-1.5 text-[10px] font-semibold text-[#bbb] uppercase tracking-[0.05em]">Calls</div>
                {filteredCalls.map(call => {
                  const item = { type: 'call', id: call.id, name: call.transcript_name || call.id };
                  return (
                    <button
                      key={call.id}
                      onClick={() => toggle(item)}
                      className="w-full flex items-center gap-3 px-4 py-2 hover:bg-[#f9f9f9] transition-colors cursor-pointer border-none bg-transparent text-left"
                    >
                      <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border transition-colors ${isSelected(item) ? 'bg-[#4a6cf7] border-[#4a6cf7]' : 'border-[#d0d0d0]'}`}>
                        {isSelected(item) && <Check size={10} className="text-white" />}
                      </div>
                      <span className="text-[12.5px] text-[#333] truncate">
                        {(call.transcript_name || call.id).replace(/^\d{6,8}[_\s]+/, '').replace(/_/g, ' ').trim()}
                      </span>
                    </button>
                  );
                })}
              </>
            )}
            {filteredFiles.length > 0 && (
              <>
                <div className="px-4 py-1.5 text-[10px] font-semibold text-[#bbb] uppercase tracking-[0.05em] mt-1">Project files</div>
                {filteredFiles.map(file => (
                  <button
                    key={file.rel}
                    onClick={() => toggle(file)}
                    className="w-full flex items-center gap-3 px-4 py-2 hover:bg-[#f9f9f9] transition-colors cursor-pointer border-none bg-transparent text-left"
                  >
                    <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border transition-colors ${isSelected(file) ? 'bg-[#4a6cf7] border-[#4a6cf7]' : 'border-[#d0d0d0]'}`}>
                      {isSelected(file) && <Check size={10} className="text-white" />}
                    </div>
                    <span className="text-[12.5px] text-[#555] truncate">{file.rel}</span>
                  </button>
                ))}
              </>
            )}
            {filteredCalls.length === 0 && filteredFiles.length === 0 && (
              <div className="text-[12px] text-[#aaa] text-center py-8">No matches</div>
            )}
          </>
        )}
      </div>

      <div className="flex-shrink-0 border-t border-[#f0f0f0] px-3 py-2.5 flex justify-between items-center">
        <span className="text-[11px] text-[#aaa]">{selected.size} selected</span>
        <button
          onClick={() => onDone([...selected.values()])}
          className="text-[12px] font-semibold text-white bg-[#1a1a1a] px-3 py-1.5 rounded-lg cursor-pointer border-none hover:bg-[#333] transition-colors"
        >
          Done
        </button>
      </div>
    </div>
  );
}

// ── Thread list sidebar ────────────────────────────────────────────────────

function ThreadList({ threads, activeThreadId, onSelect, onNew, onDelete, loading }) {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-[#f0f0f0] flex-shrink-0">
        <span className="text-[11px] font-semibold text-[#888] uppercase tracking-[0.05em]">History</span>
        <button
          onClick={onNew}
          title="New conversation"
          className="text-[#aaa] hover:text-[#333] border-none bg-transparent cursor-pointer p-1 rounded-md hover:bg-[#f0f0f0] transition-colors"
        >
          <Plus size={13} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="text-[11px] text-[#ccc] text-center py-6">Loading…</div>
        ) : threads.length === 0 ? (
          <div className="text-[11px] text-[#ccc] text-center py-6">No conversations yet</div>
        ) : (
          threads.map(t => (
            <div
              key={t.id}
              onClick={() => onSelect(t)}
              className={`group flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors rounded-md mx-1 ${t.id === activeThreadId ? 'bg-[#f0f0ff]' : 'hover:bg-[#f5f5f5]'}`}
            >
              <MessageSquare size={11} className={t.id === activeThreadId ? 'text-[#4a6cf7]' : 'text-[#ccc]'} />
              <span className={`flex-1 text-[12px] truncate ${t.id === activeThreadId ? 'font-medium text-[#4a6cf7]' : 'text-[#555]'}`}>
                {t.title}
              </span>
              <button
                onClick={e => { e.stopPropagation(); onDelete(t.id); }}
                className="opacity-0 group-hover:opacity-100 text-[#ccc] hover:text-[#e55] border-none bg-transparent cursor-pointer p-0.5 rounded transition-all"
              >
                <Trash2 size={11} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── ChatPanel ──────────────────────────────────────────────────────────────

export default function ChatPanel({ clientId, clientName, callId, onClose }) {
  const { width, onMouseDown: onDragStart } = useDragResize(400, { min: 320, max: 680 });

  const [view, setView] = useState('chat'); // 'chat' | 'history'
  const [pickerOpen, setPickerOpen] = useState(false);

  // Threads
  const [threads, setThreads]           = useState([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [activeThread, setActiveThread] = useState(null);

  // Messages
  const [messages, setMessages]     = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionCost, setSessionCost] = useState(0);

  // Context
  const [contextItems, setContextItems] = useState(
    callId ? [{ type: 'call', id: callId, name: callId }] : []
  );

  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const textareaRef    = useRef(null);

  // Load threads on mount
  useEffect(() => {
    if (!clientId) return;
    setThreadsLoading(true);
    fetchThreads(clientId)
      .then(setThreads)
      .catch(() => {})
      .finally(() => setThreadsLoading(false));
  }, [clientId]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Update context when callId prop changes (user switches calls)
  useEffect(() => {
    if (callId) {
      setContextItems(prev => {
        const alreadyHas = prev.some(i => i.type === 'call' && i.id === callId);
        if (alreadyHas) return prev;
        // Replace any existing single-call context with the new one; keep files
        const withoutCalls = prev.filter(i => i.type !== 'call');
        return [{ type: 'call', id: callId, name: callId }, ...withoutCalls];
      });
    }
  }, [callId]);

  function welcomeMessage() {
    return {
      role: 'assistant',
      content: `Hi! I have context on **${clientName || 'this client'}** and their calls. What would you like to know?`,
    };
  }

  async function openThread(thread) {
    setActiveThread(thread);
    setView('chat');
    setSessionCost(0);
    setMessages([]);
    try {
      const msgs = await fetchThreadMessages(thread.id);
      if (msgs.length === 0) {
        setMessages([welcomeMessage()]);
      } else {
        setMessages(msgs.map(m => ({
          role: m.role,
          content: m.content,
          usage: m.usage,
        })));
      }
    } catch {
      setMessages([welcomeMessage()]);
    }
  }

  async function newThread() {
    if (!clientId) {
      // No clientId means we can't persist — just clear messages
      setActiveThread(null);
      setMessages([welcomeMessage()]);
      setSessionCost(0);
      setView('chat');
      return;
    }
    try {
      const thread = await createThread(clientId, 'New conversation');
      setThreads(prev => [thread, ...prev]);
      setActiveThread(thread);
      setMessages([welcomeMessage()]);
      setSessionCost(0);
      setView('chat');
    } catch {
      setMessages([welcomeMessage()]);
      setView('chat');
    }
  }

  async function handleDeleteThread(threadId) {
    try {
      await deleteThread(threadId);
      setThreads(prev => prev.filter(t => t.id !== threadId));
      if (activeThread?.id === threadId) {
        setActiveThread(null);
        setMessages([welcomeMessage()]);
      }
    } catch {}
  }

  // Auto-create a thread on first send if none active
  async function ensureThread(userContent) {
    if (activeThread) return activeThread;
    if (!clientId) return null;
    const title = userContent.slice(0, 60) || 'New conversation';
    try {
      const thread = await createThread(clientId, title);
      setThreads(prev => [thread, ...prev]);
      setActiveThread(thread);
      return thread;
    } catch {
      return null;
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || isStreaming) return;

    const userMsg = { role: 'user', content: text };
    const history = [...messages, userMsg];
    setMessages([...history, { role: 'assistant', content: '', streaming: true }]);
    setInput('');
    setIsStreaming(true);

    const ctxItems = contextItems.map(i =>
      i.type === 'call' ? { type: 'call', id: i.id } : { type: 'file', rel: i.rel }
    );

    let rawText  = '';
    let usageData = null;

    try {
      const res = await chatStream(
        history.map(m => ({ role: m.role, content: m.content })),
        ctxItems,
      );
      if (!res.ok) throw new Error(`Server error: ${res.status}`);

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          const payload = part.slice(6).trim();
          if (payload === '[DONE]') continue;
          const parsed = JSON.parse(payload);
          if (typeof parsed === 'string') {
            rawText += parsed;
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = { role: 'assistant', content: rawText, streaming: true };
              return updated;
            });
          } else if (parsed.usage) {
            usageData = parsed.usage;
            setSessionCost(c => c + (parsed.usage.cost_usd ?? 0));
          }
        }
      }
    } catch (err) {
      rawText = `*(Error: ${err.message})*`;
    } finally {
      const finalAssistant = {
        role: 'assistant',
        content: rawText || '*(No response)*',
        usage: usageData,
        streaming: false,
      };
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = finalAssistant;
        return updated;
      });
      setIsStreaming(false);

      // Persist to DB
      const thread = await ensureThread(text);
      if (thread) {
        const toSave = [
          { role: 'user', content: text, context_items: ctxItems.length ? ctxItems : undefined },
          { role: 'assistant', content: rawText || '*(No response)*', usage: usageData },
        ];
        saveThreadMessages(thread.id, toSave).catch(() => {});
      }
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function onInputChange(e) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-shrink-0 h-full" style={{ width }}>
      {/* Drag handle */}
      <div
        onMouseDown={onDragStart}
        className="w-1 flex-shrink-0 cursor-col-resize group flex items-center justify-center"
        title="Drag to resize"
      >
        <div className="w-[3px] h-10 rounded-full bg-transparent group-hover:bg-[#d0d0d0] transition-colors" />
      </div>

      {/* Panel body */}
      <div
        className="flex-1 flex flex-col overflow-hidden rounded-[10px] bg-white relative"
        style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05)' }}
      >
        {/* Context picker overlay */}
        {pickerOpen && (
          <ContextPicker
            clientId={clientId}
            selectedItems={contextItems}
            onDone={items => { setContextItems(items); setPickerOpen(false); }}
            onClose={() => setPickerOpen(false)}
          />
        )}

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#f0f0f0] flex-shrink-0">
          <div className="flex items-center gap-2">
            {view === 'history' && (
              <button
                onClick={() => setView('chat')}
                className="text-[#ccc] hover:text-[#555] border-none bg-transparent cursor-pointer p-1 -ml-1 rounded-md hover:bg-[#f5f5f5] transition-colors"
              >
                <ChevronLeft size={15} />
              </button>
            )}
            <Sparkles size={14} className="text-[#4a6cf7]" />
            <span className="text-[13px] font-semibold text-[#1a1a1a]">
              {view === 'history' ? 'History' : 'AI Copilot'}
            </span>
            {sessionCost > 0 && view === 'chat' && (
              <span className="text-[10.5px] text-[#bbb] ml-1">~${sessionCost.toFixed(3)}</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {view === 'chat' && (
              <>
                <button
                  onClick={newThread}
                  title="New conversation"
                  className="text-[#ccc] hover:text-[#666] border-none bg-transparent cursor-pointer p-1.5 rounded-md hover:bg-[#f5f5f5] transition-colors"
                >
                  <RotateCcw size={13} />
                </button>
                <button
                  onClick={() => setView('history')}
                  title="Conversation history"
                  className="text-[#ccc] hover:text-[#666] border-none bg-transparent cursor-pointer p-1.5 rounded-md hover:bg-[#f5f5f5] transition-colors"
                >
                  <MessageSquare size={13} />
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="text-[#ccc] hover:text-[#666] border-none bg-transparent cursor-pointer p-1.5 rounded-md hover:bg-[#f5f5f5] transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Body */}
        {view === 'history' ? (
          <ThreadList
            threads={threads}
            activeThreadId={activeThread?.id}
            onSelect={openThread}
            onNew={newThread}
            onDelete={handleDeleteThread}
            loading={threadsLoading}
          />
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
              {messages.length === 0
                ? <AssistantBubble content={welcomeMessage().content} />
                : messages.map((m, i) =>
                    m.role === 'user'
                      ? <UserBubble key={i} content={m.content} />
                      : <AssistantBubble key={i} content={m.content} usage={m.usage} isStreaming={!!m.streaming && isStreaming} />
                  )
              }
              <div ref={messagesEndRef} />
            </div>

            {/* Context chips */}
            {contextItems.length > 0 && (
              <div className="flex-shrink-0 px-3 pt-2 pb-0 flex flex-wrap gap-1.5">
                {contextItems.map((item, i) => (
                  <ContextChip
                    key={i}
                    item={item}
                    onRemove={removed => setContextItems(prev => prev.filter((_, j) => j !== i))}
                  />
                ))}
              </div>
            )}

            {/* Input */}
            <div className="flex-shrink-0 border-t border-[#f0f0f0] px-3 py-3">
              <div className="flex items-end gap-2">
                {/* Context add button */}
                <button
                  onClick={() => setPickerOpen(true)}
                  title="Add context"
                  className="w-7 h-7 rounded-lg border border-[#e8e8e8] text-[#bbb] hover:text-[#555] hover:border-[#bbb] flex items-center justify-center cursor-pointer bg-white transition-colors flex-shrink-0 mb-[1px]"
                >
                  <Plus size={12} />
                </button>
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={onInputChange}
                  onKeyDown={onKeyDown}
                  placeholder="Ask anything about this client…"
                  disabled={isStreaming}
                  rows={1}
                  className="flex-1 text-[13px] border border-[#e8e8e8] rounded-xl px-3 py-2 outline-none focus:border-[#c0c0c0] placeholder-[#ccc] bg-white disabled:opacity-50 resize-none font-inherit leading-[1.5] overflow-hidden transition-colors"
                  style={{ minHeight: '36px', maxHeight: '120px' }}
                />
                <button
                  onClick={send}
                  disabled={isStreaming || !input.trim()}
                  className="w-8 h-8 rounded-lg bg-[#1a1a1a] text-white flex items-center justify-center cursor-pointer border-none hover:bg-[#333] transition-colors flex-shrink-0 disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ArrowUp size={14} />
                </button>
              </div>
              <p className="text-[10.5px] text-[#ccc] mt-1.5 text-right">Enter to send · Shift+Enter for newline</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
