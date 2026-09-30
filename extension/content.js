/**
 * content.js
 * ----------
 * Content script injected into web pages to display warning banners
 */

// Track if banner is already shown
let bannerShown = false;

/**
 * Create and inject warning banner
 */
function showWarningBanner(result) {
  // Don't show duplicate banners
  if (bannerShown) return;
  bannerShown = true;
  
  const banner = document.createElement('div');
  banner.id = 'phishinghunter-warning';
  banner.className = 'phishinghunter-banner';
  
  const risk = result.risk || 'HIGH RISK';
  const score = result.score || 0;
  const domain = result.domain || window.location.hostname;
  
  banner.innerHTML = `
    <div class="phishing-banner-content">
      <div class="banner-icon">⚠️</div>
      <div class="banner-main">
        <div class="banner-title">${risk} DETECTED</div>
        <div class="banner-subtitle">
          This site (${escapeHtml(domain)}) has been flagged with a risk score of ${score}/100
        </div>
        <div class="banner-message">
          PhishingHunter detected suspicious signals. Exercise caution and avoid entering sensitive information.
        </div>
      </div>
      <div class="banner-actions">
        <button class="banner-btn-details" id="phishing-banner-details">View Details</button>
        <button class="banner-btn-dismiss" id="phishing-banner-dismiss">✕</button>
      </div>
    </div>
  `;
  
  document.body.prepend(banner);
  
  // Animate in
  setTimeout(() => {
    banner.classList.add('show');
  }, 100);
  
  // Event listeners
  document.getElementById('phishing-banner-dismiss').addEventListener('click', () => {
    banner.classList.remove('show');
    setTimeout(() => {
      banner.remove();
      bannerShown = false;
    }, 300);
  });
  
  document.getElementById('phishing-banner-details').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'getApiEndpoint' }, (response) => {
      if (response && response.endpoint) {
        const baseUrl = response.endpoint.replace('/api/check', '');
        window.open(baseUrl, '_blank');
      }
    });
  });
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Listen for messages from background script
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'showWarning' && message.result) {
    showWarningBanner(message.result);
  }
});

console.log('PhishingHunter content script loaded');
