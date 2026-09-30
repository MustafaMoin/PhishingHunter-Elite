/**
 * popup.js
 * --------
 * Popup logic for PhishingHunter extension
 */

// DOM elements
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const resultsEl = document.getElementById('results');
const errorEndpointEl = document.getElementById('errorEndpoint');

const riskScoreEl = document.getElementById('riskScore');
const riskLevelEl = document.getElementById('riskLevel');
const riskFillEl = document.getElementById('riskFill');
const urlDisplayEl = document.getElementById('urlDisplay');
const domainChipEl = document.getElementById('domainChip');

const statSignalsEl = document.getElementById('statSignals');
const statTimeEl = document.getElementById('statTime');
const statCachedEl = document.getElementById('statCached');
const signalsListEl = document.getElementById('signalsList');

const btnDetailsEl = document.getElementById('btnDetails');
const btnFeedbackEl = document.getElementById('btnFeedback');
const btnSettingsEl = document.getElementById('btnSettings');
const btnOptionsFooterEl = document.getElementById('btnOptionsFooter');

let currentUrl = '';
let currentResult = null;

/**
 * Initialize popup
 */
async function init() {
  showLoading();
  
  try {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab || !tab.url) {
      showError('No active tab found');
      return;
    }
    
    currentUrl = tab.url;
    
    // Check if we should skip this URL
    if (shouldSkipUrl(currentUrl)) {
      showError('This page cannot be scanned (internal/local URL)');
      return;
    }
    
    // Try to get cached result from storage
    const storageKey = `scan_${tab.id}`;
    const stored = await chrome.storage.local.get([storageKey]);
    
    if (stored[storageKey] && stored[storageKey].url === currentUrl) {
      // Use stored result
      currentResult = stored[storageKey].result;
      displayResult(currentResult);
      return;
    }
    
    // No cached result, trigger scan
    chrome.runtime.sendMessage(
      { action: 'scanUrl', url: currentUrl },
      (response) => {
        if (response && response.result) {
          currentResult = response.result;
          displayResult(currentResult);
        } else {
          showError('Unable to scan URL');
        }
      }
    );
    
  } catch (error) {
    console.error('Init error:', error);
    showError(error.message || 'Unknown error');
  }
}

/**
 * Check if URL should be skipped
 */
function shouldSkipUrl(url) {
  const skipPatterns = [
    /^chrome:/,
    /^chrome-extension:/,
    /^about:/,
    /^edge:/,
    /^file:/,
    /^localhost/,
    /^127\.0\.0\.1/,
  ];
  
  return skipPatterns.some(pattern => pattern.test(url));
}

/**
 * Show loading state
 */
function showLoading() {
  loadingEl.classList.remove('hidden');
  errorEl.classList.add('hidden');
  resultsEl.classList.add('hidden');
}

/**
 * Show error state
 */
function showError(message) {
  loadingEl.classList.add('hidden');
  resultsEl.classList.add('hidden');
  errorEl.classList.remove('hidden');
  
  const errorText = errorEl.querySelector('.error-text');
  if (errorText) {
    errorText.textContent = message || 'Unable to connect to PhishingHunter API';
  }
  
  // Get API endpoint and show it
  chrome.runtime.sendMessage({ action: 'getApiEndpoint' }, (response) => {
    if (response && response.endpoint) {
      errorEndpointEl.textContent = response.endpoint;
    }
  });
}

/**
 * Display scan result
 */
function displayResult(result) {
  loadingEl.classList.add('hidden');
  errorEl.classList.add('hidden');
  resultsEl.classList.remove('hidden');
  
  // Risk score
  const score = result.score || 0;
  const risk = result.risk || 'UNKNOWN';
  
  riskScoreEl.textContent = score;
  riskLevelEl.textContent = risk;
  riskFillEl.style.width = `${Math.min(score, 100)}%`;
  
  // Apply color classes
  riskScoreEl.className = 'risk-score';
  riskFillEl.className = 'risk-fill';
  
  if (risk === 'SAFE') {
    riskScoreEl.classList.add('safe');
    riskFillEl.classList.add('safe');
  } else if (risk === 'LOW RISK') {
    riskScoreEl.classList.add('low');
    riskFillEl.classList.add('low');
  } else if (risk === 'HIGH RISK') {
    riskScoreEl.classList.add('high');
    riskFillEl.classList.add('high');
  } else if (risk === 'PHISHING') {
    riskScoreEl.classList.add('phishing');
    riskFillEl.classList.add('phishing');
  }
  
  // URL info
  urlDisplayEl.textContent = result.url || currentUrl;
  urlDisplayEl.title = result.url || currentUrl;
  domainChipEl.textContent = result.domain || '—';
  
  // Stats
  const signals = result.signals || [];
  statSignalsEl.textContent = signals.length;
  statTimeEl.textContent = `${result.scan_time_ms || 0}ms`;
  statCachedEl.textContent = result.cached ? 'YES' : 'NO';
  
  // Top signals (show top 5)
  signalsListEl.innerHTML = '';
  const topSignals = signals
    .filter(s => s.points > 0) // Only positive points
    .slice(0, 5);
  
  if (topSignals.length === 0) {
    signalsListEl.innerHTML = '<div style="text-align:center;color:#00ff8866;font-size:11px;padding:20px;">No threat signals detected</div>';
  } else {
    topSignals.forEach(signal => {
      const item = document.createElement('div');
      item.className = `signal-item ${signal.severity || 'info'}`;
      
      item.innerHTML = `
        <div class="signal-header">
          <div class="signal-key">${escapeHtml(signal.key || '').replace(/_/g, ' ')}</div>
          <div class="signal-points">+${signal.points}</div>
        </div>
        <div class="signal-detail">${escapeHtml(signal.detail || '')}</div>
      `;
      
      signalsListEl.appendChild(item);
    });
  }
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

/**
 * Open full report in new tab
 */
function openFullReport() {
  if (!currentUrl) return;
  
  chrome.runtime.sendMessage({ action: 'getApiEndpoint' }, (response) => {
    if (response && response.endpoint) {
      // Extract base URL from API endpoint
      const baseUrl = response.endpoint.replace('/api/check', '');
      window.open(baseUrl, '_blank');
    }
  });
}

/**
 * Open feedback/report issue
 */
function openFeedback() {
  if (!currentResult) return;
  
  // In a real implementation, this would open a feedback form
  alert('Feedback feature coming soon!\n\nYou can report false positives/negatives through the main dashboard.');
}

/**
 * Open options page
 */
function openOptions() {
  chrome.runtime.openOptionsPage();
}

// Event listeners
btnDetailsEl.addEventListener('click', openFullReport);
btnFeedbackEl.addEventListener('click', openFeedback);
btnSettingsEl.addEventListener('click', openOptions);
btnOptionsFooterEl.addEventListener('click', openOptions);

// Initialize on load
init();
