let ws;
const output = document.getElementById('output');
const commandInput = document.getElementById('command-input');
const statusDiv = document.getElementById('status');

function connect() {
  ws = new WebSocket(`ws://${window.location.host}/ws`);

  ws.onopen = function () {
    const statusDiv = document.getElementById('status');
    const statusText = statusDiv.querySelector('.status-text');
    statusDiv.classList.remove('status-connecting', 'status-running', 'status-stopped');
    statusDiv.classList.add('status-connecting');
    statusText.textContent = 'Connected - Checking Status...';

    // Request initial status and worlds
    ws.send(JSON.stringify({ type: 'get_status' }));
    ws.send(JSON.stringify({ type: 'get_worlds' }));

    // Set up periodic status updates with the configurable interval
    refreshTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'get_status' }));
        ws.send(JSON.stringify({ type: 'get_worlds' }));
      }
    }, refreshInterval);
  };

  ws.onclose = function () {
    const statusDiv = document.getElementById('status');
    const statusText = statusDiv.querySelector('.status-text');
    statusDiv.classList.remove('status-connecting', 'status-running', 'status-stopped');
    statusDiv.classList.add('status-connecting');
    statusText.textContent = 'Disconnected - Reconnecting...';
    setTimeout(connect, 1000);
  };

  ws.onmessage = function (event) {
    let data;
    try {
      // First try to parse as regular JSON
      if (typeof event.data === 'string') {
        data = JSON.parse(event.data);
      }
      // If it's a blob, handle it asynchronously
      else if (event.data instanceof Blob) {
        // event.data.text().then(text => {
        //   try {
        //     data = JSON.parse(text);
        //     handleMessage(data);
        //   } catch (e) {
        //     console.error('Failed to parse blob data:', e);
        //     appendOutput(`Error: Failed to parse server message - ${e.message}`, 'error');
        //   }
        // });
        return;
      }
      // Handle the parsed data
      if (data) {
        handleMessage(data);
      }
    } catch (e) {
      console.error('Failed to parse message:', e);
      appendOutput(`Error: Failed to parse server message - ${e.message}`, 'error');
    }
  };
}

function sendCommand() {
  const command = commandInput.value.trim();
  if (command) {
    ws.send(JSON.stringify({
      type: 'command',
      command: command
    }));
    appendOutput(`${command}`, 'command-line');
    commandInput.value = '';
  }
}

function appendOutput(text, className = '') {
  const div = document.createElement('div');
  div.textContent = text;
  if (className) {
    div.className = className;
  }
  output.appendChild(div);
  output.scrollTop = output.scrollHeight;
}

function updateStatus(status) {
  const statusDiv = document.getElementById('status');
  const statusText = statusDiv.querySelector('.status-text');
  const lastUpdated = statusDiv.querySelector('.last-updated');

  // Update last-updated timestamp
  const now = new Date();
  const timeString = now.toLocaleTimeString();
  lastUpdated.textContent = `Last updated: ${timeString}`;

  // Remove all existing status classes
  statusDiv.classList.remove('status-connecting', 'status-running', 'status-stopped');

  if (status.error) {
    statusDiv.classList.add('status-stopped');
    statusText.textContent = `Error - ${status.error}`;
    return;
  }

  switch (status.status.toLowerCase()) {
    case 'running':
      statusDiv.classList.add('status-running');
      break;
    case 'stopped':
    case 'exited':
      statusDiv.classList.add('status-stopped');
      break;
    default:
      statusDiv.classList.add('status-connecting');
  }

  statusText.textContent = `${status.status} (${status.name})`;
}

function updateWorlds(worlds) {
  const worldsList = document.getElementById('worlds-list');
  worldsList.innerHTML = ''; // Clear existing worlds

  if (!worlds || worlds.length === 0) {
    const noWorldsDiv = document.createElement('div');
    noWorldsDiv.className = 'no-worlds';
    noWorldsDiv.textContent = 'No active worlds found';
    worldsList.appendChild(noWorldsDiv);
    return;
  }

  worlds.forEach(world => {
    const worldDiv = document.createElement('div');
    worldDiv.className = 'world-card';

    // Create tags HTML if tags exist
    const tagsHtml = world.tags ?
      `<div class="world-tags">
            ${world.tags.split(',').map(tag => `<span class="tag">${tag.trim()}</span>`).join('')}
           </div>` : '';

    // Create users list HTML if users exist
    const usersHtml = world.users_list && world.users_list.length > 0 ?
      `<div class="user-list">
            <span class="label">Connected Users:</span>
            <div class="users">
              ${world.users_list.map(user => `
                <div class="user-card">
                  <div class="user-header">
                    <span class="user-name">${user.username}</span>
                    <span class="user-role">${user.role}</span>
                  </div>
                  <div class="user-stats">
                    <span class="user-stat" title="Present Status">
                      <i class="status-dot ${user.present ? 'present' : 'away'}"></i>
                      ${user.present ? 'Present' : 'Away'}
                    </span>
                    <span class="user-stat" title="Ping">
                      ${user.ping}ms
                    </span>
                    <span class="user-stat" title="FPS">
                      ${user.fps.toFixed(1)} FPS
                    </span>
                    ${user.silenced ? '<span class="user-stat silenced" title="User is silenced">🔇</span>' : ''}
                  </div>
                </div>
              `).join('')}
            </div>
           </div>` : '';

    worldDiv.innerHTML = `
          <span class="world-name">${world.name}</span>
          <div class="session-id-container">
            <div class="session-id">Session: ${world.sessionId}</div>
            <button
              class="copy-button"
              onclick="copyToClipboard('${world.sessionId}')"
              data-session-id="${world.sessionId}">
              Copy
            </button>
          </div>
          <div class="world-details">
            <div class="world-stat">
              <span class="label">Users:</span>
              <span>${world.users}/${world.maxUsers}</span>
            </div>
            <div class="world-stat">
              <span class="label">Present:</span>
              <span>${world.present}</span>
            </div>
            <div class="world-stat">
              <span class="label">Access:</span>
              <span>${world.accessLevel}</span>
            </div>
            <div class="world-stat">
              <span class="label">Uptime:</span>
              <span>${world.uptime}</span>
            </div>
            <div class="world-stat">
              <span class="label">Hidden:</span>
              <span>${world.hidden ? 'Yes' : 'No'}</span>
            </div>
            <div class="world-stat">
              <span class="label">Mobile:</span>
              <span>${world.mobileFriendly ? 'Yes' : 'No'}</span>
            </div>
            ${world.description ?
        `<div class="world-description">${world.description}</div>` : ''}
            ${tagsHtml}
            ${usersHtml}
          </div>
        `;

    worldsList.appendChild(worldDiv);
  });
}

// Handle Enter key in input
commandInput.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') {
    sendCommand();
  }
});

// Initial connection
connect();

function toggleConsole() {
  const consoleSection = document.querySelector('.console-section');
  const toggleButton = document.querySelector('.toggle-console:nth-of-type(1)');
  const isExpanded = consoleSection.style.display === 'block';

  // Close config panel if open
  const configSection = document.querySelector('.config-section');
  const configButton = document.querySelector('.toggle-console:nth-of-type(2)');
  configSection.style.display = 'none';
  configButton.classList.remove('expanded');

  consoleSection.style.display = isExpanded ? 'none' : 'block';
  toggleButton.classList.toggle('expanded', !isExpanded);

  if (!isExpanded) {
    const input = document.getElementById('command-input');
    input.focus();
  }
}

function toggleConfig() {
  const configSection = document.querySelector('.config-section');
  const toggleButton = document.querySelector('.toggle-console:nth-of-type(2)');
  const isExpanded = configSection.style.display === 'block';

  // Close console panel if open
  const consoleSection = document.querySelector('.console-section');
  const consoleButton = document.querySelector('.toggle-console:nth-of-type(1)');
  consoleSection.style.display = 'none';
  consoleButton.classList.remove('expanded');

  configSection.style.display = isExpanded ? 'none' : 'block';
  toggleButton.classList.toggle('expanded', !isExpanded);

  if (!isExpanded && !currentConfig) {
    loadConfig();
  }
}

function copyToClipboard(sessionId) {
  // Check if the Clipboard API is supported
  if (!navigator.clipboard) {
    // Fallback for browsers that don't support the Clipboard API
    const textArea = document.createElement('textarea');
    textArea.value = sessionId;
    textArea.style.position = 'fixed';  // Avoid scrolling to bottom
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
      document.execCommand('copy');
      const button = document.querySelector(`[data-session-id="${sessionId}"]`);
      button.textContent = 'Copied!';
      button.classList.add('copied');

      setTimeout(() => {
        button.textContent = 'Copy';
        button.classList.remove('copied');
      }, 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }

    document.body.removeChild(textArea);
    return;
  }

  // Use Clipboard API if available
  navigator.clipboard.writeText(sessionId)
    .then(() => {
      const button = document.querySelector(`[data-session-id="${sessionId}"]`);
      button.textContent = 'Copied!';
      button.classList.add('copied');

      setTimeout(() => {
        button.textContent = 'Copy';
        button.classList.remove('copied');
      }, 2000);
    })
    .catch(err => {
      console.error('Failed to copy text: ', err);
    });
}

let currentConfig = null;

async function loadConfig() {
  try {
    const response = await fetch('/config');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const config = await response.json();
    currentConfig = config;

    const editor = document.getElementById('config-editor');
    editor.value = JSON.stringify(config, null, 2);
    updateLineNumbers();
    updateLineHighlight();
    hideError();
  } catch (error) {
    showError(`Failed to load config: ${error.message}`);
  }
}

async function saveConfig() {
  const editor = document.getElementById('config-editor');
  try {
    // Validate JSON
    const config = JSON.parse(editor.value);

    // Send to server
    const response = await fetch('/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to save config');
    }

    currentConfig = config;
    hideError();
    showSuccess();
  } catch (error) {
    showError(`Invalid JSON: ${error.message}`);
  }
}

function formatConfig() {
  const editor = document.getElementById('config-editor');
  try {
    const config = JSON.parse(editor.value);
    editor.value = JSON.stringify(config, null, 2);
    updateLineNumbers();
    hideError();
  } catch (error) {
    showError(`Invalid JSON: ${error.message}`);
  }
}

function showError(message) {
  const errorDiv = document.querySelector('.error-message');
  errorDiv.textContent = message;
  errorDiv.style.display = 'block';
  errorDiv.style.backgroundColor = '#ff6b6b22';
  errorDiv.style.color = '#ff6b6b';
}

function showSuccess() {
  const errorDiv = document.querySelector('.error-message');
  errorDiv.textContent = 'Config saved successfully!';
  errorDiv.style.display = 'block';
  errorDiv.style.backgroundColor = '#4CAF5022';
  errorDiv.style.color = '#4CAF50';
  setTimeout(() => {
    errorDiv.style.display = 'none';
  }, 3000);
}

function hideError() {
  const errorDiv = document.querySelector('.error-message');
  errorDiv.style.display = 'none';
}

let refreshInterval = 30 * 1000; // Default 30 seconds
let refreshTimer = null;

function updateRefreshInterval() {
  console.log('updateRefreshInterval');
  const input = document.getElementById('refresh-interval');
  const newInterval = Math.max(5, Math.min(60, parseInt(input.value))) * 1000;

  if (refreshInterval !== newInterval) {
    refreshInterval = newInterval;

    // Clear existing timer
    if (refreshTimer) {
      clearInterval(refreshTimer);
    }

    // Set up new timer
    refreshTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'get_status' }));
        ws.send(JSON.stringify({ type: 'get_worlds' }));
      }
    }, refreshInterval);
  }
}

// Add event listener for the refresh interval input
document.getElementById('refresh-interval').addEventListener('change', updateRefreshInterval);
document.getElementById('refresh-interval').addEventListener('input', updateRefreshInterval);

// Move the message handling logic to a separate function
function handleMessage(data) {
  switch (data.type) {
    case 'container_output':
      appendOutput(data.output);
      break;
    case 'command_response':
      console.log('command_response', data.output);
      break;
    case 'status_update':
      updateStatus(data.status);
      break;
    case 'worlds_update':
      updateWorlds(data.output);
      break;
    case 'error':
      console.log('error', data.message);
      appendOutput(`Error: ${data.message}`, 'error');
      break;
    default:
      console.warn('Unknown message type:', data.type);
  }
}

function updateLineNumbers() {
  const editor = document.getElementById('config-editor');
  const lineNumbers = document.getElementById('line-numbers');
  const lines = editor.value.split('\n');
  const numbers = lines.map((_, i) => `${(i + 1).toString().padStart(3)}`).join('\n');
  lineNumbers.textContent = numbers;
}

// Add event listeners for the config editor
document.getElementById('config-editor').addEventListener('input', () => {
  updateLineNumbers();
  updateLineHighlight();
});

document.getElementById('config-editor').addEventListener('keyup', updateLineHighlight);
document.getElementById('config-editor').addEventListener('click', updateLineHighlight);
document.getElementById('config-editor').addEventListener('scroll', function () {
  document.getElementById('line-numbers').scrollTop = this.scrollTop;
  const highlight = document.getElementById('config-editor-highlight');
  if (highlight) {
    highlight.style.transform = `translateY(-${this.scrollTop}px)`;
  }
});

// Update the loadConfig function to initialize the highlight
async function loadConfig() {
  try {
    const response = await fetch('/config');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const config = await response.json();
    currentConfig = config;

    const editor = document.getElementById('config-editor');
    editor.value = JSON.stringify(config, null, 2);
    updateLineNumbers();
    updateLineHighlight();
    hideError();
  } catch (error) {
    showError(`Failed to load config: ${error.message}`);
  }
}

function updateLineHighlight() {
  const editor = document.getElementById('config-editor');
  const lineNumbers = document.getElementById('line-numbers');
  const lineHeight = 21; // Fixed line height to match CSS

  // Get cursor position
  const cursorPosition = editor.selectionStart;
  const lines = editor.value.substr(0, cursorPosition).split('\n');
  const currentLineNumber = lines.length;

  // Update line numbers highlight
  const lineNumberElements = editor.value.split('\n')
    .map((_, i) => `<div class="${i + 1 === currentLineNumber ? 'current-line' : ''}">${(i + 1).toString().padStart(3)}</div>`)
    .join('');
  lineNumbers.innerHTML = lineNumberElements;

  // Update editor line highlight
  let highlight = document.getElementById('config-editor-highlight');
  if (!highlight) {
    highlight = document.createElement('div');
    highlight.id = 'config-editor-highlight';
    editor.parentElement.insertBefore(highlight, editor);
  }

  highlight.style.top = `${(currentLineNumber - 1) * lineHeight + 10}px`; // Add padding offset
}