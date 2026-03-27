# 🌊 StreamContext

**Never lose your AI conversation context again.**

> Continue any Claude or ChatGPT conversation in a fresh window — with full, intelligent context automatically transferred.

[![Version](https://img.shields.io/badge/version-2.0.0-blue?style=flat-square&color=00c8ff)](https://github.com/KranthiNallagatla/streamcontext)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-yellow?style=flat-square)](https://python.org)

---

## The Problem

Your Claude or ChatGPT conversation grows long → **browser slows to a crawl** → you start a new chat → **you lose everything**.

Existing tools just dump the raw conversation history (slow, huge, misses the point). StreamContext uses Claude to generate an **intelligent Context Transfer Document** — capturing decisions, current state, code snippets, next steps — so the new chat picks up exactly where you left off.

---

## How It Works

```
You chat on Claude.ai or ChatGPT
  ↓
StreamContext captures every message locally
  ↓
Chat getting slow? Click "⚡ Continue Fresh"
  ↓  (takes ~15-20 seconds)
Claude analyzes your entire conversation
  ↓
Generates an 8-section Context Transfer Document
  ↓
Opens new chat + auto-injects context
  ↓
Continue seamlessly — the AI knows everything
```

---

## Features

| Feature | Description |
|---------|-------------|
| ⚡ **One-click continue** | Click Continue Fresh — context is generated and injected automatically |
| 🧠 **Deep AI analysis** | Uses Claude Sonnet to intelligently synthesize conversations, not dump them |
| 🔄 **Auto-inject** | Context is automatically pasted into the new chat — zero manual steps |
| 📚 **Full archive** | Every conversation saved locally, searchable, with context history |
| 🔒 **100% local** | Nothing leaves your machine. SQLite database on your Mac. |
| 🚀 **Auto-start** | Runs as a Mac LaunchAgent — always available, no manual starting |
| 📊 **Progress tracking** | Real-time progress bar during context generation |
| ✅ **Works on both** | Claude.ai and ChatGPT supported |

---

## Quick Start

### Prerequisites
- macOS (tested on macOS 14+)
- Python 3.9+
- Chrome browser
- Anthropic API key ([get one here](https://console.anthropic.com))

### 1. Clone & Setup

```bash
git clone https://github.com/KranthiNallagatla/streamcontext.git
cd streamcontext/service
pip3 install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Start the Service

```bash
python3 main.py
```

Visit **http://localhost:7892** to see the archive.

### 3. Auto-Start on Login (Recommended)

```bash
chmod +x install-autostart.sh && ./install-autostart.sh
```

StreamContext will now start automatically every time you log in.

### 4. Install Chrome Extension

1. Open Chrome → `chrome://extensions`
2. Enable **Developer Mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. The 🌊 StreamContext icon appears in your toolbar

### 5. Use It!

Go to **claude.ai** or **chatgpt.com**. You'll see the StreamContext bar at the top.

When your chat gets slow → click **⚡ Continue Fresh**.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Chrome Extension                    │
│  ┌─────────────────────────────────────────┐    │
│  │  Toolbar: message count + service status │    │
│  │  Content script: captures all messages   │    │
│  │  Auto-inject: pastes context in new chat │    │
│  └────────────────┬────────────────────────┘    │
└───────────────────┼─────────────────────────────┘
                    │ HTTP API (localhost:7892)
┌───────────────────▼─────────────────────────────┐
│              Local Mac Service                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ FastAPI  │  │ SQLite   │  │ Anthropic API│   │
│  │ REST API │  │ Database │  │ Summarization│   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │  Archive UI  ·  Settings  ·  Onboarding  │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## Context Transfer Document Format

StreamContext generates an 8-section document:

```
# 🌊 StreamContext Context Transfer

## 👤 About This User
## 🎯 Active Task  
## ✅ Completed This Session
## 🔧 Current System State
## 💾 Critical Details
## 🐛 Issues & Resolutions
## 💡 Key Decisions Made
## ⏭️ Immediate Next Steps
## 🗣️ Last Exchanges (verbatim)
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health + stats |
| `/conversations` | GET | List all conversations |
| `/conversations/{id}` | GET | Get conversation + messages |
| `/conversations/{id}/messages` | POST | Save messages |
| `/conversations/{id}/summarize` | POST | Generate context |
| `/conversations/{id}` | DELETE | Delete conversation |
| `/settings` | GET/POST | Get/update settings |

---

## Configuration

Settings are stored in the local SQLite database and can be updated via the Settings page (`http://localhost:7892/settings`):

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | `claude-sonnet-4-6` | Claude model for summarization |
| `max_messages_per_summary` | `80` | Max messages to analyze |
| `auto_save_interval` | `5` | Save every N messages |

---

## Privacy

- ✅ Everything stays on your Mac
- ✅ SQLite database at `~/.streamcontext/conversations.db`
- ✅ No accounts, no cloud sync, no telemetry
- ✅ API key stored in local `.env` file only
- ✅ Chrome extension only reads pages you're chatting on

---

## Why "StreamContext"?

Built by a Kafka engineer. Every AI conversation is an **event stream** — each message is an event. StreamContext is the consumer that persists your stream, letting you resume from any point.

Just like Kafka never loses events, StreamContext never loses your conversations.

---

## Roadmap

- [ ] Firefox extension
- [ ] Semantic search across all conversations
- [ ] Automatic context injection without clipboard
- [ ] Multi-device sync (optional, encrypted)
- [ ] Support for more platforms (Gemini, Perplexity, etc.)
- [ ] Chrome Web Store submission

---

## Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — built for the community 🌊

---

*Built with ❤️ by [@KranthiNallagatla](https://github.com/KranthiNallagatla)*
