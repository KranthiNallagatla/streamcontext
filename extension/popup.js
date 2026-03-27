const SERVICE_URL = 'http://localhost:7892';

async function init() {
  await checkService();
  setupButtons();
}

async function checkService() {
  const dot = document.getElementById('status-dot');
  const label = document.getElementById('status-label');
  const sub = document.getElementById('status-sub');
  const startBtn = document.getElementById('start-btn');
  const statsSection = document.getElementById('stats-section');
  const setupSection = document.getElementById('setup-section');

  try {
    const r = await fetch(`${SERVICE_URL}/health`, { signal: AbortSignal.timeout(2500) });
    if (!r.ok) throw new Error();
    const data = await r.json();

    dot.className = 'status-dot dot-green';
    label.textContent = 'Service Running';
    sub.textContent = `v${data.version} · ${data.conversations} conversations`;
    startBtn.style.display = 'none';
    statsSection.style.display = 'block';
    setupSection.style.display = 'none';

    document.getElementById('stat-convs').textContent = data.conversations || 0;
    document.getElementById('stat-msgs').textContent = data.messages > 999
      ? `${(data.messages/1000).toFixed(1)}k` : data.messages || 0;

  } catch (e) {
    dot.className = 'status-dot dot-red';
    label.textContent = 'Service Offline';
    sub.textContent = 'Start the local service to begin';
    startBtn.style.display = 'block';
    statsSection.style.display = 'none';
    setupSection.style.display = 'block';
  }
}

function setupButtons() {
  document.getElementById('btn-archive').onclick = () => {
    chrome.tabs.create({ url: `${SERVICE_URL}` });
    window.close();
  };

  document.getElementById('btn-github').onclick = () => {
    chrome.tabs.create({ url: 'https://github.com/KranthiNallagatla/streamcontext' });
    window.close();
  };

  document.getElementById('btn-settings').onclick = () => {
    chrome.tabs.create({ url: `${SERVICE_URL}/settings` });
    window.close();
  };

  document.getElementById('btn-docs').onclick = () => {
    chrome.tabs.create({ url: 'https://github.com/KranthiNallagatla/streamcontext#readme' });
    window.close();
  };

  document.getElementById('btn-feedback').onclick = () => {
    chrome.tabs.create({ url: 'https://github.com/KranthiNallagatla/streamcontext/issues/new' });
    window.close();
  };

  document.getElementById('start-btn').onclick = () => {
    navigator.clipboard.writeText('cd ~/streamcontext/service && python3 main.py')
      .then(() => {
        document.getElementById('start-btn').textContent = '✓ Copied!';
        setTimeout(() => document.getElementById('start-btn').textContent = 'Start Service', 2000);
      });
  };

  document.getElementById('setup-cmd').onclick = () => {
    navigator.clipboard.writeText('cd ~/streamcontext/service && python3 main.py')
      .then(() => {
        document.getElementById('setup-cmd').style.color = '#00d4aa';
        document.getElementById('setup-cmd').textContent = '✓ Copied to clipboard!';
        setTimeout(() => {
          document.getElementById('setup-cmd').style.color = '';
          document.getElementById('setup-cmd').textContent = 'cd ~/streamcontext/service && python3 main.py';
        }, 2000);
      });
  };
}

init();
