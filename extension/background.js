// StreamContext v2.0 — Background Service Worker

const SERVICE_URL = 'http://localhost:7892';

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'openArchive') {
    chrome.tabs.create({ url: `${SERVICE_URL}` });
  }
  if (message.action === 'checkService') {
    fetch(`${SERVICE_URL}/health`, { signal: AbortSignal.timeout(2000) })
      .then(r => r.json())
      .then(data => sendResponse({ ok: true, data }))
      .catch(() => sendResponse({ ok: false }));
    return true; // Keep channel open for async
  }
});

// On install, open onboarding
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    chrome.tabs.create({ url: `${SERVICE_URL}/onboarding` });
  }
});

// Badge to show service status
async function updateBadge() {
  try {
    const r = await fetch(`${SERVICE_URL}/health`, { signal: AbortSignal.timeout(2000) });
    if (r.ok) {
      chrome.action.setBadgeText({ text: '' });
      chrome.action.setBadgeBackgroundColor({ color: '#00d4aa' });
    } else {
      throw new Error();
    }
  } catch (e) {
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#ff4757' });
  }
}

// Check service every 60 seconds
setInterval(updateBadge, 60000);
updateBadge();
