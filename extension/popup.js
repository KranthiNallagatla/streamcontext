const SERVICE_URL = 'http://localhost:7892';

async function checkService() {
  try {
    const res = await fetch(`${SERVICE_URL}/health`, { signal: AbortSignal.timeout(2000) });
    const data = await res.json();
    
    document.getElementById('service-dot').className = 'dot dot-green';
    document.getElementById('service-status').textContent = 'Running ✓';
    document.getElementById('conv-count').textContent = data.conversations || '0';
    document.getElementById('msg-count').textContent = data.messages || '0';
  } catch (e) {
    document.getElementById('service-dot').className = 'dot dot-red';
    document.getElementById('service-status').textContent = 'Not running — start with: python service/main.py';
    document.getElementById('conv-count').textContent = '?';
    document.getElementById('msg-count').textContent = '?';
  }
}

document.getElementById('open-archive').addEventListener('click', () => {
  chrome.tabs.create({ url: `${SERVICE_URL}` });
});

document.getElementById('open-settings').addEventListener('click', () => {
  chrome.tabs.create({ url: `${SERVICE_URL}/settings` });
});

checkService();
