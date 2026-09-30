/**
 * options.js
 * ----------
 * Options page logic for extension settings
 */

const apiEndpointInput = document.getElementById('apiEndpoint');
const btnSave = document.getElementById('btnSave');
const btnTest = document.getElementById('btnTest');
const statusMessage = document.getElementById('statusMessage');

// Default API endpoint
const DEFAULT_ENDPOINT = 'http://127.0.0.1:5000/api/check';

/**
 * Load saved settings
 */
function loadSettings() {
  chrome.storage.sync.get(['apiEndpoint'], (result) => {
    apiEndpointInput.value = result.apiEndpoint || DEFAULT_ENDPOINT;
  });
}

/**
 * Save settings
 */
function saveSettings() {
  const endpoint = apiEndpointInput.value.trim();
  
  if (!endpoint) {
    showStatus('Please enter an API endpoint', 'error');
    return;
  }
  
  // Validate URL format
  try {
    new URL(endpoint);
  } catch (e) {
    showStatus('Invalid URL format', 'error');
    return;
  }
  
  // Save to storage
  chrome.storage.sync.set({ apiEndpoint: endpoint }, () => {
    showStatus('✅ Settings saved successfully!', 'success');
  });
}

/**
 * Test connection to API
 */
async function testConnection() {
  const endpoint = apiEndpointInput.value.trim();
  
  if (!endpoint) {
    showStatus('Please enter an API endpoint first', 'error');
    return;
  }
  
  showStatus('Testing connection...', 'success');
  btnTest.disabled = true;
  
  try {
    // Test with a simple URL
    const testUrl = 'https://google.com';
    const response = await fetch(`${endpoint}?url=${encodeURIComponent(testUrl)}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(10000),
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        showStatus('✅ Connection successful! API is working.', 'success');
      } else {
        showStatus('⚠️ API responded but returned an error', 'error');
      }
    } else {
      showStatus(`❌ Connection failed: HTTP ${response.status}`, 'error');
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      showStatus('❌ Connection timeout. Is the server running?', 'error');
    } else {
      showStatus(`❌ Connection failed: ${error.message}`, 'error');
    }
  } finally {
    btnTest.disabled = false;
  }
}

/**
 * Show status message
 */
function showStatus(message, type) {
  statusMessage.textContent = message;
  statusMessage.className = `status-message ${type}`;
  statusMessage.style.display = 'block';
  
  // Auto-hide success messages after 3 seconds
  if (type === 'success') {
    setTimeout(() => {
      statusMessage.style.display = 'none';
    }, 3000);
  }
}

// Event listeners
btnSave.addEventListener('click', saveSettings);
btnTest.addEventListener('click', testConnection);

// Load settings on page load
loadSettings();
