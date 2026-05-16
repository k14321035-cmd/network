/* ═══════════════════════════════════════════
   IP Geolocation Tracker - JavaScript
   ═══════════════════════════════════════════ */

// Global variables
let map = null;
let currentMarker = null;
let searchHistory = [];
const MAX_HISTORY = 20;

// Initialize map on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeMap();
    loadHistory();
    
    // Handle Enter key on input
    document.getElementById('ipInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') lookupIP();
    });
});

/**
 * Initialize Leaflet map
 */
function initializeMap() {
    map = L.map('map').setView([20, 0], 2);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
    }).addTo(map);
}

/**
 * Lookup IP address
 */
async function lookupIP() {
    const ip = document.getElementById('ipInput').value.trim();
    const errorEl = document.getElementById('errorMessage');
    
    if (!ip) {
        showError('Please enter an IP address');
        return;
    }
    
    clearError();
    showLoadingState();
    
    try {
        const response = await fetch('/api/lookup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ip: ip })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displayResults(data);
            addToHistory(data);
        } else {
            showError(data.error || 'Failed to lookup IP address');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
    
    hideLoadingState();
}

/**
 * Get user's own IP
 */
async function showMyIP() {
    clearError();
    showLoadingState();
    
    try {
        const response = await fetch('/api/my-ip');
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('ipInput').value = data.ip;
            displayResults(data);
            addToHistory(data);
            switchTab('map');
        } else {
            showError(data.error || 'Failed to get your IP');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
    
    hideLoadingState();
}

/**
 * Display results in all tabs
 */
function displayResults(data) {
    // Update info tab
    document.getElementById('displayIP').textContent = data.ip || '-';
    document.getElementById('displayHostname').textContent = data.hostname || '-';
    document.getElementById('displayCountry').textContent = data.country || '-';
    document.getElementById('displayCountryCode').textContent = data.country_code || '-';
    document.getElementById('displayCity').textContent = data.city || '-';
    document.getElementById('displayRegion').textContent = data.region || '-';
    document.getElementById('displayLat').textContent = data.latitude || '-';
    document.getElementById('displayLon').textContent = data.longitude || '-';
    document.getElementById('displayTimezone').textContent = data.timezone || '-';
    document.getElementById('displayISP').textContent = data.isp || data.org || '-';
    document.getElementById('displayType').textContent = data.type || '-';
    
    if (data.timestamp) {
        const date = new Date(data.timestamp);
        document.getElementById('displayTimestamp').textContent = date.toLocaleString();
    }
    
    // Update map
    if (data.latitude && data.longitude) {
        updateMap(data);
    }
}

/**
 * Update map with marker and view
 */
function updateMap(data) {
    const lat = parseFloat(data.latitude);
    const lng = parseFloat(data.longitude);
    
    if (isNaN(lat) || isNaN(lng)) return;
    
    // Remove old marker
    if (currentMarker) {
        map.removeLayer(currentMarker);
    }
    
    // Add new marker
    const popupText = `
        <strong>${data.ip}</strong><br>
        ${data.city}, ${data.region}<br>
        ${data.country}
    `;
    
    currentMarker = L.marker([lat, lng])
        .bindPopup(popupText)
        .addTo(map);
    
    // Center map on marker
    map.setView([lat, lng], 10);
}

/**
 * Execute batch lookup
 */
async function executeBatchLookup() {
    const input = document.getElementById('batchInput').value.trim();
    
    if (!input) {
        showError('Please enter at least one IP address');
        return;
    }
    
    const ips = input.split('\n')
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0);
    
    if (ips.length === 0) {
        showError('No valid IP addresses found');
        return;
    }
    
    if (ips.length > 10) {
        showError('Maximum 10 IP addresses allowed');
        return;
    }
    
    clearError();
    showLoadingState();
    
    try {
        const response = await fetch('/api/batch-lookup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ips: ips })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displayBatchResults(data.results);
        } else {
            showError(data.error || 'Batch lookup failed');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    }
    
    hideLoadingState();
}

/**
 * Display batch results
 */
function displayBatchResults(results) {
    const container = document.getElementById('batchResults');
    container.innerHTML = '';
    
    if (results.length === 0) {
        container.innerHTML = '<p style="color: var(--muted);">No results found</p>';
        return;
    }
    
    results.forEach(result => {
        const item = document.createElement('div');
        item.className = 'batch-result-item';
        item.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>${result.ip}</strong><br>
                    <span style="color: var(--muted); font-size: 0.9rem;">
                        ${result.city}, ${result.region}, ${result.country}
                    </span>
                </div>
                <button onclick="lookupIPFromBatch('${result.ip}')" 
                        style="padding: 0.5rem 1rem; background: var(--primary); color: white; border: none; border-radius: 4px; cursor: pointer;">
                    View Details
                </button>
            </div>
        `;
        container.appendChild(item);
    });
}

/**
 * Lookup IP from batch results
 */
function lookupIPFromBatch(ip) {
    document.getElementById('ipInput').value = ip;
    lookupIP();
    switchTab('info');
}

/**
 * Switch tabs
 */
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabId = tabName === 'map' ? 'mapTab' : 
                  tabName === 'info' ? 'infoTab' : 'historyTab';
    document.getElementById(tabId).classList.add('active');
    
    // Add active class to button
    event.target.classList.add('active');
}

/**
 * Add to search history
 */
function addToHistory(data) {
    const historyItem = {
        ip: data.ip,
        country: data.country,
        city: data.city,
        region: data.region,
        timestamp: new Date().toLocaleString(),
        fullData: data
    };
    
    searchHistory.unshift(historyItem);
    
    if (searchHistory.length > MAX_HISTORY) {
        searchHistory.pop();
    }
    
    saveHistory();
    updateHistoryDisplay();
}

/**
 * Update history display
 */
function updateHistoryDisplay() {
    const container = document.getElementById('historyList');
    container.innerHTML = '';
    
    if (searchHistory.length === 0) {
        container.innerHTML = '<p style="color: var(--muted);">No search history yet</p>';
        return;
    }
    
    searchHistory.forEach((item, index) => {
        const historyEl = document.createElement('div');
        historyEl.className = 'history-item';
        historyEl.onclick = () => loadHistoryItem(item);
        historyEl.innerHTML = `
            <div class="history-info">
                <div class="history-ip">${item.ip}</div>
                <div class="history-location">${item.city}, ${item.region}, ${item.country}</div>
                <div class="history-time">${item.timestamp}</div>
            </div>
            <button onclick="event.stopPropagation(); removeHistoryItem(${index})" 
                    style="background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1.2rem;">×</button>
        `;
        container.appendChild(historyEl);
    });
}

/**
 * Load history item
 */
function loadHistoryItem(item) {
    document.getElementById('ipInput').value = item.ip;
    displayResults(item.fullData);
    switchTab('map');
}

/**
 * Remove history item
 */
function removeHistoryItem(index) {
    searchHistory.splice(index, 1);
    saveHistory();
    updateHistoryDisplay();
}

/**
 * Clear all history
 */
function clearHistory() {
    if (confirm('Are you sure you want to clear all search history?')) {
        searchHistory = [];
        saveHistory();
        updateHistoryDisplay();
    }
}

/**
 * Save history to localStorage
 */
function saveHistory() {
    try {
        localStorage.setItem('ipTrackerHistory', JSON.stringify(searchHistory));
    } catch (e) {
        console.error('Failed to save history:', e);
    }
}

/**
 * Load history from localStorage
 */
function loadHistory() {
    try {
        const saved = localStorage.getItem('ipTrackerHistory');
        if (saved) {
            searchHistory = JSON.parse(saved);
            updateHistoryDisplay();
        }
    } catch (e) {
        console.error('Failed to load history:', e);
    }
}

/**
 * Show/hide batch lookup section
 */
function showBatchLookup() {
    const batchSection = document.getElementById('batchSection');
    batchSection.style.display = batchSection.style.display === 'none' ? 'block' : 'none';
    
    if (batchSection.style.display === 'block') {
        batchSection.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Show help section
 */
function showHelp() {
    const helpSection = document.getElementById('helpSection');
    helpSection.style.display = helpSection.style.display === 'none' ? 'block' : 'none';
    
    if (helpSection.style.display === 'block') {
        helpSection.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Show error message
 */
function showError(message) {
    const errorEl = document.getElementById('errorMessage');
    errorEl.textContent = message;
    errorEl.classList.add('show');
}

/**
 * Clear error message
 */
function clearError() {
    const errorEl = document.getElementById('errorMessage');
    errorEl.classList.remove('show');
    errorEl.textContent = '';
}

/**
 * Show loading state
 */
function showLoadingState() {
    const btn = event ? event.target : document.querySelector('.btn-search');
    if (btn && btn.textContent) {
        btn.disabled = true;
        btn.textContent = 'Loading...';
    }
}

/**
 * Hide loading state
 */
function hideLoadingState() {
    const btns = document.querySelectorAll('.btn-search, .btn-my-ip, .btn-batch');
    btns.forEach(btn => {
        btn.disabled = false;
        if (btn.className.includes('btn-search')) btn.textContent = 'Search';
        else if (btn.className.includes('btn-my-ip')) btn.textContent = 'My IP';
        else if (btn.className.includes('btn-batch')) btn.textContent = 'Lookup Batch';
    });
}
