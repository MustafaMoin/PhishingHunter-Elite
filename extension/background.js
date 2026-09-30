/**
 * background.js
 * -------------
 * Service worker for PhishingHunter browser extension.
 * 
 * Responsibilities:
 * - Monitor tab navigation and check URLs
 * - Maintain scan cache in chrome.storage
 * - Update badge with risk score
 * - Handle context menu clicks
 * - Debounce rapid navigation
 */

// Default API endpoint (can be changed in options)
let API_ENDPOINT = 'http://127.0.0.1:5000/api/check';

// Cache for recent scans (in-memory, service worker lifecycle)
const scanCache = new Map();
const CACHE_TTL = 600000; // 10 minutes

// Debounce map to prevent rapid re-scans
const debounceMap = new Map();
const DEBOUNCE_TIME = 2000; // 2 seconds

// Load API endpoint from storage on startup
chrome.storage.sync.get(['apiEndpoint'], (result) => {
  if (result.apiEndpoint) {
    API_ENDPOINT = result.apiEndpoint;
  }
});

// Listen for storage changes (when user updates options)
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'sync' && changes.apiEndpoint) {
    API_ENDPOINT = changes.apiEndpoint.newValue;
    console.log('API endpoint updated:', API_ENDPOINT);
  }
});

/**
 * Check if URL should be skipped (internal pages, localhost, etc.)
 */
function shouldSkipUrl(url) {
  if (!url) return true;
  
  const skipPatterns = [
    /^chrome:/,
    /^chrome-extension:/,
    /^about:/,
    /^edge:/,
    /^file:/,
    /^localhost/,
    /^127\.0\.0\.1/,
    /^192\.168\./,
    /^10\./,
  ];
  
  return skipPatterns.some(pattern => pattern.test(url));
}

/**
 * Get cached scan result
 */
function getCachedResult(url) {
  const cached = scanCache.get(url);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.result;
  }
  scanCache.delete(url);
  return null;
}

/**
 * Cache scan result
 */
function cacheResult(url, result) {
  scanCache.set(url, {
    result: result,
    timestamp: Date.now()
  });
  
  // Cleanup old cache entries (keep only last 100)
  if (scanCache.size > 100) {
    const firstKey = scanCache.keys().next().value;
    scanCache.delete(firstKey);
  }
}

/**
 * Scan URL using PhishingHunter API
 */
async function scanUrl(url) {
  try {
    const response = await fetch(`${API_ENDPOINT}?url=${encodeURIComponent(url)}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(10000), // 10 second timeout
    });
    
    if (!response.ok) {
      console.error('API returned error:', response.status);
      return null;
    }
    
    const data = await response.json();
    
    if (data.success && data.result) {
      return data.result;
    }
    
    return null;
  } catch (error) {
    console.error('Scan failed:', error);
    return null;
  }
}

/**
 * Update extension badge with risk indicator
 */
function updateBadge(tabId, result) {
  if (!result) {
    chrome.action.setBadgeText({ tabId: tabId, text: '' });
    return;
  }
  
  const score = result.score;
  const risk = result.risk;
  
  let badgeText = String(score);
  let badgeColor = '#00ff00'; // Green (safe)
  
  if (risk === 'PHISHING' || risk === 'HIGH RISK') {
    badgeColor = '#ff0000'; // Red
  } else if (risk === 'LOW RISK') {
    badgeColor = '#ffaa00'; // Orange
  }
  
  chrome.action.setBadgeText({
    tabId: tabId,
    text: badgeText
  });
  
  chrome.action.setBadgeBackgroundColor({
    tabId: tabId,
    color: badgeColor
  });
}

/**
 * Handle tab navigation
 */
async function handleNavigation(tabId, url) {
  // Skip internal pages
  if (shouldSkipUrl(url)) {
    return;
  }
  
  // Check debounce
  const lastCheck = debounceMap.get(url);
  if (lastCheck && Date.now() - lastCheck < DEBOUNCE_TIME) {
    return;
  }
  debounceMap.set(url, Date.now());
  
  // Check cache
  const cached = getCachedResult(url);
  if (cached) {
    updateBadge(tabId, cached);
    
    // Show warning banner if high risk
    if (cached.risk === 'PHISHING' || cached.risk === 'HIGH RISK') {
      chrome.tabs.sendMessage(tabId, {
        action: 'showWarning',
        result: cached
      });
    }
    return;
  }
  
  // Scan URL
  const result = await scanUrl(url);
  
  if (result) {
    cacheResult(url, result);
    updateBadge(tabId, result);
    
    // Store in chrome.storage for popup access
    chrome.storage.local.set({
      [`scan_${tabId}`]: {
        url: url,
        result: result,
        timestamp: Date.now()
      }
    });
    
    // Show warning banner if high risk
    if (result.risk === 'PHISHING' || result.risk === 'HIGH RISK') {
      chrome.tabs.sendMessage(tabId, {
        action: 'showWarning',
        result: result
      });
    }
  }
}

/**
 * Listen for tab updates (navigation)
 */
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    handleNavigation(tabId, tab.url);
  }
});

/**
 * Listen for tab activation (user switches tabs)
 */
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const tab = await chrome.tabs.get(activeInfo.tabId);
  if (tab.url) {
    // Just update badge from cache, don't re-scan
    const cached = getCachedResult(tab.url);
    if (cached) {
      updateBadge(activeInfo.tabId, cached);
    }
  }
});

/**
 * Create context menu on installation
 */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'phishinghunter-check',
    title: 'Check this link with PhishingHunter',
    contexts: ['link']
  });
});

/**
 * Handle context menu clicks
 */
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'phishinghunter-check' && info.linkUrl) {
    // Scan the link
    const result = await scanUrl(info.linkUrl);
    
    if (result) {
      cacheResult(info.linkUrl, result);
      
      // Store for popup
      chrome.storage.local.set({
        [`contextMenu_${Date.now()}`]: {
          url: info.linkUrl,
          result: result,
          timestamp: Date.now()
        }
      });
      
      // Open popup with result
      chrome.action.openPopup();
    }
  }
});

/**
 * Handle messages from content script or popup
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'getApiEndpoint') {
    sendResponse({ endpoint: API_ENDPOINT });
  } else if (message.action === 'scanUrl') {
    scanUrl(message.url).then(result => {
      sendResponse({ result: result });
    });
    return true; // Keep channel open for async response
  }
});

console.log('PhishingHunter background service worker initialized');
