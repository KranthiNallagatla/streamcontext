/**
 * StreamContext v2.0 — Content Script
 * Professional-grade AI conversation context transfer
 */

const SC_VERSION = '2.0.0';
const SERVICE_URL = 'http://localhost:7892';
const SC_COLOR = '#00c8ff';

let platform = null;
let conversationId = null;
let messageCount = 0;
let observer = null;
let saveTimer = null;
let serviceAvailable = false;

// ─── Platform Detection ───────────────────────────────────────────────────────

function detectPlatform() {
  const h = window.location.hostname;
  if (h.includes('claude.ai')) return 'claude';
  if (h.includes('chatgpt.com') || h.includes('chat.openai.com')) return 'chatgpt';
  return null;
}

function getConversationId() {
  const url = window.location.href;
  const patterns = {
    claude: /\/chat\/([a-zA-Z0-9-]+)/,
    chatgpt: /\/c\/([a-zA-Z0-9-]+)/
  };
  const match = url.match(patterns[platform]);
  return match ? match[1] : 'conv-' + btoa(url).slice(0, 16).replace(/[^a-zA-Z0-9]/g, '');
}

// ─── Message Extraction ───────────────────────────────────────────────────────

function extractMessages() {
  if (platform === 'claude') return extractClaude();
  if (platform === 'chatgpt') return extractChatGPT();
  return [];
}

function extractClaude() {
  const messages = [];
  
  // Try multiple selector strategies for resilience
  const strategies = [
    // Strategy 1: data-testid
    () => {
      const turns = document.querySelectorAll('[data-testid="human-turn"], [data-testid="ai-turn"]');
      if (turns.length === 0) return null;
      return Array.from(turns).map(t => ({
        role: t.getAttribute('data-testid') === 'human-turn' ? 'user' : 'assistant',
        content: t.innerText?.trim() || ''
      }));
    },
    // Strategy 2: message classes
    () => {
      const turns = document.querySelectorAll('[class*="human-turn"], [class*="ai-turn"]');
      if (turns.length === 0) return null;
      return Array.from(turns).map(t => ({
        role: t.className.includes('human') ? 'user' : 'assistant',
        content: t.innerText?.trim() || ''
      }));
    },
    // Strategy 3: prose blocks (Claude's rendered output)
    () => {
      // Look for alternating message pattern
      const proseBlocks = document.querySelectorAll('[class*="prose"], [class*="message-content"]');
      if (proseBlocks.length === 0) return null;
      return Array.from(proseBlocks).map((b, i) => ({
        role: i % 2 === 0 ? 'user' : 'assistant',
        content: b.innerText?.trim() || ''
      }));
    },
    // Strategy 4: Generic fallback — scan all substantial text blocks
    () => {
      const allDivs = document.querySelectorAll('div[class]');
      const msgs = [];
      allDivs.forEach(div => {
        const text = div.innerText?.trim();
        if (!text || text.length < 20) return;
        if (div.children.length > 5) return; // Skip containers
        const cls = div.className || '';
        if (cls.includes('human') || cls.includes('user') || cls.includes('Human')) {
          msgs.push({ role: 'user', content: text });
        } else if (cls.includes('assistant') || cls.includes('ai-') || cls.includes('claude')) {
          msgs.push({ role: 'assistant', content: text });
        }
      });
      return msgs.length > 0 ? msgs : null;
    }
  ];

  for (const strategy of strategies) {
    try {
      const result = strategy();
      if (result && result.length > 0) {
        return result.filter(m => m.content.length > 5).map(m => ({
          ...m,
          content: m.content.substring(0, 4000)
        }));
      }
    } catch (e) {}
  }
  return messages;
}

function extractChatGPT() {
  // ChatGPT uses data-message-author-role attribute
  const turns = document.querySelectorAll('[data-message-author-role]');
  if (turns.length > 0) {
    return Array.from(turns)
      .map(t => ({
        role: t.getAttribute('data-message-author-role') === 'user' ? 'user' : 'assistant',
        content: (t.innerText?.trim() || '').substring(0, 4000)
      }))
      .filter(m => m.content.length > 5);
  }
  
  // Fallback: article tags
  const articles = document.querySelectorAll('article[data-testid*="conversation"]');
  return Array.from(articles).map((a, i) => ({
    role: i % 2 === 0 ? 'user' : 'assistant',
    content: (a.innerText?.trim() || '').substring(0, 4000)
  })).filter(m => m.content.length > 5);
}

// ─── Service Communication ────────────────────────────────────────────────────

async function checkService() {
  try {
    const r = await fetch(`${SERVICE_URL}/health`, { signal: AbortSignal.timeout(2000) });
    serviceAvailable = r.ok;
  } catch (e) {
    serviceAvailable = false;
  }
  return serviceAvailable;
}

async function saveToService(messages) {
  if (!serviceAvailable) return;
  try {
    await fetch(`${SERVICE_URL}/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform,
        messages,
        url: window.location.href,
        title: document.title || 'Untitled'
      })
    });
  } catch (e) {
    // Silently fail — service might be restarting
  }
}

async function generateContext(messages) {
  const r = await fetch(`${SERVICE_URL}/conversations/${conversationId}/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, platform })
  });
  if (!r.ok) throw new Error(`Service error: ${r.status}`);
  return r.json();
}

// ─── Auto-inject into new tab ─────────────────────────────────────────────────

function autoInjectContext(summary, newTabId) {
  // Store context for the new tab to pick up
  chrome.storage.local.set({
    'sc_pending_inject': {
      summary,
      platform,
      timestamp: Date.now(),
      tabId: newTabId
    }
  });
}

// Check if we should auto-inject on this page
async function checkForPendingInject() {
  const data = await chrome.storage.local.get('sc_pending_inject');
  const pending = data.sc_pending_inject;
  if (!pending) return;
  
  // Only inject if recent (< 30 seconds) and matches platform
  const age = Date.now() - pending.timestamp;
  if (age > 30000) {
    chrome.storage.local.remove('sc_pending_inject');
    return;
  }
  
  if (pending.platform !== platform) return;
  
  // Wait for the input to be ready
  chrome.storage.local.remove('sc_pending_inject');
  
  let attempts = 0;
  const tryInject = setInterval(() => {
    attempts++;
    if (attempts > 20) { clearInterval(tryInject); return; }
    
    const input = findChatInput();
    if (!input) return;
    
    clearInterval(tryInject);
    
    // Show inject notification
    showInjectBanner(pending.summary, input);
  }, 500);
}

function findChatInput() {
  // Claude
  if (platform === 'claude') {
    return document.querySelector(
      '[data-testid="composer-send-button"]')?.closest('form')?.querySelector('div[contenteditable]') ||
      document.querySelector('div[contenteditable="true"]') ||
      document.querySelector('textarea[placeholder*="message" i]');
  }
  // ChatGPT
  return document.querySelector('#prompt-textarea') ||
    document.querySelector('textarea[data-id="root"]') ||
    document.querySelector('textarea[placeholder*="message" i]');
}

function showInjectBanner(summary, input) {
  const banner = document.createElement('div');
  banner.id = 'sc-inject-banner';
  banner.innerHTML = `
    <div id="sc-inject-inner">
      <span id="sc-inject-icon">🌊</span>
      <div id="sc-inject-text">
        <strong>StreamContext ready</strong>
        <span>Context from previous conversation is ready to inject</span>
      </div>
      <div id="sc-inject-actions">
        <button id="sc-inject-yes">⚡ Auto-paste context</button>
        <button id="sc-inject-no">✕</button>
      </div>
    </div>
  `;
  document.body.prepend(banner);
  
  document.getElementById('sc-inject-yes').onclick = () => {
    injectIntoInput(summary, input);
    banner.remove();
  };
  document.getElementById('sc-inject-no').onclick = () => banner.remove();
  
  // Auto-dismiss after 15 seconds
  setTimeout(() => { if (banner.parentNode) banner.remove(); }, 15000);
}

function injectIntoInput(summary, input) {
  if (input.tagName === 'TEXTAREA') {
    input.value = summary;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  } else if (input.contentEditable === 'true') {
    input.focus();
    input.innerHTML = '';
    document.execCommand('insertText', false, summary);
  }
  input.focus();
  
  // Show success
  showToast('✅ Context injected! Review and press Enter to send.');
}

// ─── Toast Notifications ──────────────────────────────────────────────────────

function showToast(message, type = 'success', duration = 4000) {
  const existing = document.getElementById('sc-toast');
  if (existing) existing.remove();
  
  const toast = document.createElement('div');
  toast.id = 'sc-toast';
  toast.className = `sc-toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, duration);
}

// ─── Toolbar ─────────────────────────────────────────────────────────────────

function injectToolbar() {
  if (document.getElementById('sc-toolbar')) return;
  
  const toolbar = document.createElement('div');
  toolbar.id = 'sc-toolbar';
  toolbar.innerHTML = `
    <div id="sc-toolbar-inner">
      <div id="sc-toolbar-left">
        <span id="sc-logo">🌊</span>
        <span id="sc-brand">StreamContext</span>
        <span id="sc-msg-count" class="sc-pill">Counting...</span>
        <span id="sc-service-status" class="sc-pill sc-pill-offline">● Connecting</span>
      </div>
      <div id="sc-toolbar-right">
        <button id="sc-btn-continue" class="sc-btn-primary" title="Generate context and continue in fresh chat">
          ⚡ Continue Fresh
        </button>
        <button id="sc-btn-archive" class="sc-btn-ghost" title="View conversation archive">
          📚
        </button>
      </div>
    </div>
    <div id="sc-progress-bar"><div id="sc-progress-fill"></div></div>
    <div id="sc-status-text"></div>
  `;
  
  document.body.prepend(toolbar);
  document.body.style.paddingTop = '52px';
  
  document.getElementById('sc-btn-continue').addEventListener('click', handleContinueFresh);
  document.getElementById('sc-btn-archive').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'openArchive' });
  });
}

function updateToolbar(count, online) {
  const countEl = document.getElementById('sc-msg-count');
  const statusEl = document.getElementById('sc-service-status');
  
  if (countEl) {
    countEl.textContent = `${count} msg${count !== 1 ? 's' : ''}`;
    countEl.className = count > 100 ? 'sc-pill sc-pill-danger' :
                         count > 50  ? 'sc-pill sc-pill-warn' : 'sc-pill';
  }
  
  if (statusEl) {
    statusEl.textContent = online ? '● Service' : '● Offline';
    statusEl.className = online ? 'sc-pill sc-pill-online' : 'sc-pill sc-pill-offline';
    statusEl.title = online ? 'StreamContext service running' : 'Start service: python3 ~/streamcontext/service/main.py';
  }
}

function setProgress(pct, text) {
  const fill = document.getElementById('sc-progress-fill');
  const statusText = document.getElementById('sc-status-text');
  if (fill) fill.style.width = `${pct}%`;
  if (statusText) statusText.textContent = text || '';
}

// ─── Continue Fresh ───────────────────────────────────────────────────────────

async function handleContinueFresh() {
  const btn = document.getElementById('sc-btn-continue');
  if (!btn || btn.disabled) return;
  
  btn.disabled = true;
  btn.textContent = '⏳ Analyzing...';
  
  try {
    // Step 1: Extract messages
    setProgress(10, 'Extracting conversation messages...');
    const messages = extractMessages();
    
    if (messages.length === 0) {
      showToast('⚠️ No messages found. Make sure you\'re on a chat page.', 'warn');
      btn.disabled = false;
      btn.textContent = '⚡ Continue Fresh';
      setProgress(0, '');
      return;
    }
    
    setProgress(25, `Found ${messages.length} messages. Saving...`);
    
    // Step 2: Save to service
    await saveToService(messages);
    
    setProgress(40, 'Generating deep context transfer document...');
    btn.textContent = '🧠 Thinking...';
    
    // Step 3: Generate context
    let summary;
    let autoInjected = false;
    
    if (serviceAvailable) {
      setProgress(50, 'Using Claude to analyze your conversation...');
      
      // Stream progress updates while waiting
      const progressInterval = setInterval(() => {
        const fill = document.getElementById('sc-progress-fill');
        if (fill) {
          const current = parseFloat(fill.style.width) || 50;
          if (current < 85) fill.style.width = `${current + 2}%`;
        }
      }, 800);
      
      try {
        const result = await generateContext(messages);
        summary = result.summary;
        clearInterval(progressInterval);
      } catch (e) {
        clearInterval(progressInterval);
        throw e;
      }
    } else {
      // Offline fallback — generate locally
      setProgress(60, 'Service offline — generating basic context...');
      summary = generateOfflineContext(messages);
    }
    
    setProgress(90, 'Opening new chat...');
    
    // Step 4: Open new tab and auto-inject
    const newUrl = platform === 'claude' ? 'https://claude.ai/new' : 'https://chatgpt.com/';
    
    // Store for auto-inject
    chrome.storage.local.set({
      'sc_pending_inject': {
        summary,
        platform,
        timestamp: Date.now()
      }
    });
    
    // Open new tab
    const newTab = window.open(newUrl, '_blank');
    
    setProgress(100, '');
    
    // Also show modal as fallback
    showContextModal(summary, true);
    
    btn.disabled = false;
    btn.textContent = '⚡ Continue Fresh';
    setProgress(0, '');
    
  } catch (e) {
    console.error('StreamContext error:', e);
    showToast(`❌ ${e.message}`, 'error', 6000);
    btn.disabled = false;
    btn.textContent = '⚡ Continue Fresh';
    setProgress(0, '');
  }
}

function generateOfflineContext(messages) {
  const total = messages.length;
  const recent = messages.slice(-15);
  
  let ctx = `# 🌊 StreamContext — Continuing Previous Conversation
*${total} messages | Generated offline by StreamContext v${SC_VERSION}*

---

## 📋 Recent Conversation

`;
  recent.forEach(m => {
    ctx += `**${m.role === 'user' ? '👤 You' : '🤖 AI'}:** ${m.content.substring(0, 600)}\n\n---\n\n`;
  });
  
  ctx += `\n*Please continue from where we left off.*`;
  return ctx;
}

// ─── Context Modal ────────────────────────────────────────────────────────────

function showContextModal(summary, autoOpened = false) {
  const existing = document.getElementById('sc-modal');
  if (existing) existing.remove();
  
  const modal = document.createElement('div');
  modal.id = 'sc-modal';
  
  const wordCount = summary.split(/\s+/).length;
  const charCount = summary.length;
  
  modal.innerHTML = `
    <div class="sc-overlay" id="sc-overlay">
      <div class="sc-modal-box">
        <div class="sc-modal-header">
          <div class="sc-modal-title">
            <span>🌊</span>
            <span>Context Transfer Ready</span>
            <span class="sc-modal-meta">${wordCount} words · ${charCount} chars</span>
          </div>
          <button class="sc-modal-close" id="sc-modal-close">✕</button>
        </div>
        
        <div class="sc-modal-body">
          ${autoOpened ? `
          <div class="sc-auto-notice">
            <span>✅</span>
            <span>New chat opened! The context will auto-inject when the page loads. If not, use the button below.</span>
          </div>` : ''}
          
          <div class="sc-modal-actions">
            <button class="sc-action-primary" id="sc-btn-copy-open">
              📋 Copy & Open New Chat
            </button>
            <button class="sc-action-secondary" id="sc-btn-copy-only">
              Copy Only
            </button>
            <button class="sc-action-ghost" id="sc-btn-select-all">
              Select All
            </button>
          </div>
          
          <div class="sc-preview-label">Context Transfer Document Preview:</div>
          <textarea class="sc-context-text" id="sc-context-text" readonly>${escapeHtml(summary)}</textarea>
          <div class="sc-modal-hint">
            💡 Tip: The context will auto-inject into the new chat. If it doesn't, paste it manually.
          </div>
        </div>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // Events
  document.getElementById('sc-modal-close').onclick = () => modal.remove();
  document.getElementById('sc-overlay').onclick = (e) => { if (e.target.id === 'sc-overlay') modal.remove(); };
  
  document.getElementById('sc-btn-copy-open').onclick = async () => {
    await copyToClipboard(summary);
    const newUrl = platform === 'claude' ? 'https://claude.ai/new' : 'https://chatgpt.com/';
    window.open(newUrl, '_blank');
    document.getElementById('sc-btn-copy-open').textContent = '✅ Copied & Opened!';
    setTimeout(() => modal.remove(), 2000);
  };
  
  document.getElementById('sc-btn-copy-only').onclick = async () => {
    const ok = await copyToClipboard(summary);
    document.getElementById('sc-btn-copy-only').textContent = ok ? '✅ Copied!' : '⚠️ Select manually';
  };
  
  document.getElementById('sc-btn-select-all').onclick = () => {
    const ta = document.getElementById('sc-context-text');
    ta.select();
    showToast('Text selected — press Cmd+C to copy');
  };
  
  document.getElementById('sc-context-text').onclick = function() { this.select(); };
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function copyToClipboard(text) {
  // Try modern API
  try {
    if (navigator.clipboard && document.hasFocus()) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) {}
  
  // Fallback: textarea trick
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(ta);
  return ok;
}

// ─── Message Watching ─────────────────────────────────────────────────────────

function startWatching() {
  if (observer) observer.disconnect();
  
  observer = new MutationObserver(() => {
    const messages = extractMessages();
    if (messages.length !== messageCount) {
      messageCount = messages.length;
      updateToolbar(messageCount, serviceAvailable);
      
      // Debounced save
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => saveToService(messages), 3000);
    }
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: false,
    attributes: false
  });
}

// ─── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  platform = detectPlatform();
  if (!platform) return;
  
  conversationId = getConversationId();
  
  // Wait for page to settle
  await new Promise(r => setTimeout(r, 1500));
  
  injectToolbar();
  startWatching();
  
  // Initial message count
  const messages = extractMessages();
  messageCount = messages.length;
  
  // Check service
  const online = await checkService();
  updateToolbar(messageCount, online);
  
  // Save initial state
  if (online && messages.length > 0) {
    saveToService(messages);
  }
  
  // Check for pending auto-inject
  checkForPendingInject();
  
  // Recheck service periodically
  setInterval(async () => {
    const was = serviceAvailable;
    await checkService();
    if (was !== serviceAvailable) {
      updateToolbar(messageCount, serviceAvailable);
    }
  }, 30000);
}

// Handle SPA navigation
let lastUrl = window.location.href;
new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    conversationId = getConversationId();
    messageCount = 0;
    if (observer) observer.disconnect();
    const existing = document.getElementById('sc-toolbar');
    if (existing) existing.remove();
    document.body.style.paddingTop = '';
    setTimeout(init, 1000);
  }
}).observe(document, { subtree: true, childList: true });

init();
