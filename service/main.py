"""
StreamContext Local Service
FastAPI + SQLite backend that runs on your Mac 24/7
Captures, stores, and summarizes AI conversations
"""

import os
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import List, Optional
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="StreamContext", version="1.0.0")

# Allow Chrome extension to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path.home() / ".streamcontext" / "conversations.db"
DB_PATH.parent.mkdir(exist_ok=True)

# Initialize DB
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            platform TEXT,
            url TEXT,
            title TEXT,
            created_at TEXT,
            updated_at TEXT,
            message_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            summary TEXT,
            created_at TEXT,
            message_count INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Models
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

# Anthropic client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@app.get("/health")
def health():
    conn = sqlite3.connect(DB_PATH)
    conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    conn.close()
    return {
        "status": "ok",
        "conversations": conv_count,
        "messages": msg_count,
        "version": "1.0.0"
    }

@app.post("/conversations/{conversation_id}/messages")
def save_messages(conversation_id: str, data: ConversationData):
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    
    # Upsert conversation
    existing = conn.execute(
        "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    
    if existing:
        conn.execute("""
            UPDATE conversations 
            SET updated_at = ?, message_count = ?, url = ?, title = ?
            WHERE id = ?
        """, (now, len(data.messages), data.url, data.title, conversation_id))
    else:
        conn.execute("""
            INSERT INTO conversations (id, platform, url, title, created_at, updated_at, message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (conversation_id, data.platform, data.url, data.title, now, now, len(data.messages)))
    
    # Clear old messages and re-insert
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    for msg in data.messages:
        conn.execute("""
            INSERT INTO messages (conversation_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, msg.role, msg.content, now))
    
    conn.commit()
    conn.close()
    return {"saved": len(data.messages)}

@app.post("/conversations/{conversation_id}/summarize")
async def summarize(conversation_id: str, data: SummarizeRequest):
    messages = data.messages
    
    if not messages:
        raise HTTPException(status_code=400, detail="No messages to summarize")
    
    # Build conversation text
    conv_text = "\n\n".join([
        f"{'Human' if m.role == 'user' else 'Assistant'}: {m.content[:1000]}"
        for m in messages[-40:]  # Last 40 messages
    ])
    
    # Use Claude Haiku for fast, cheap summarization
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": f"""You are summarizing an AI conversation so it can be continued in a fresh chat.

Create a smart context summary that:
1. Captures the KEY decisions, conclusions, and important facts
2. Lists what was built/created/decided
3. Notes the current state and what comes next
4. Is concise but complete (aim for 400-600 words)
5. Starts with "# Continuing Previous Conversation" 
6. Ends with "Please continue from where we left off."

Do NOT dump the raw conversation. Intelligently synthesize it.

CONVERSATION:
{conv_text}

Create the smart context summary now:"""
            }]
        )
        
        summary = response.content[0].text
        
        # Save summary to DB
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO summaries (conversation_id, summary, created_at, message_count)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, summary, datetime.now().isoformat(), len(messages)))
        conn.commit()
        conn.close()
        
        return {"summary": summary, "message_count": len(messages)}
    
    except Exception as e:
        # Fallback summary
        recent = messages[-10:]
        fallback = "# Continuing Previous Conversation\n\n"
        fallback += "## Recent Context\n\n"
        for m in recent:
            fallback += f"**{'You' if m.role == 'user' else 'AI'}**: {m.content[:300]}\n\n"
        fallback += "\nPlease continue from where we left off."
        return {"summary": fallback, "message_count": len(messages), "fallback": True}

@app.get("/conversations")
def list_conversations():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT id, platform, title, message_count, created_at, updated_at
        FROM conversations
        ORDER BY updated_at DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return [{
        "id": r[0], "platform": r[1], "title": r[2],
        "message_count": r[3], "created_at": r[4], "updated_at": r[5]
    } for r in rows]

@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    conn = sqlite3.connect(DB_PATH)
    conv = conn.execute(
        "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")
    messages = conn.execute(
        "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY id",
        (conversation_id,)
    ).fetchall()
    conn.close()
    return {
        "id": conv[0], "platform": conv[1], "url": conv[2],
        "title": conv[3], "messages": [{"role": m[0], "content": m[1]} for m in messages]
    }

@app.get("/", response_class=HTMLResponse)
def archive_ui():
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>StreamContext Archive</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'JetBrains Mono', monospace; background: #0a0a1a; color: #e8e8f0; min-height: 100vh; }
  .header { padding: 24px 32px; background: #111128; border-bottom: 1px solid rgba(0,200,255,0.15); display: flex; align-items: center; gap: 12px; }
  .logo { font-size: 28px; filter: drop-shadow(0 0 10px #00c8ff); }
  .title { font-size: 20px; font-weight: 700; color: #00c8ff; }
  .subtitle { font-size: 11px; color: #555; margin-top: 2px; }
  .content { max-width: 900px; margin: 32px auto; padding: 0 32px; }
  .section-label { font-size: 10px; letter-spacing: 2px; color: #555; text-transform: uppercase; margin-bottom: 12px; }
  .conv-list { display: flex; flex-direction: column; gap: 8px; }
  .conv-card { background: #111128; border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 16px; cursor: pointer; transition: all 0.2s; }
  .conv-card:hover { border-color: rgba(0,200,255,0.2); background: #15152a; }
  .conv-title { font-size: 13px; font-weight: 600; color: #e8e8f0; margin-bottom: 4px; }
  .conv-meta { font-size: 10px; color: #555; display: flex; gap: 12px; }
  .platform-badge { padding: 2px 8px; border-radius: 8px; font-size: 9px; font-weight: 600; text-transform: uppercase; }
  .platform-claude { background: rgba(255,100,50,0.15); color: #ff6432; }
  .platform-chatgpt { background: rgba(16,163,127,0.15); color: #10a37f; }
  .msg-count { background: rgba(0,200,255,0.1); color: #00c8ff; padding: 2px 6px; border-radius: 6px; font-size: 9px; }
  .empty { text-align: center; padding: 60px; color: #555; }
  .empty-icon { font-size: 48px; margin-bottom: 12px; }
  .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }
  .stat-box { background: #111128; border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 16px; text-align: center; }
  .stat-num { font-size: 24px; font-weight: 700; color: #00c8ff; }
  .stat-label { font-size: 10px; color: #555; margin-top: 4px; }
</style>
</head>
<body>
<div class="header">
  <span class="logo">🌊</span>
  <div>
    <div class="title">StreamContext Archive</div>
    <div class="subtitle">All your AI conversations, preserved forever</div>
  </div>
</div>
<div class="content">
  <div class="stats-row" id="stats"></div>
  <div class="section-label">Recent Conversations</div>
  <div class="conv-list" id="conv-list">
    <div class="empty"><div class="empty-icon">💬</div>No conversations yet.<br>Start chatting on Claude.ai or ChatGPT!</div>
  </div>
</div>
<script>
async function load() {
  try {
    const health = await fetch('/health').then(r => r.json());
    document.getElementById('stats').innerHTML = `
      <div class="stat-box"><div class="stat-num">${health.conversations}</div><div class="stat-label">Conversations</div></div>
      <div class="stat-box"><div class="stat-num">${health.messages}</div><div class="stat-label">Messages Saved</div></div>
      <div class="stat-box"><div class="stat-num">100%</div><div class="stat-label">Local & Private</div></div>
    `;
    
    const convs = await fetch('/conversations').then(r => r.json());
    if (convs.length > 0) {
      document.getElementById('conv-list').innerHTML = convs.map(c => `
        <div class="conv-card" onclick="window.open('/conversations/${c.id}', '_blank')">
          <div class="conv-title">${c.title || 'Untitled Conversation'}</div>
          <div class="conv-meta">
            <span class="platform-badge platform-${c.platform}">${c.platform}</span>
            <span class="msg-count">${c.message_count} messages</span>
            <span>${new Date(c.updated_at).toLocaleDateString()}</span>
          </div>
        </div>
      `).join('');
    }
  } catch(e) {
    console.error(e);
  }
}
load();
</script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn
    print("🌊 StreamContext Service starting...")
    print("📍 Running at: http://localhost:7892")
    print("📚 Archive UI: http://localhost:7892")
    print("🔑 API Key:", "✓ Set" if os.getenv("ANTHROPIC_API_KEY") else "✗ Missing — add to .env")
    uvicorn.run(app, host="127.0.0.1", port=7892, log_level="warning")
