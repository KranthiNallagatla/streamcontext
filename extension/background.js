// StreamContext Background Service Worker

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'openArchive') {
    chrome.tabs.create({ url: 'http://localhost:7892' });
  }
});

// Handle extension install
chrome.runtime.onInstalled.addListener(() => {
  console.log('StreamContext installed!');
});
