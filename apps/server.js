const express = require('express');
const { google } = require('googleapis');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Secure Local Token Storage Configuration
const TOKENS_FILE = path.join(__dirname, 'data', 'tokens.json');
// Hash the encryption key to ensure it is exactly 32 bytes
const ENCRYPTION_KEY = crypto
  .createHash('sha256')
  .update(process.env.ENCRYPTION_KEY || 'centralized-gcp-workspace-integration-key-g14f')
  .digest();
const IV_LENGTH = 16;

// Application State Config
let configState = {
  driveLoggingEnabled: true
};

/**
 * Encrypt data using AES-256-CBC
 */
function encrypt(text) {
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv('aes-256-cbc', ENCRYPTION_KEY, iv);
  let encrypted = cipher.update(text);
  encrypted = Buffer.concat([encrypted, cipher.final()]);
  return iv.toString('hex') + ':' + encrypted.toString('hex');
}

/**
 * Decrypt data using AES-256-CBC
 */
function decrypt(text) {
  try {
    const textParts = text.split(':');
    const iv = Buffer.from(textParts.shift(), 'hex');
    const encryptedText = Buffer.from(textParts.join(':'), 'hex');
    const decipher = crypto.createDecipheriv('aes-256-cbc', ENCRYPTION_KEY, iv);
    let decrypted = decipher.update(encryptedText);
    decrypted = Buffer.concat([decrypted, decipher.final()]);
    return decrypted.toString();
  } catch (e) {
    console.error('[ERROR] Decryption of tokens failed:', e.message);
    return null;
  }
}

/**
 * Load tokens from encrypted file
 */
function loadTokens() {
  if (!fs.existsSync(TOKENS_FILE)) {
    return {};
  }
  try {
    const encryptedData = fs.readFileSync(TOKENS_FILE, 'utf8');
    if (!encryptedData.trim()) return {};
    const decrypted = decrypt(encryptedData);
    return decrypted ? JSON.parse(decrypted) : {};
  } catch (e) {
    console.error('[WARNING] Failed to parse tokens file:', e.message);
    return {};
  }
}

/**
 * Save tokens to encrypted file
 */
function saveTokens(tokens) {
  try {
    const dir = path.dirname(TOKENS_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const encrypted = encrypt(JSON.stringify(tokens));
    fs.writeFileSync(TOKENS_FILE, encrypted, 'utf8');
  } catch (e) {
    console.error('[ERROR] Failed to write tokens file:', e.message);
  }
}

/**
 * Find and load client secrets
 */
function getOAuthCredentials() {
  const paths = [
    path.join(__dirname, 'client_secrets.json'),
    path.join(__dirname, '..', 'gcp', 'client_secrets.json'),
    path.join(__dirname, '..', '..', 'code', 'gcp', 'client_secrets.json'),
    path.join(__dirname, '..', 'gcp', 'client_secrets.json') // backup
  ];

  for (const p of paths) {
    if (fs.existsSync(p)) {
      try {
        const data = JSON.parse(fs.readFileSync(p, 'utf8'));
        if (data.web) {
          return data.web;
        }
      } catch (e) {
        console.error(`[ERROR] Parsing secrets file at ${p}:`, e.message);
      }
    }
  }

  // Fallback to environment variables
  if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
    return {
      client_id: process.env.GOOGLE_CLIENT_ID,
      client_secret: process.env.GOOGLE_CLIENT_SECRET,
      redirect_uris: [process.env.GOOGLE_REDIRECT_URI || 'http://localhost:3000/oauth2callback']
    };
  }

  return null;
}

/**
 * Checks if the server is running in Demo Mode (credentials missing or default placeholder)
 */
function isDemoModeActive() {
  const creds = getOAuthCredentials();
  if (!creds) return true;
  if (creds.client_id && creds.client_id.includes('YOUR_CLIENT_ID')) return true;
  return false;
}


/**
 * Create separate OAuth client for a specific account email
 */
function getAuthenticatedClient(email) {
  const creds = getOAuthCredentials();
  if (!creds) {
    throw new Error('OAuth 2.0 Client credentials not configured. Please run setup first.');
  }

  const tokens = loadTokens();
  const accountTokens = tokens[email];
  if (!accountTokens) {
    throw new Error(`No authorization tokens found for account: ${email}`);
  }

  const redirectUri = creds.redirect_uris[0];
  const oauth2Client = new google.auth.OAuth2(
    creds.client_id,
    creds.client_secret,
    redirectUri
  );

  oauth2Client.setCredentials(accountTokens);

  // Auto token-refresh saving hook
  oauth2Client.on('tokens', (newTokens) => {
    const currentTokens = loadTokens();
    if (currentTokens[email]) {
      currentTokens[email] = {
        ...currentTokens[email],
        ...newTokens
      };
      saveTokens(currentTokens);
      console.log(`[INFO] Access token refreshed and saved automatically for ${email}`);
    }
  });

  return oauth2Client;
}

/**
 * Google Drive logging utility
 */
async function logToGoogleDrive(email, message) {
  try {
    const authClient = getAuthenticatedClient(email);
    const drive = google.drive({ version: 'v3', auth: authClient });

    const logFileName = 'Workspace_Automation_Logs.txt';
    const listRes = await drive.files.list({
      q: `name = '${logFileName}' and mimeType = 'text/plain' and trashed = false`,
      fields: 'files(id, name)',
      spaces: 'drive'
    });

    const files = listRes.data.files;
    let fileId;
    let existingContent = '';

    const logEntry = `[${new Date().toISOString()}] ${message}\n`;

    if (files && files.length > 0) {
      fileId = files[0].id;
      // Get file content
      const contentRes = await drive.files.get({
        fileId: fileId,
        alt: 'media'
      });
      existingContent = typeof contentRes.data === 'string' ? contentRes.data : JSON.stringify(contentRes.data) || '';
    }

    const newContent = existingContent + logEntry;

    if (fileId) {
      await drive.files.update({
        fileId: fileId,
        media: {
          mimeType: 'text/plain',
          body: newContent
        }
      });
      console.log(`[DRIVE LOG] Appended entry to file ID: ${fileId} for ${email}`);
    } else {
      const createRes = await drive.files.create({
        requestBody: {
          name: logFileName,
          mimeType: 'text/plain'
        },
        media: {
          mimeType: 'text/plain',
          body: newContent
        }
      });
      fileId = createRes.data.id;
      console.log(`[DRIVE LOG] Created log file ID: ${fileId} for ${email}`);
    }
    return fileId;
  } catch (error) {
    console.error(`[ERROR] Drive Logging failed for ${email}:`, error.message);
    throw error;
  }
}

// ==========================================
//                 API Routes
// ==========================================

// Get configuration state and list of accounts
app.get('/api/config', (req, res) => {
  const creds = getOAuthCredentials();
  const tokens = loadTokens();
  const accountsList = Object.keys(tokens).map(email => ({
    email,
    expiry_date: tokens[email].expiry_date,
    hasRefreshToken: !!tokens[email].refresh_token
  }));

  const isDemo = isDemoModeActive();

  res.json({
    hasCredentials: !isDemo && !!creds,
    isDemoMode: isDemo,
    clientId: (creds && !isDemo) ? creds.client_id.substring(0, 15) + '...' : 'DEMO_CLIENT_ID',
    driveLoggingEnabled: configState.driveLoggingEnabled,
    connectedAccounts: accountsList
  });
});

// Toggle Google Drive logging option
app.post('/api/config/drive-logging', (req, res) => {
  const { enabled } = req.body;
  configState.driveLoggingEnabled = !!enabled;
  res.json({ success: true, driveLoggingEnabled: configState.driveLoggingEnabled });
});

// OAuth connection initialization route
app.get('/connect-google', (req, res) => {
  const isDemo = isDemoModeActive();
  if (isDemo) {
    // In demo mode, bypass Google and redirect to callback with a demo code
    console.log('[DEMO MODE] Redirecting directly to mock auth callback...');
    return res.redirect('/oauth2callback?code=mock_demo_auth_code');
  }

  const creds = getOAuthCredentials();
  if (!creds) {
    return res.status(500).send('OAuth credentials not found. Run the setup script first.');
  }

  const oauth2Client = new google.auth.OAuth2(
    creds.client_id,
    creds.client_secret,
    creds.redirect_uris[0]
  );

  const scopes = [
    'openid',
    'email',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.file'
  ];

  const url = oauth2Client.generateAuthUrl({
    access_type: 'offline', // crucial for receiving the refresh token
    prompt: 'consent',     // forces consent to guarantee refresh token is returned
    scope: scopes
  });

  res.redirect(url);
});

// OAuth 2.0 Redirect Callback URL
app.get('/oauth2callback', async (req, res) => {
  const { code } = req.query;
  const isDemo = isDemoModeActive() || code === 'mock_demo_auth_code';

  if (isDemo) {
    const randomId = Math.floor(Math.random() * 900) + 100;
    const mockEmail = `demo-workspace-${randomId}@gmail.com`;
    
    // Store mock tokens
    const currentTokens = loadTokens();
    currentTokens[mockEmail] = {
      access_token: 'mock_access_token_' + Math.random().toString(36).substring(7),
      refresh_token: 'mock_refresh_token_' + Math.random().toString(36).substring(7),
      expiry_date: Date.now() + 3600000
    };
    saveTokens(currentTokens);

    console.log(`[DEMO MODE] Linkage successful for mock account: ${mockEmail}`);

    return res.send(`
      <html>
        <head>
          <title>Authentication Successful (Demo Mode)</title>
          <style>
            body { font-family: 'Outfit', sans-serif; background: #0a0e17; color: #e2e8f0; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .card { background: rgba(25, 34, 56, 0.45); padding: 40px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; backdrop-filter: blur(14px); }
            h2 { color: #66fcf1; }
            button { background: #66fcf1; color: #0a0e17; border: none; padding: 12px 24px; font-weight: bold; border-radius: 8px; cursor: pointer; margin-top: 20px; transition: transform 0.2s; font-family: 'Inter', sans-serif; }
            button:hover { transform: scale(1.05); }
          </style>
        </head>
        <body>
          <div class="card">
            <h2>Connection Successful! (Demo Mode)</h2>
            <p>Mock Account <strong>${mockEmail}</strong> has been linked.</p>
            <button onclick="window.location.href='/'">Go back to Dashboard</button>
          </div>
        </body>
      </html>
    `);
  }

  const creds = getOAuthCredentials();
  if (!creds) {
    return res.status(500).send('Client credentials not configured.');
  }


  try {
    const oauth2Client = new google.auth.OAuth2(
      creds.client_id,
      creds.client_secret,
      creds.redirect_uris[0]
    );

    // Exchange auth code for tokens
    const { tokens } = await oauth2Client.getToken(code);
    oauth2Client.setCredentials(tokens);

    // Call userinfo endpoint to identify which account just logged in
    const oauth2 = google.oauth2({ version: 'v2', auth: oauth2Client });
    const userInfo = await oauth2.userinfo.get();
    const email = userInfo.data.email;

    if (!email) {
      throw new Error('Failed to retrieve user email.');
    }

    // Save tokens in secure store
    const currentTokens = loadTokens();
    
    // Ensure we keep the refresh token if Google didn't return one this time
    const existingTokens = currentTokens[email] || {};
    const finalTokens = {
      ...existingTokens,
      ...tokens
    };

    currentTokens[email] = finalTokens;
    saveTokens(currentTokens);

    console.log(`[AUTH] Connected Google account successfully: ${email}`);

    // If logging is enabled, record initialization event to Drive
    if (configState.driveLoggingEnabled) {
      await logToGoogleDrive(email, `Initialized multi-account connection for ${email}`);
    }

    // Redirect user back to dashboard homepage
    res.send(`
      <html>
        <head>
          <title>Authentication Successful</title>
          <style>
            body { font-family: 'Outfit', sans-serif; background: #0b0c10; color: #c5c6c7; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .card { background: rgba(255, 255, 255, 0.05); padding: 40px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; }
            h2 { color: #66fcf1; }
            button { background: #66fcf1; color: #0b0c10; border: none; padding: 12px 24px; font-weight: bold; border-radius: 8px; cursor: pointer; margin-top: 20px; transition: transform 0.2s; }
            button:hover { transform: scale(1.05); }
          </style>
        </head>
        <body>
          <div class="card">
            <h2>Connection Successful!</h2>
            <p>Account <strong>${email}</strong> has been linked.</p>
            <button onclick="window.location.href='/'">Go back to Dashboard</button>
          </div>
        </body>
      </html>
    `);
  } catch (error) {
    console.error('[ERROR] OAuth Callback failed:', error);
    res.status(500).send(`Authentication failed: ${error.message}`);
  }
});

// Disconnect Google Account
app.post('/api/accounts/disconnect', (req, res) => {
  const { email } = req.body;
  const tokens = loadTokens();
  if (tokens[email]) {
    delete tokens[email];
    saveTokens(tokens);
    console.log(`[AUTH] Disconnected Google account: ${email}`);
    return res.json({ success: true });
  }
  res.status(404).json({ error: 'Account not found' });
});

// Fetch Recent Emails (Dynamic Routing Example)
app.get('/api/gmail/list', async (req, res) => {
  const { email } = req.query;
  try {
    if (email && email.startsWith('demo-')) {
      await new Promise(r => setTimeout(r, 600)); // Simulate API latency
      const mockMessages = [
        { id: 'msg-001', from: 'Google Cloud Billing <billing-alerts@google.com>', subject: 'Budget Alert: 50% Threshold Reached', snippet: 'Project ws-auth-5712 has exceeded 50% of the allocated budget ($25.00 of $50.00)...' },
        { id: 'msg-002', from: 'Overseer Agent <agent@overseer.internal>', subject: 'Job execution report: Succeeded', snippet: 'Auto-apply automation finished at 22:38 UTC. Applied 14 rule triggers successfully...' },
        { id: 'msg-003', from: 'Centralized OAuth Hub <no-reply@gcp-oauth.central>', subject: 'New Connection Verified', snippet: 'Security notification: A new Workspace API client context was authorized for this profile...' }
      ];
      console.log(`[DEMO MODE] Intercepted Gmail list query for: ${email}`);
      return res.json({ success: true, messages: mockMessages });
    }

    const authClient = getAuthenticatedClient(email);
    const gmail = google.gmail({ version: 'v1', auth: authClient });

    // Call Gmail API
    const listRes = await gmail.users.messages.list({
      userId: 'me',
      maxResults: 5
    });

    const messages = listRes.data.messages || [];
    const detailedMessages = [];

    for (const msg of messages) {
      const detail = await gmail.users.messages.get({
        userId: 'me',
        id: msg.id
      });
      const headers = detail.data.payload.headers;
      const subject = (headers.find(h => h.name.toLowerCase() === 'subject') || {}).value || '(No Subject)';
      const from = (headers.find(h => h.name.toLowerCase() === 'from') || {}).value || 'Unknown';
      detailedMessages.push({
        id: msg.id,
        snippet: detail.data.snippet,
        subject,
        from
      });
    }

    if (configState.driveLoggingEnabled) {
      await logToGoogleDrive(email, `Fetched recent emails list.`);
    }

    res.json({ success: true, messages: detailedMessages });
  } catch (error) {
    console.error(`[API] Gmail access error for ${email}:`, error);
    res.status(500).json({ error: error.message });
  }
});

// Create Calendar Event (Dynamic Routing Example)
app.post('/api/calendar/create', async (req, res) => {
  const { email, summary, description, startDateTime, endDateTime } = req.body;
  try {
    if (email && email.startsWith('demo-')) {
      await new Promise(r => setTimeout(r, 600));
      console.log(`[DEMO MODE] Intercepted Calendar event insert for: ${email}`);
      return res.json({
        success: true,
        event: {
          summary: summary || 'Mock Demo Workspace Event',
          description: description || 'Created in local demo sandbox.',
          htmlLink: 'https://calendar.google.com/calendar/r/eventedit?text=' + encodeURIComponent(summary || 'Demo Event'),
          status: 'confirmed'
        }
      });
    }

    const authClient = getAuthenticatedClient(email);
    const calendar = google.calendar({ version: 'v3', auth: authClient });

    const event = {
      summary,
      description,
      start: {
        dateTime: startDateTime || new Date().toISOString(),
        timeZone: 'UTC'
      },
      end: {
        dateTime: endDateTime || new Date(Date.now() + 3600000).toISOString(),
        timeZone: 'UTC'
      }
    };

    const insertRes = await calendar.events.insert({
      calendarId: 'primary',
      requestBody: event
    });

    if (configState.driveLoggingEnabled) {
      await logToGoogleDrive(email, `Created calendar event: "${summary}" (${insertRes.data.htmlLink})`);
    }

    res.json({ success: true, event: insertRes.data });
  } catch (error) {
    console.error(`[API] Calendar create error for ${email}:`, error);
    res.status(500).json({ error: error.message });
  }
});

// Test Gemini Prompt via User's OAuth Credentials
app.post('/api/gemini/query', async (req, res) => {
  const { email, prompt } = req.body;
  try {
    if (email && email.startsWith('demo-')) {
      await new Promise(r => setTimeout(r, 800));
      console.log(`[DEMO MODE] Intercepted Gemini API query for: ${email}`);
      let simulatedResponse = `**Simulated Gemini 1.5 Flash Model response** (Demo Sandbox Mode):\n\nYour prompt: *"${prompt}"*\n\nBecause this workspace is running in Local Demo Mode, this response is simulated locally. Once a valid \`client_secrets.json\` is loaded and a live Google Workspace account is authorized, the application will invoke the Generative Language API using your account's secure OAuth access token.`;
      
      if (prompt.toLowerCase().includes('moon')) {
        simulatedResponse = `**Simulated Gemini 1.5 Flash**:\n\nThe average distance from the Earth to the Moon is approximately **384,400 kilometers** (about **238,855 miles**). Since the Moon travels in an elliptical orbit, the actual distance varies from 363,300 km at perigee (closest approach) to 405,500 km at apogee (farthest distance).`;
      }
      
      return res.json({ success: true, response: simulatedResponse });
    }

    const authClient = getAuthenticatedClient(email);
    const credentials = await authClient.getAccessToken();
    const token = credentials.token;

    if (!token) {
      throw new Error('Could not acquire active access token for Gemini API.');
    }

    // Call the Google Generative Language API using the user's OAuth access token
    // Standard model endpoints: gemini-1.5-flash
    const url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent';
    
    // We import dynamically or use Node's native fetch (which exists in v22.x)
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        contents: [{
          parts: [{ text: prompt || "Say Hello in a premium developer style!" }]
        }]
      })
    });

    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error?.message || 'Error communicating with Generative Language API');
    }

    const outputText = data.candidates?.[0]?.content?.parts?.[0]?.text || 'No response text received.';

    if (configState.driveLoggingEnabled) {
      await logToGoogleDrive(email, `Executed Gemini prompt: "${prompt.substring(0, 30)}..."`);
    }

    res.json({ success: true, response: outputText });
  } catch (error) {
    console.error(`[API] Gemini API error for ${email}:`, error);
    res.status(500).json({ error: error.message });
  }
});

// Manual Log to Google Drive
app.post('/api/drive/log', async (req, res) => {
  const { email, logMessage } = req.body;
  try {
    if (email && email.startsWith('demo-')) {
      console.log(`[DEMO MODE] Intercepted Drive logging for: ${email}`);
      console.log(`[DRIVE MOCK LOG] Content: "${logMessage}"`);
      return res.json({ success: true, fileId: 'mock_drive_file_id_571288' });
    }

    const fileId = await logToGoogleDrive(email, logMessage);
    res.json({ success: true, fileId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Start Server
app.listen(PORT, () => {
  console.log(`[SERVER] Multi-Account Workspace Engine listening on http://localhost:${PORT}`);
  const creds = getOAuthCredentials();
  if (!creds) {
    console.log('[WARNING] client_secrets.json not found in search paths.');
    console.log('[WARNING] Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET or place client_secrets.json in code/gcp/');
  } else {
    console.log('[INFO] Loaded OAuth Client credentials successfully.');
  }
});
