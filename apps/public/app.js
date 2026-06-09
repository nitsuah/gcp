document.addEventListener('DOMContentLoaded', () => {
  // UI Elements
  const credentialStatus = document.getElementById('credential-status');
  const driveLoggingToggle = document.getElementById('drive-logging-toggle');
  const accountsList = document.getElementById('accounts-list');
  const btnConnect = document.getElementById('btn-connect');
  const activeAccountSelect = document.getElementById('active-account-select');
  const consoleOutput = document.getElementById('console-output');
  const btnClearConsole = document.getElementById('btn-clear-console');

  // Action Buttons
  const btnListEmails = document.getElementById('btn-list-emails');
  const btnCreateEvent = document.getElementById('btn-create-event');
  const geminiPrompt = document.getElementById('gemini-prompt');
  const btnQueryGemini = document.getElementById('btn-query-gemini');

  // Application State
  let hasCredentials = false;
  let isDemoMode = false;
  let driveLoggingEnabled = true;
  let connectedAccounts = [];
  let selectedAccount = '';

  // Console log helper
  function logToConsole(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = `[${timestamp}] `;
    let colorClass = '';
    
    if (type === 'error') colorClass = 'style="color:#ef4444;"';
    else if (type === 'success') colorClass = 'style="color:#10b981;"';
    else if (type === 'api') colorClass = 'style="color:#a855f7;"';

    consoleOutput.innerHTML += `\n<span ${colorClass}>${prefix}${message}</span>`;
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
  }

  // Load configuration from backend
  async function fetchConfig() {
    try {
      const response = await fetch('/api/config');
      const data = await response.json();

      hasCredentials = data.hasCredentials;
      isDemoMode = data.isDemoMode;
      driveLoggingEnabled = data.driveLoggingEnabled;
      connectedAccounts = data.connectedAccounts;

      // Update Credential Status bar
      if (hasCredentials) {
        credentialStatus.innerHTML = `
          <span class="status-dot success"></span>
          <span class="status-text">Client credentials active</span>
        `;
      } else if (isDemoMode) {
        credentialStatus.innerHTML = `
          <span class="status-dot success" style="background-color: var(--success); box-shadow: 0 0 8px var(--success);"></span>
          <span class="status-text" style="color: var(--success);">Demo Sandbox Active</span>
        `;
      } else {
        credentialStatus.innerHTML = `
          <span class="status-dot warning"></span>
          <span class="status-text">Warning: Credentials missing (client_secrets.json)</span>
        `;
      }

      // Update Drive Logging Switch
      driveLoggingToggle.checked = driveLoggingEnabled;

      // Render accounts
      renderAccounts();
      // Update action controls state
      updateActionControls();
    } catch (error) {
      logToConsole(`Failed to retrieve configuration: ${error.message}`, 'error');
    }
  }

  // Render accounts list in sidebar and update select dropdown
  function renderAccounts() {
    // 1. Sidebar list
    if (connectedAccounts.length === 0) {
      accountsList.innerHTML = `<div class="no-accounts">No accounts connected yet.</div>`;
    } else {
      accountsList.innerHTML = '';
      connectedAccounts.forEach(account => {
        const dateStr = account.expiry_date ? new Date(account.expiry_date).toLocaleString() : 'N/A';
        const card = document.createElement('div');
        card.className = 'account-card';
        card.innerHTML = `
          <div class="account-info">
            <span class="account-email">${account.email}</span>
            <span class="account-meta">Expires: ${dateStr}</span>
          </div>
          <button class="btn-danger-icon btn-disconnect" data-email="${account.email}" title="Disconnect Account">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        `;
        accountsList.appendChild(card);
      });

      // Bind disconnect event listeners
      document.querySelectorAll('.btn-disconnect').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const email = btn.getAttribute('data-email');
          if (confirm(`Disconnect ${email}?`)) {
            await disconnectAccount(email);
          }
        });
      });
    }

    // 2. Select dropdown
    const previousSelection = activeAccountSelect.value;
    activeAccountSelect.innerHTML = '<option value="">-- Select Target Account Context --</option>';
    
    if (connectedAccounts.length > 0) {
      activeAccountSelect.disabled = false;
      connectedAccounts.forEach(account => {
        const option = document.createElement('option');
        option.value = account.email;
        option.textContent = account.email;
        activeAccountSelect.appendChild(option);
      });

      // Restore selection if still available
      if (connectedAccounts.some(a => a.email === previousSelection)) {
        activeAccountSelect.value = previousSelection;
        selectedAccount = previousSelection;
      } else {
        selectedAccount = '';
      }
    } else {
      activeAccountSelect.disabled = true;
      selectedAccount = '';
    }
  }

  // Toggle API action buttons based on selected account
  function updateActionControls() {
    const isEnabled = selectedAccount !== '';
    btnListEmails.disabled = !isEnabled;
    btnCreateEvent.disabled = !isEnabled;
    btnQueryGemini.disabled = !isEnabled;
  }

  // Disconnect / Revoke Account Auth
  async function disconnectAccount(email) {
    try {
      const response = await fetch('/api/accounts/disconnect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const resData = await response.json();
      if (resData.success) {
        logToConsole(`Disconnected account context: ${email}`, 'success');
        if (selectedAccount === email) {
          selectedAccount = '';
        }
        await fetchConfig();
      } else {
        logToConsole(`Failed to disconnect: ${resData.error}`, 'error');
      }
    } catch (e) {
      logToConsole(`Disconnect request failed: ${e.message}`, 'error');
    }
  }

  // Event Listeners
  
  // Toggle Drive Logging State
  driveLoggingToggle.addEventListener('change', async () => {
    try {
      const enabled = driveLoggingToggle.checked;
      const response = await fetch('/api/config/drive-logging', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      const resData = await response.json();
      if (resData.success) {
        driveLoggingEnabled = resData.driveLoggingEnabled;
        logToConsole(`Drive Logging ${driveLoggingEnabled ? 'enabled' : 'disabled'}.`, 'success');
      }
    } catch (e) {
      logToConsole(`Failed to update Drive config: ${e.message}`, 'error');
    }
  });

  // Account dropdown select change
  activeAccountSelect.addEventListener('change', (e) => {
    selectedAccount = e.target.value;
    updateActionControls();
    if (selectedAccount) {
      logToConsole(`Context shifted to account: ${selectedAccount}`, 'info');
    } else {
      logToConsole('Account context cleared.', 'info');
    }
  });

  // Connect Account Button - triggers OAuth Redirect
  btnConnect.addEventListener('click', () => {
    if (!hasCredentials && !isDemoMode) {
      logToConsole('Cannot connect: Local client_secrets.json is missing or incomplete.', 'error');
      alert('Please configure GCP credentials first! Check client_secrets.json directions in the console.');
      return;
    }
    if (isDemoMode) {
      logToConsole('GCP credentials missing. Launching Connection in Local Demo Sandbox...', 'warning');
    } else {
      logToConsole('Initiating OAuth authorization redirection flow...', 'info');
    }
    window.location.href = '/connect-google';
  });

  // Clear output screen
  btnClearConsole.addEventListener('click', () => {
    consoleOutput.innerHTML = 'Console cleared.';
  });

  // Call Gmail API
  btnListEmails.addEventListener('click', async () => {
    if (!selectedAccount) return;
    logToConsole(`Querying Gmail API for account: ${selectedAccount}...`, 'api');
    btnListEmails.disabled = true;

    try {
      const response = await fetch(`/api/gmail/list?email=${encodeURIComponent(selectedAccount)}`);
      const data = await response.json();

      if (response.ok && data.success) {
        logToConsole(`Retrieved ${data.messages.length} recent messages successfully:`, 'success');
        data.messages.forEach(msg => {
          consoleOutput.innerHTML += `\n  - <strong>From:</strong> ${msg.from}\n    <strong>Subject:</strong> ${msg.subject}\n    <strong>Snippet:</strong> ${msg.snippet.substring(0, 75)}...`;
        });
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
      } else {
        logToConsole(`Gmail API Error: ${data.error || 'Unknown error'}`, 'error');
      }
    } catch (e) {
      logToConsole(`Request failed: ${e.message}`, 'error');
    } finally {
      btnListEmails.disabled = false;
    }
  });

  // Call Calendar API
  btnCreateEvent.addEventListener('click', async () => {
    if (!selectedAccount) return;
    const summary = prompt("Enter event title:", "Workspace Hub Automated Event");
    if (summary === null) return; // cancelled
    
    logToConsole(`Creating calendar event on account: ${selectedAccount}...`, 'api');
    btnCreateEvent.disabled = true;

    try {
      const response = await fetch('/api/calendar/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: selectedAccount,
          summary: summary,
          description: 'Created programmatically via multi-tenant OAuth flow wrapper.'
        })
      });
      const data = await response.json();

      if (response.ok && data.success) {
        logToConsole(`Event created successfully! Title: "${data.event.summary}"`, 'success');
        logToConsole(`Link: ${data.event.htmlLink}`);
      } else {
        logToConsole(`Calendar API Error: ${data.error || 'Unknown error'}`, 'error');
      }
    } catch (e) {
      logToConsole(`Request failed: ${e.message}`, 'error');
    } finally {
      btnCreateEvent.disabled = false;
    }
  });

  // Query Gemini API
  btnQueryGemini.addEventListener('click', async () => {
    if (!selectedAccount) return;
    const promptText = geminiPrompt.value.trim();
    if (!promptText) {
      alert("Please enter a prompt for Gemini.");
      return;
    }

    logToConsole(`Sending OAuth query to Gemini model: "${promptText.substring(0, 30)}..."`, 'api');
    btnQueryGemini.disabled = true;

    try {
      const response = await fetch('/api/gemini/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: selectedAccount,
          prompt: promptText
        })
      });
      const data = await response.json();

      if (response.ok && data.success) {
        logToConsole('Gemini response retrieved successfully:', 'success');
        consoleOutput.innerHTML += `\n<span style="color:#d1d5db; white-space:pre-wrap;">${data.response}</span>\n`;
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
      } else {
        logToConsole(`Gemini API Error: ${data.error || 'Unknown error'}`, 'error');
      }
    } catch (e) {
      logToConsole(`Request failed: ${e.message}`, 'error');
    } finally {
      btnQueryGemini.disabled = false;
    }
  });

  // Initial Load
  fetchConfig();
});
