# PhishingHunter Elite - Browser Extension

Chrome/Firefox browser extension for real-time phishing detection.

## Features

✅ **Real-time Protection** - Automatically scans pages as you browse  
✅ **Visual Badge** - Risk score displayed on extension icon  
✅ **Warning Banners** - High-risk sites show dismissible warnings  
✅ **Context Menu** - Right-click any link to check it  
✅ **Cyber-HUD Interface** - Matching the main dashboard aesthetic  
✅ **Configurable** - Point to local or remote API server  
✅ **Privacy-First** - No data sent to external services

## Installation

### Chrome/Edge (Chromium-based)

1. Start the PhishingHunter API server:
   ```bash
   cd PhishingHunter_v2
   python app.py
   ```

2. Open Chrome and navigate to `chrome://extensions/`

3. Enable "Developer mode" (toggle in top-right corner)

4. Click "Load unpacked"

5. Select the `extension` folder from your PhishingHunter directory

6. The extension icon should appear in your toolbar!

### Firefox

1. Start the PhishingHunter API server:
   ```bash
   cd PhishingHunter_v2
   python app.py
   ```

2. Open Firefox and navigate to `about:debugging#/runtime/this-firefox`

3. Click "Load Temporary Add-on..."

4. Navigate to the `extension` folder and select `manifest.json`

5. The extension will be loaded temporarily (until you close Firefox)

**Note:** For permanent Firefox installation, you need to sign the extension through Mozilla AMO (Add-ons Marketplace).

## Usage

### Automatic Scanning

Once installed, the extension automatically:
- Scans each page you visit
- Shows risk score as a badge on the extension icon
- Displays warning banner for high-risk sites
- Caches results for 10 minutes

### Manual Checking

**Option 1: Extension Popup**
1. Click the PhishingHunter icon in your toolbar
2. See detailed risk analysis for the current page
3. View top threat signals
4. Click "View Full Report" to open the main dashboard

**Option 2: Context Menu**
1. Right-click any link on a page
2. Select "Check this link with PhishingHunter"
3. The link will be scanned immediately
4. Click the extension icon to see results

### Configuration

1. Right-click the extension icon → "Options"
   
   OR
   
   Click the ⚙️ settings icon in the popup

2. Configure the API endpoint:
   - **Local (default):** `http://127.0.0.1:5000/api/check`
   - **Remote:** `https://your-server.com/api/check`

3. Click "Test Connection" to verify

4. Click "Save Settings"

## Architecture

```
Browser Page
    ↓
Content Script (content.js)
    ↓ (warning banners)
    ↓
Background Service Worker (background.js)
    ↓ (navigation tracking, API calls)
    ↓
PhishingHunter API (http://127.0.0.1:5000/api/check)
    ↓
Full Detection Pipeline
    ├─ Blocklists
    ├─ Google Safe Browsing
    ├─ VirusTotal
    ├─ ML Classifier
    ├─ Visual Similarity
    └─ 25+ Signals
```

## File Structure

```
extension/
├── manifest.json          # Extension config (Manifest V3)
├── background.js          # Service worker (tab monitoring, API calls)
├── popup.html            # Extension popup UI
├── popup.css             # Cyber-HUD styling
├── popup.js              # Popup logic
├── content.js            # Content script (warning banners)
├── content.css           # Warning banner styles
├── options.html          # Settings page
├── options.js            # Settings logic
└── icons/                # Extension icons (to be added)
    ├── icon16.png
    ├── icon32.png
    ├── icon48.png
    └── icon128.png
```

## Privacy & Security

### What Data is Collected?
- **URLs you visit** - Sent to YOUR PhishingHunter server for analysis
- **Scan results** - Cached locally in browser storage (10-minute TTL)
- **Settings** - API endpoint stored in sync storage

### What Data is NOT Collected?
- ❌ No browsing history sent to external services
- ❌ No personal information
- ❌ No tracking or analytics
- ❌ No third-party data sharing

### Security Notes:
- Extension uses Manifest V3 (latest security standard)
- Minimal permissions requested (activeTab, storage, contextMenus)
- All communication via HTTPS recommended for production
- Content Security Policy enforced
- No eval() or remote code execution

## Permissions Explained

| Permission | Why Needed |
|------------|------------|
| `activeTab` | Read current page URL for scanning |
| `storage` | Cache scan results and save settings |
| `contextMenus` | Add "Check this link" context menu |
| `host_permissions: <all_urls>` | Inject warning banners on high-risk sites |

## Troubleshooting

### Extension shows "Unable to connect to API"
- Make sure the PhishingHunter server is running: `python app.py`
- Verify the server is accessible at `http://127.0.0.1:5000`
- Check the API endpoint in extension settings (click ⚙️ icon)
- Click "Test Connection" in settings

### Badge not showing risk scores
- The extension only scans HTTP/HTTPS pages (not chrome://, about:, file://)
- Check browser console for errors (F12 → Console tab)
- Reload the extension: `chrome://extensions/` → Click reload icon

### Warning banner not appearing
- Banners only show for "HIGH RISK" or "PHISHING" scores (≥55)
- Check if content script is blocked by page's CSP
- Try disabling other extensions that might conflict

### Popup shows "No active tab found"
- Make sure you're not on an internal browser page (chrome://, about:, etc.)
- Try refreshing the page and clicking the extension icon again

## Development

### Local Development

1. Make changes to extension files
2. Go to `chrome://extensions/`
3. Click the reload icon for PhishingHunter extension
4. Test your changes

### Debugging

**Background Service Worker:**
```
chrome://extensions/ → PhishingHunter → "Inspect views: service worker"
```

**Content Script:**
```
Open any page → F12 → Console tab → Check for "PhishingHunter content script loaded"
```

**Popup:**
```
Click extension icon → Right-click popup → "Inspect"
```

## Building for Production

### Chrome Web Store

1. Create icon assets (16x16, 32x32, 48x48, 128x128)
2. Update `manifest.json` version
3. Zip the extension folder
4. Upload to Chrome Web Store Developer Dashboard
5. Fill in store listing details
6. Submit for review

### Firefox Add-ons (AMO)

1. Create icon assets
2. Update `manifest.json` version
3. Zip the extension folder
4. Sign at [addons.mozilla.org](https://addons.mozilla.org)
5. Upload to AMO
6. Submit for review

## Roadmap

### Planned Features:
- [ ] Automatic updates when API version changes
- [ ] Offline mode (cached results only)
- [ ] Whitelist/blacklist management
- [ ] Statistics dashboard
- [ ] Export scan history
- [ ] Dark/light theme toggle
- [ ] Keyboard shortcuts
- [ ] Multi-language support

## License

Same license as PhishingHunter main project.

## Support

For issues or questions:
1. Check the main PhishingHunter documentation
2. Ensure the API server is running correctly
3. Check browser console for errors
4. Try reinstalling the extension

---

**Version:** 2.0.0  
**Compatibility:** Chrome 88+, Edge 88+, Firefox 109+  
**Manifest:** V3  
**Last Updated:** Phase 6 Complete
