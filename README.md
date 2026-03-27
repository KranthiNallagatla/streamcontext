# 🌊 StreamContext

> Never lose your AI conversation context again.

Built by a Kafka engineer. Because conversations are streams — and streams should never be lost.

## The Problem

Your Claude/ChatGPT chat grows long → browser slows down → you start a new chat → **you lose everything**.

Existing Chrome extensions just dump the raw conversation (slow, huge, ugly). StreamContext uses AI to create **intelligent summaries** that fit perfectly in a new chat window.

## How It Works

```
You chat on Claude.ai or ChatGPT
→ StreamContext captures every message locally
→ Chat getting slow? Click "⚡ Continue Fresh"
→ AI generates smart summary (not a raw dump)
→ New chat opens with perfect context injected
→ Continue exactly where you left off
→ Old conversation archived & searchable forever
```

## Demo

```
[Long slow chat with 200 messages]
     ↓ Click "⚡ Continue Fresh"
[StreamContext analyzes conversation]
[Generates 500-word intelligent summary]
[Opens new chat with context injected]
[You continue seamlessly in fast new chat]
```

## Architecture

```
┌─────────────────────────────────────────┐
│         Chrome Extension                │
│  Captures messages from Claude/ChatGPT  │
│  Adds "⚡ Continue Fresh" toolbar       │
└──────────────┬──────────────────────────┘
               │ HTTP (localhost:7892)
┌──────────────▼──────────────────────────┐
│         Local Mac Service               │
│  FastAPI + SQLite                       │
│  Stores all conversations locally       │
│  Generates AI summaries via Claude API  │
│  Serves beautiful archive UI            │
└─────────────────────────────────────────┘
```

## Quick Start

### Step 1 — Start the local service

```bash
cd service
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
python main.py
```

Service runs at **http://localhost:7892**

### Step 2 — Install Chrome extension

1. Open Chrome → `chrome://extensions`
2. Enable **Developer Mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. Done! 🎉

### Step 3 — Start chatting!

Go to **claude.ai** or **chatgpt.com**.

You'll see the StreamContext bar at the top of every chat.

When your chat gets slow — click **⚡ Continue Fresh**.

## Features

| Feature | Status |
|---|---|
| Auto-capture messages | ✅ |
| Smart AI summary | ✅ |
| One-click continue | ✅ |
| Full conversation archive | ✅ |
| Beautiful archive UI | ✅ |
| 100% local & private | ✅ |
| Works on Claude.ai | ✅ |
| Works on ChatGPT | ✅ |
| Runs 24/7 on Mac mini | ✅ |
| Firefox support | 🔜 |
| Semantic search | 🔜 |

## Why "StreamContext"?

Built by a Kafka engineer. Conversations are **event streams** — every message is an event. StreamContext is the consumer that persists your stream and lets you continue from any point.

Just like Kafka never loses events, StreamContext never loses your conversations.

## Privacy

- ✅ 100% local — nothing leaves your machine
- ✅ SQLite database stored in `~/.streamcontext/`  
- ✅ No accounts, no cloud, no tracking
- ✅ Your API key stays in your `.env` file

## Tech Stack

- **Chrome Extension** — Vanilla JS, Manifest V3
- **Local Service** — Python FastAPI + SQLite
- **AI Summarization** — Claude Haiku (fast & cheap)
- **Archive UI** — Clean dark terminal aesthetic

## License

MIT — built for the community 🌊
