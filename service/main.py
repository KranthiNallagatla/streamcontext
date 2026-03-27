"""
StreamContext Local Service v2.0
Production-grade — runs on your Mac 24/7
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

VERSION = "2.0.0"
app = FastAPI(title="StreamContext", version=VERSION, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_PATH = Path.home() / ".streamcontext" / "conversations.db"
DB_PATH.parent.mkdir(exist_ok=True)

# ─── Database ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = get_db()
    c.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        url TEXT,
        title TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        message_count INTEGER DEFAULT 0,
        summary_count INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        summary TEXT NOT NULL,
        model TEXT,
        created_at TEXT NOT NULL,
        message_count INTEGER DEFAULT 0,
        tokens_used INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    # Default settings
    defaults = {
        'model': 'claude-sonnet-4-6',
        'max_messages_per_summary': '80',
        'auto_save_interval': '5',
        'theme': 'dark',
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings VALUES (?, ?, ?)", (k, v, datetime.now().isoformat()))
    c.commit()
    c.close()

init_db()

# ─── Models ───────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ConversationData(BaseModel):
    platform: str
    messages: List[Message]
    url: str
    title: str

class SummarizeRequest(BaseModel):
    messages: List[Message]
    platform: str

# ─── Anthropic Client ─────────────────────────────────────────────────────────

def get_client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(500, "ANTHROPIC_API_KEY not set in .env file")
    return anthropic.Anthropic(api_key=key)

def get_setting(key: str, default: str = '') -> str:
    c = get_db()
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    c.close()
    return row['value'] if row else default

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    c = get_db()
    convs = c.execute("SELECT COUNT(*) as n FROM conversations").fetchone()['n']
    msgs = c.execute("SELECT COUNT(*) as n FROM messages").fetchone()['n']
    summs = c.execute("SELECT COUNT(*) as n FROM summaries").fetchone()['n']
    c.close()
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {
        "status": "ok",
        "version": VERSION,
        "conversations": convs,
        "messages": msgs,
        "summaries": summs,
        "api_key": api_key_set
    }

@app.post("/conversations/{cid}/messages")
def save_messages(cid: str, data: ConversationData):
    c = get_db()
    now = datetime.now().isoformat()
    exists = c.execute("SELECT id FROM conversations WHERE id=?", (cid,)).fetchone()
    if exists:
        c.execute("""UPDATE conversations 
                     SET updated_at=?, message_count=?, url=?, title=?
                     WHERE id=?""", (now, len(data.messages), data.url, data.title[:200], cid))
    else:
        c.execute("INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)",
                  (cid, data.platform, data.url, data.title[:200], now, now, len(data.messages), 0))
    
    # Clear and re-save messages
    c.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    for m in data.messages:
        c.execute("INSERT INTO messages (conversation_id,role,content,timestamp) VALUES (?,?,?,?)",
                  (cid, m.role, m.content[:5000], now))
    c.commit()
    c.close()
    return {"ok": True, "saved": len(data.messages)}

@app.post("/conversations/{cid}/summarize")
async def summarize(cid: str, data: SummarizeRequest):
    messages = data.messages
    if not messages:
        raise HTTPException(400, "No messages to summarize")
    
    total = len(messages)
    model = get_setting('model', 'claude-sonnet-4-6')
    max_msgs = int(get_setting('max_messages_per_summary', '80'))

    def build_conv_text(msgs, max_chars=100000):
        """Smart text builder — keeps beginning + recent end for very long convos"""
        lines = []
        for m in msgs:
            role = "Human" if m.role == "user" else "Assistant"
            lines.append(f"{role}: {m.content[:4000]}")
        full = "\n\n".join(lines)
        if len(full) <= max_chars:
            return full, len(msgs)
        # Keep first 15% (context establishment) + last 70% (recent work)
        first_cut = max_chars // 7
        last_cut = int(max_chars * 0.7)
        omitted = total - 10 - 15
        return (f"{full[:first_cut]}\n\n"
                f"[... {omitted} messages omitted for length — total conversation: {total} messages ...]\n\n"
                f"{full[-last_cut:]}"), len(msgs)

    conv_text, used_msgs = build_conv_text(messages)

    prompt = f"""You are StreamContext's AI engine, helping users continue AI conversations in fresh chat windows.
    
The user had a conversation with {total} messages total and needs to continue it in a new tab.

Create a "Context Transfer Document" — a comprehensive brief that lets the new AI chat pick up EXACTLY where things left off.

CRITICAL RULES:
- Be SPECIFIC: include actual file names, paths, commands, values, code snippets
- Be COMPLETE: capture ALL decisions, todos, and current state
- Be ACTIONABLE: the new chat should know exactly what to do next
- Include VERBATIM the last 3-5 exchanges so the flow is preserved

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

# 🌊 StreamContext Context Transfer
*Conversation: {total} messages | Platform: {data.platform} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*

---

## 👤 About This User
[Name, role, location, tech setup, goals — be specific]

## 🎯 Active Task
[The SPECIFIC thing being worked on right now — one clear sentence]

## ✅ Completed This Session
[Bulleted list — specific file names, commands that ran, things that worked]

## 🔧 Current System State  
[What's running, what's configured, what's installed, URLs, ports]

## 💾 Critical Details
[File paths, API keys referenced, config values, URLs, specific numbers/IDs]

## 🐛 Issues & Resolutions
[Problems hit and how they were solved — or still open issues]

## 💡 Key Decisions Made
[Important choices and the reasoning — affects what to do next]

## ⏭️ Immediate Next Steps
[Numbered list of what to do next, in order]

## 🗣️ Last Exchanges (verbatim)
[Copy the last 4-6 message exchanges EXACTLY as they appeared]

---

*Continue seamlessly — you have full context of everything above.*

CONVERSATION TO ANALYZE:
{conv_text}"""

    try:
        client = get_client()
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        # Save to DB
        c = get_db()
        c.execute("""INSERT INTO summaries (conversation_id,summary,model,created_at,message_count,tokens_used)
                     VALUES (?,?,?,?,?,?)""",
                  (cid, summary, model, datetime.now().isoformat(), total, tokens))
        c.execute("UPDATE conversations SET summary_count = summary_count + 1 WHERE id=?", (cid,))
        c.commit()
        c.close()

        return {
            "ok": True,
            "summary": summary,
            "message_count": total,
            "model": model,
            "tokens_used": tokens
        }

    except anthropic.AuthenticationError:
        raise HTTPException(401, "Invalid Anthropic API key. Check your .env file.")
    except anthropic.RateLimitError:
        raise HTTPException(429, "Rate limit reached. Try again in a moment.")
    except Exception as e:
        # Fallback: recent messages without AI
        recent = messages[-12:]
        fallback = f"# 🌊 StreamContext Context Transfer\n*{total} messages | Offline mode*\n\n---\n\n## Recent Conversation\n\n"
        for m in recent:
            role = "👤 You" if m.role == "user" else "🤖 AI"
            fallback += f"**{role}:** {m.content[:600]}\n\n---\n\n"
        fallback += "\n*Please continue from where we left off.*"
        return {"ok": True, "summary": fallback, "message_count": total, "fallback": True, "error": str(e)}

@app.get("/conversations")
def list_conversations(limit: int = 50, offset: int = 0, platform: Optional[str] = None):
    c = get_db()
    if platform:
        rows = c.execute("""SELECT id,platform,title,message_count,summary_count,created_at,updated_at
                            FROM conversations WHERE platform=?
                            ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                         (platform, limit, offset)).fetchall()
    else:
        rows = c.execute("""SELECT id,platform,title,message_count,summary_count,created_at,updated_at
                            FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                         (limit, offset)).fetchall()
    total = c.execute("SELECT COUNT(*) as n FROM conversations").fetchone()['n']
    c.close()
    return {
        "conversations": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/conversations/{cid}")
def get_conversation(cid: str):
    c = get_db()
    conv = c.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msgs = c.execute("SELECT role,content,timestamp FROM messages WHERE conversation_id=? ORDER BY id",
                     (cid,)).fetchall()
    summs = c.execute("SELECT id,summary,model,created_at,message_count FROM summaries WHERE conversation_id=? ORDER BY id DESC",
                      (cid,)).fetchall()
    c.close()
    return {
        **dict(conv),
        "messages": [dict(m) for m in msgs],
        "summaries": [dict(s) for s in summs]
    }

@app.delete("/conversations/{cid}")
def delete_conversation(cid: str):
    c = get_db()
    c.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    c.execute("DELETE FROM summaries WHERE conversation_id=?", (cid,))
    c.execute("DELETE FROM conversations WHERE id=?", (cid,))
    c.commit()
    c.close()
    return {"ok": True}

@app.get("/settings")
def get_settings():
    c = get_db()
    rows = c.execute("SELECT key,value FROM settings").fetchall()
    c.close()
    return {r['key']: r['value'] for r in rows}

@app.post("/settings")
async def update_settings(request: Request):
    data = await request.json()
    c = get_db()
    now = datetime.now().isoformat()
    for k, v in data.items():
        c.execute("INSERT OR REPLACE INTO settings VALUES (?,?,?)", (k, str(v), now))
    c.commit()
    c.close()
    return {"ok": True}

# ─── UI Pages ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def archive():
    return ARCHIVE_HTML

@app.get("/onboarding", response_class=HTMLResponse)
def onboarding():
    return ONBOARDING_HTML

# ─── HTML Pages ───────────────────────────────────────────────────────────────

ARCHIVE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>StreamContext — Archive</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #070710; --surface: #0d0d1f; --surface2: #12122a;
    --border: rgba(255,255,255,0.07); --text: #e8e8f0; --text-dim: #666;
    --accent: #00c8ff; --accent2: #0070f3; --success: #00d4aa;
    --danger: #ff4757; --warn: #f59e0b;
  }
  html, body { height: 100%; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
  
  .nav { padding: 0 32px; height: 56px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; backdrop-filter: blur(12px); }
  .nav-left { display: flex; align-items: center; gap: 12px; }
  .nav-logo { font-size: 22px; filter: drop-shadow(0 0 8px rgba(0,200,255,0.5)); }
  .nav-brand { font-size: 16px; font-weight: 800; background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .nav-right { display: flex; align-items: center; gap: 8px; }
  .nav-btn { padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text-dim); font-family: inherit; transition: all 0.2s; }
  .nav-btn:hover { color: var(--text); border-color: rgba(255,255,255,0.15); }
  .nav-btn.primary { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #000; border: none; }
  .nav-btn.primary:hover { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(0,200,255,0.3); }
  
  .container { max-width: 1100px; margin: 0 auto; padding: 32px; }
  
  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .stat-card-num { font-size: 28px; font-weight: 800; color: var(--accent); }
  .stat-card-label { font-size: 12px; color: var(--text-dim); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  
  .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .section-title { font-size: 14px; font-weight: 700; color: var(--text); }
  .section-meta { font-size: 12px; color: var(--text-dim); }
  
  .filter-bar { display: flex; gap: 8px; margin-bottom: 16px; }
  .filter-btn { padding: 6px 14px; border-radius: 20px; font-size: 12px; cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text-dim); font-family: inherit; transition: all 0.2s; }
  .filter-btn.active, .filter-btn:hover { background: rgba(0,200,255,0.1); color: var(--accent); border-color: rgba(0,200,255,0.2); }
  
  .conv-grid { display: flex; flex-direction: column; gap: 8px; }
  .conv-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
  .conv-card:hover { border-color: rgba(0,200,255,0.2); background: var(--surface2); transform: translateY(-1px); }
  .conv-card-left { flex: 1; min-width: 0; }
  .conv-title { font-size: 14px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }
  .conv-meta { display: flex; align-items: center; gap: 10px; }
  .platform-tag { padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
  .tag-claude { background: rgba(255,100,50,0.12); color: #ff6432; }
  .tag-chatgpt { background: rgba(16,163,127,0.12); color: #10a37f; }
  .meta-item { font-size: 11px; color: var(--text-dim); }
  .conv-card-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .icon-btn { width: 30px; height: 30px; border-radius: 7px; border: 1px solid var(--border); background: var(--surface2); color: var(--text-dim); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 13px; transition: all 0.2s; }
  .icon-btn:hover { color: var(--danger); border-color: rgba(255,71,87,0.3); background: rgba(255,71,87,0.08); }
  
  .empty { text-align: center; padding: 80px 20px; }
  .empty-icon { font-size: 56px; margin-bottom: 16px; filter: grayscale(0.5); }
  .empty-title { font-size: 18px; font-weight: 700; color: var(--text); margin-bottom: 8px; }
  .empty-sub { font-size: 14px; color: var(--text-dim); max-width: 400px; margin: 0 auto; }
  
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.75); backdrop-filter: blur(4px); z-index: 1000; display: none; align-items: center; justify-content: center; padding: 20px; }
  .modal-overlay.open { display: flex; }
  .modal { background: var(--surface); border: 1px solid rgba(0,200,255,0.15); border-radius: 16px; width: 800px; max-width: 95vw; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 24px 80px rgba(0,0,0,0.6); }
  .modal-header { padding: 20px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
  .modal-title { font-size: 16px; font-weight: 700; }
  .modal-close { background: none; border: none; color: var(--text-dim); font-size: 20px; cursor: pointer; padding: 4px 8px; border-radius: 6px; }
  .modal-close:hover { background: var(--surface2); }
  .modal-body { padding: 20px 24px; overflow-y: auto; flex: 1; }
  .summary-text { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; line-height: 1.7; color: #c8c8d8; white-space: pre-wrap; overflow-x: auto; max-height: 400px; overflow-y: auto; }
  .modal-actions { display: flex; gap: 8px; margin-bottom: 16px; }

  .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 600; }
  .badge-blue { background: rgba(0,200,255,0.1); color: var(--accent); border: 1px solid rgba(0,200,255,0.15); }
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-left">
    <span class="nav-logo">🌊</span>
    <span class="nav-brand">StreamContext</span>
    <span class="badge badge-blue" id="version-badge">v2.0</span>
  </div>
  <div class="nav-right">
    <button class="nav-btn" onclick="location.reload()">↻ Refresh</button>
    <button class="nav-btn primary" onclick="window.open('https://github.com/KranthiNallagatla/streamcontext','_blank')">⭐ GitHub</button>
  </div>
</nav>

<div class="container">
  <div class="stats-grid" id="stats-grid">
    <div class="stat-card"><div class="stat-card-num">-</div><div class="stat-card-label">Conversations</div></div>
    <div class="stat-card"><div class="stat-card-num">-</div><div class="stat-card-label">Messages Saved</div></div>
    <div class="stat-card"><div class="stat-card-num">-</div><div class="stat-card-label">Contexts Generated</div></div>
    <div class="stat-card"><div class="stat-card-num">🔒</div><div class="stat-card-label">100% Local</div></div>
  </div>

  <div class="section-header">
    <span class="section-title">Conversations</span>
    <span class="section-meta" id="conv-meta">Loading...</span>
  </div>
  
  <div class="filter-bar">
    <button class="filter-btn active" data-filter="all" onclick="filterConvs('all',this)">All</button>
    <button class="filter-btn" data-filter="claude" onclick="filterConvs('claude',this)">Claude</button>
    <button class="filter-btn" data-filter="chatgpt" onclick="filterConvs('chatgpt',this)">ChatGPT</button>
  </div>
  
  <div class="conv-grid" id="conv-grid">
    <div class="empty">
      <div class="empty-icon">🌊</div>
      <div class="empty-title">Loading...</div>
    </div>
  </div>
</div>

<!-- Summary Modal -->
<div class="modal-overlay" id="modal">
  <div class="modal">
    <div class="modal-header">
      <span class="modal-title" id="modal-title">Context Transfer Document</span>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="modal-actions">
        <button class="nav-btn primary" id="modal-copy-btn" onclick="copyModalText()">📋 Copy Context</button>
        <button class="nav-btn" onclick="closeModal()">Close</button>
      </div>
      <pre class="summary-text" id="modal-text"></pre>
    </div>
  </div>
</div>

<script>
let allConvs = [];
let currentFilter = 'all';

async function loadData() {
  try {
    const [health, convData] = await Promise.all([
      fetch('/health').then(r=>r.json()),
      fetch('/conversations?limit=100').then(r=>r.json())
    ]);
    
    // Update stats
    const grid = document.getElementById('stats-grid');
    grid.innerHTML = `
      <div class="stat-card"><div class="stat-card-num">${health.conversations}</div><div class="stat-card-label">Conversations</div></div>
      <div class="stat-card"><div class="stat-card-num">${health.messages > 999 ? (health.messages/1000).toFixed(1)+'k' : health.messages}</div><div class="stat-card-label">Messages Saved</div></div>
      <div class="stat-card"><div class="stat-card-num">${health.summaries}</div><div class="stat-card-label">Contexts Generated</div></div>
      <div class="stat-card"><div class="stat-card-num">🔒</div><div class="stat-card-label">100% Local & Private</div></div>
    `;
    
    allConvs = convData.conversations || [];
    document.getElementById('conv-meta').textContent = `${allConvs.length} conversations`;
    renderConvs(allConvs);
  } catch(e) {
    document.getElementById('conv-grid').innerHTML = `<div class="empty"><div class="empty-icon">⚠️</div><div class="empty-title">Service not running</div><div class="empty-sub">Start the service: python3 ~/streamcontext/service/main.py</div></div>`;
  }
}

function filterConvs(filter, btn) {
  currentFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const filtered = filter === 'all' ? allConvs : allConvs.filter(c => c.platform === filter);
  renderConvs(filtered);
}

function renderConvs(convs) {
  const grid = document.getElementById('conv-grid');
  if (convs.length === 0) {
    grid.innerHTML = `<div class="empty"><div class="empty-icon">🌊</div><div class="empty-title">No conversations yet</div><div class="empty-sub">Start chatting on Claude.ai or ChatGPT with the StreamContext extension installed.</div></div>`;
    return;
  }
  grid.innerHTML = convs.map(c => `
    <div class="conv-card" onclick="openConv('${c.id}')">
      <div class="conv-card-left">
        <div class="conv-title">${escHtml(c.title || 'Untitled Conversation')}</div>
        <div class="conv-meta">
          <span class="platform-tag tag-${c.platform}">${c.platform}</span>
          <span class="meta-item">💬 ${c.message_count} messages</span>
          ${c.summary_count > 0 ? `<span class="meta-item">📋 ${c.summary_count} contexts</span>` : ''}
          <span class="meta-item">🕐 ${timeAgo(c.updated_at)}</span>
        </div>
      </div>
      <div class="conv-card-right">
        <button class="icon-btn" onclick="event.stopPropagation();deleteConv('${c.id}')" title="Delete">🗑</button>
      </div>
    </div>
  `).join('');
}

async function openConv(id) {
  try {
    const data = await fetch(`/conversations/${id}`).then(r=>r.json());
    const summaries = data.summaries || [];
    if (summaries.length > 0) {
      showModal(data.title || 'Conversation', summaries[0].summary);
    } else {
      // Generate new context
      const msgs = data.messages || [];
      if (msgs.length === 0) return;
      const result = await fetch(`/conversations/${id}/summarize`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({messages: msgs, platform: data.platform})
      }).then(r=>r.json());
      showModal(data.title || 'Conversation', result.summary);
      loadData();
    }
  } catch(e) { alert('Error: ' + e.message); }
}

async function deleteConv(id) {
  if (!confirm('Delete this conversation?')) return;
  await fetch(`/conversations/${id}`, {method:'DELETE'});
  allConvs = allConvs.filter(c => c.id !== id);
  renderConvs(currentFilter === 'all' ? allConvs : allConvs.filter(c => c.platform === currentFilter));
}

function showModal(title, text) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-text').textContent = text;
  document.getElementById('modal').classList.add('open');
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
}

function copyModalText() {
  navigator.clipboard.writeText(document.getElementById('modal-text').textContent)
    .then(() => {
      document.getElementById('modal-copy-btn').textContent = '✅ Copied!';
      setTimeout(() => document.getElementById('modal-copy-btn').textContent = '📋 Copy Context', 2000);
    });
}

function timeAgo(iso) {
  const d = new Date(iso), now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
  return Math.floor(diff/86400) + 'd ago';
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

document.getElementById('modal').addEventListener('click', e => {
  if (e.target.id === 'modal') closeModal();
});

loadData();
</script>
</body>
</html>"""

ONBOARDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Welcome to StreamContext</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #070710; color: #e8e8f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 40px 20px; }
  .card { max-width: 560px; width: 100%; background: #0d0d1f; border: 1px solid rgba(0,200,255,0.15); border-radius: 20px; padding: 40px; box-shadow: 0 24px 80px rgba(0,0,0,0.5); }
  .logo { font-size: 48px; text-align: center; margin-bottom: 16px; filter: drop-shadow(0 0 20px rgba(0,200,255,0.5)); }
  h1 { font-size: 28px; font-weight: 800; text-align: center; background: linear-gradient(135deg, #00c8ff, #0070f3); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
  .subtitle { text-align: center; color: #666; font-size: 14px; margin-bottom: 32px; }
  .step { display: flex; gap: 16px; margin-bottom: 24px; }
  .step-num { width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #00c8ff, #0070f3); color: #000; font-weight: 800; font-size: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .step-content h3 { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
  .step-content p { font-size: 13px; color: #888; line-height: 1.5; }
  .step-content code { background: #070710; border: 1px solid rgba(255,255,255,0.07); border-radius: 5px; padding: 2px 6px; font-family: 'SF Mono', monospace; font-size: 11px; color: #00c8ff; }
  .btn { display: block; width: 100%; padding: 14px; background: linear-gradient(135deg, #00c8ff, #0070f3); border: none; border-radius: 10px; color: #000; font-size: 15px; font-weight: 800; cursor: pointer; margin-top: 24px; font-family: inherit; transition: all 0.2s; text-align: center; text-decoration: none; }
  .btn:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,200,255,0.3); }
</style>
</head>
<body>
<div class="card">
  <div class="logo">🌊</div>
  <h1>Welcome to StreamContext</h1>
  <p class="subtitle">Never lose your AI conversation context again</p>
  
  <div class="step">
    <div class="step-num">1</div>
    <div class="step-content">
      <h3>Service is running ✅</h3>
      <p>The StreamContext local service is running at <code>localhost:7892</code>. Your conversations are being saved locally.</p>
    </div>
  </div>
  
  <div class="step">
    <div class="step-num">2</div>
    <div class="step-content">
      <h3>Install the Chrome extension</h3>
      <p>Open Chrome → <code>chrome://extensions</code> → Enable Developer Mode → Load Unpacked → select <code>~/streamcontext/extension</code></p>
    </div>
  </div>
  
  <div class="step">
    <div class="step-num">3</div>
    <div class="step-content">
      <h3>Start chatting normally</h3>
      <p>Go to <code>claude.ai</code> or <code>chatgpt.com</code>. You'll see the StreamContext bar at the top.</p>
    </div>
  </div>
  
  <div class="step">
    <div class="step-num">4</div>
    <div class="step-content">
      <h3>Click ⚡ Continue Fresh when ready</h3>
      <p>When your chat gets slow or too long, click the button. StreamContext generates a deep context document and opens a fresh chat — automatically!</p>
    </div>
  </div>
  
  <a href="/" class="btn">Open Archive →</a>
</div>
</body>
</html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print("=" * 55)
    print("  🌊 StreamContext v2.0")
    print("  Never lose your AI conversation context")
    print("=" * 55)
    print(f"  📍 Archive:    http://localhost:7892")
    print(f"  📡 API:        http://localhost:7892/health")
    print(f"  🔑 API Key:    {'✓ Set' if os.getenv('ANTHROPIC_API_KEY') else '✗ Missing! Add to .env'}")
    print(f"  💾 Database:   {DB_PATH}")
    print("=" * 55)

    uvicorn.run(app, host="127.0.0.1", port=7892, log_level="warning")
