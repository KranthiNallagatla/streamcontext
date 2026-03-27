// StreamContext Content Script
// Captures messages and injects the "Continue Fresh" UI

const SERVICE_URL = 'http://localhost:7892';

let conversationId = null;
let platform = null;
let messageCount = 0;
let capturedMessages = [];
let observer = null;

// Detect platform
function detectPlatform() {
  if (window.location.hostname.includes('claude.ai')) return 'claude';
  if (window.location.hostname.includes('chatgpt.com') || window.location.hostname.includes('chat.openai.com')) return 'chatgpt';
  return null;
}

// Get conversation ID from URL
function getConversationId() {
  const url = window.location.href;
  if (platform === 'claude') {
    const match = url.match(/\/chat\/([a-zA-Z0-9-]+)/);
    return match ? match[1] : 'default-' + Date.now();
  }
  if (platform === 'chatgpt') {
    const match = url.match(/\/c\/([a-zA-Z0-9-]+)/);
    return match ? match[1] : 'default-' + Date.now();
  }
  return 'default-' + Date.now();
}

// Extract messages from DOM
function extractMessages() {
  const messages = [];

  if (platform === 'claude') {
    // Claude message selectors
    const userMsgs = document.querySelectorAll('[data-testid="human-turn"], .human-turn');
    const assistantMsgs = document.querySelectorAll('[data-testid="ai-turn"], .ai-turn');

    // Try generic approach
    const allTurns = document.querySelectorAll('[class*="ConversationItem"], [class*="message"], [data-testid*="turn"]');
    
    allTurns.forEach(turn => {
      const text = turn.innerText?.trim();
      if (text && text.length > 10) {
        const isUser = turn.className?.includes('human') || 
                       turn.getAttribute('data-testid')?.includes('human');
        messages.push({
          role: isUser ? 'user' : 'assistant',
          content: text.substring(0, 2000)
        });
      }
    });
  }

  if (platform === 'chatgpt') {
    const turns = document.querySelectorAll('[data-message-author-role]');
    turns.forEach(turn => {
      const role = turn.getAttribute('data-message-author-role');
      const text = turn.innerText?.trim();
      if (text && text.length > 5) {
        messages.push({
          role: role === 'user' ? 'user' : 'assistant',
          content: text.substring(0, 2000)
        });
      }
    });
  }

  return messages;
}

// Save messages to local service
async function saveToService(messages) {
  try {
    await fetch(`${SERVICE_URL}/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform,
        messages,
        url: window.location.href,
        title: document.title
      })
    });
  } catch (e) {
    // Service not running — store locally
    chrome.storage.local.set({ 
      [`conv_${conversationId}`]: { platform, messages, url: window.location.href, title: document.title, timestamp: Date.now() }
    });
  }
}

// Inject StreamContext toolbar
function injectToolbar() {
  if (document.getElementById('streamcontext-bar')) return;

  const bar = document.createElement('div');
  bar.id = 'streamcontext-bar';
  bar.innerHTML = `
    <div id="sc-inner">
      <div id="sc-left">
        <span id="sc-logo">🌊</span>
        <span id="sc-name">StreamContext</span>
        <span id="sc-count" class="sc-badge">0 messages</span>
      </div>
      <div id="sc-right">
        <button id="sc-continue-btn" class="sc-btn sc-btn-primary">
          ⚡ Continue Fresh
        </button>
        <button id="sc-archive-btn" class="sc-btn sc-btn-secondary">
          📚 Archive
        </button>
      </div>
    </div>
    <div id="sc-status"></div>
  `;

  document.body.prepend(bar);

  // Add padding to body so content isn't hidden
  document.body.style.paddingTop = '48px';

  // Continue Fresh button
  document.getElementById('sc-continue-btn').addEventListener('click', handleContinueFresh);
  document.getElementById('sc-archive-btn').addEventListener('click', handleArchive);
}

// Handle Continue Fresh
async function handleContinueFresh() {
  const btn = document.getElementById('sc-continue-btn');
  const status = document.getElementById('sc-status');
  
  btn.disabled = true;
  btn.textContent = '⏳ Generating smart summary...';
  status.textContent = 'Analyzing conversation and creating intelligent context...';
  status.className = 'sc-status-loading';

  try {
    // Get fresh messages
    const messages = extractMessages();
    
    // Ask service to summarize
    let summary = null;
    try {
      const response = await fetch(`${SERVICE_URL}/conversations/${conversationId}/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, platform })
      });
      const data = await response.json();
      summary = data.summary;
    } catch (e) {
      // Fallback: generate summary from messages locally
      summary = generateFallbackSummary(messages);
    }

    // Copy to clipboard
    await navigator.clipboard.writeText(summary);
    
    // Open new chat
    if (platform === 'claude') {
      window.open('https://claude.ai/new', '_blank');
    } else {
      window.open('https://chatgpt.com/', '_blank');
    }

    btn.disabled = false;
    btn.textContent = '✅ Context copied! Paste in new chat';
    status.textContent = '📋 Smart summary copied to clipboard. Just paste it in your new chat!';
    status.className = 'sc-status-success';

    setTimeout(() => {
      btn.textContent = '⚡ Continue Fresh';
      status.textContent = '';
    }, 5000);

  } catch (e) {
    btn.disabled = false;
    btn.textContent = '⚡ Continue Fresh';
    status.textContent = '❌ Error: ' + e.message;
    status.className = 'sc-status-error';
  }
}

// Fallback summary generator (when service not running)
function generateFallbackSummary(messages) {
  const recentMessages = messages.slice(-20);
  const convText = recentMessages.map(m => 
    `${m.role === 'user' ? 'Human' : 'Assistant'}: ${m.content.substring(0, 500)}`
  ).join('\n\n');

  return `# Continuing Previous Conversation

## Context
This is a continuation of a previous conversation. Here's a summary of what was discussed:

${convText}

---
Please continue from where we left off, maintaining the same context and tone.`;
}

// Handle Archive
function handleArchive() {
  chrome.runtime.sendMessage({ action: 'openArchive' });
}

// Update message count in toolbar
function updateCount(count) {
  const countEl = document.getElementById('sc-count');
  if (countEl) {
    countEl.textContent = `${count} messages`;
    if (count > 50) {
      countEl.className = 'sc-badge sc-badge-warning';
      countEl.title = 'Chat is getting long — consider using Continue Fresh!';
    } else if (count > 100) {
      countEl.className = 'sc-badge sc-badge-danger';
    }
  }
}

// Watch for new messages
function watchMessages() {
  if (observer) observer.disconnect();

  observer = new MutationObserver(() => {
    const messages = extractMessages();
    if (messages.length !== messageCount) {
      messageCount = messages.length;
      capturedMessages = messages;
      updateCount(messageCount);
      
      // Auto-save every 5 new messages
      if (messageCount % 5 === 0) {
        saveToService(messages);
      }
    }
  });

  observer.observe(document.body, { 
    childList: true, 
    subtree: true,
    characterData: true 
  });
}

// Init
function init() {
  platform = detectPlatform();
  if (!platform) return;

  conversationId = getConversationId();
  
  // Wait for page to load
  setTimeout(() => {
    injectToolbar();
    watchMessages();
    
    // Initial capture
    const messages = extractMessages();
    messageCount = messages.length;
    capturedMessages = messages;
    updateCount(messageCount);
    saveToService(messages);
  }, 2000);
}

// Re-init on navigation (SPA)
let lastUrl = window.location.href;
new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    conversationId = getConversationId();
    messageCount = 0;
    capturedMessages = [];
    setTimeout(init, 1500);
  }
}).observe(document, { subtree: true, childList: true });

init();
