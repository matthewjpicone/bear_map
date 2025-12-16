/**
 * Discord Integration Client
 * Handles Discord channel linking and message fetching
 */

(function() {
  'use strict';

  let discordState = {
    connected: false,
    enabled: false,
    channelId: null,
    channelName: null,
    linkedAt: null,
    botTokenConfigured: false,
  };

  /**
   * Initialize Discord integration UI
   */
  async function initDiscord() {
    await updateDiscordStatus();
    attachEventListeners();
    
    // Auto-refresh messages every 30 seconds if channel is linked
    setInterval(() => {
      if (discordState.enabled && discordState.channelId) {
        refreshMessages();
      }
    }, 30000);
  }

  /**
   * Fetch and update Discord connection status
   */
  async function updateDiscordStatus() {
    try {
      const response = await fetch('/api/discord/status');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      discordState = data;
      
      updateStatusUI();
    } catch (error) {
      console.error('Failed to fetch Discord status:', error);
      showStatusMessage('Failed to check Discord status', 'error');
    }
  }

  /**
   * Update the UI based on current Discord state
   */
  function updateStatusUI() {
    const statusIndicator = document.getElementById('discordStatusIndicator');
    const statusText = document.getElementById('discordStatusText');
    const notConfigured = document.getElementById('discordNotConfigured');
    const controls = document.getElementById('discordControls');
    const linked = document.getElementById('discordLinked');
    const notLinked = document.getElementById('discordNotLinked');
    const messagesSection = document.getElementById('discordMessages');
    
    // Update connection indicator
    if (discordState.connected) {
      statusIndicator.style.color = '#16a34a';
      statusText.textContent = 'Connected';
    } else {
      statusIndicator.style.color = '#dc2626';
      statusText.textContent = 'Disconnected';
    }
    
    // Show appropriate sections
    if (!discordState.botTokenConfigured) {
      notConfigured.style.display = 'block';
      controls.style.display = 'none';
      return;
    }
    
    notConfigured.style.display = 'none';
    controls.style.display = 'block';
    
    // Show link status
    if (discordState.enabled && discordState.channelId) {
      linked.style.display = 'block';
      notLinked.style.display = 'none';
      messagesSection.style.display = 'block';
      
      document.getElementById('linkedChannelName').textContent = 
        discordState.channelName || 'Unknown';
      document.getElementById('linkedChannelId').textContent = 
        discordState.channelId || 'Unknown';
      
      // Load messages
      refreshMessages();
    } else {
      linked.style.display = 'none';
      notLinked.style.display = 'block';
      messagesSection.style.display = 'none';
    }
  }

  /**
   * Link a Discord channel
   */
  async function linkChannel() {
    const channelIdInput = document.getElementById('discordChannelId');
    const channelId = channelIdInput.value.trim();
    
    if (!channelId) {
      showStatusMessage('Please enter a channel ID', 'error');
      return;
    }
    
    if (!/^\d+$/.test(channelId)) {
      showStatusMessage('Channel ID must be a number', 'error');
      return;
    }
    
    try {
      showStatusMessage('Linking channel...', 'info');
      
      const response = await fetch('/api/discord/link', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ channel_id: channelId }),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP ${response.status}`);
      }
      
      const data = await response.json();
      showStatusMessage(`Successfully linked to ${data.channel.name}!`, 'success');
      
      // Clear input
      channelIdInput.value = '';
      
      // Refresh status
      await updateDiscordStatus();
    } catch (error) {
      console.error('Failed to link channel:', error);
      showStatusMessage(`Failed to link channel: ${error.message}`, 'error');
    }
  }

  /**
   * Unlink the Discord channel
   */
  async function unlinkChannel() {
    if (!confirm('Are you sure you want to unlink the Discord channel?')) {
      return;
    }
    
    try {
      showStatusMessage('Unlinking channel...', 'info');
      
      const response = await fetch('/api/discord/unlink', {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      showStatusMessage('Channel unlinked successfully', 'success');
      
      // Refresh status
      await updateDiscordStatus();
    } catch (error) {
      console.error('Failed to unlink channel:', error);
      showStatusMessage(`Failed to unlink channel: ${error.message}`, 'error');
    }
  }

  /**
   * Refresh messages from Discord
   */
  async function refreshMessages() {
    const messageList = document.getElementById('messageList');
    const limitSelect = document.getElementById('messageLimit');
    const limit = limitSelect ? parseInt(limitSelect.value) : 50;
    
    try {
      const response = await fetch(`/api/discord/messages?limit=${limit}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      displayMessages(data.messages);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      messageList.innerHTML = `<p style="color: var(--danger);">Failed to load messages: ${error.message}</p>`;
    }
  }

  /**
   * Display messages in the UI
   */
  function displayMessages(messages) {
    const messageList = document.getElementById('messageList');
    
    if (!messages || messages.length === 0) {
      messageList.innerHTML = '<p style="color: var(--text-dim);">No messages to display</p>';
      return;
    }
    
    const html = messages.map(msg => {
      const timestamp = new Date(msg.timestamp).toLocaleString();
      const avatarUrl = msg.author.avatar_url || '';
      const hasAttachments = msg.attachments && msg.attachments.length > 0;
      
      return `
        <div class="discord-message">
          <div class="message-header">
            ${avatarUrl ? `<img src="${avatarUrl}" alt="${msg.author.name}" class="message-avatar" />` : ''}
            <span class="message-author">${escapeHtml(msg.author.name)}</span>
            <span class="message-timestamp">${timestamp}</span>
          </div>
          <div class="message-content">
            ${escapeHtml(msg.content) || '<em style="color: var(--text-dim);">(no text content)</em>'}
          </div>
          ${hasAttachments ? `
            <div class="message-attachments">
              ${msg.attachments.map(att => `
                <a href="${att.url}" target="_blank" class="attachment-link">
                  📎 ${escapeHtml(att.filename)}
                </a>
              `).join('')}
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
    
    messageList.innerHTML = html;
  }

  /**
   * Show a status message to the user
   */
  function showStatusMessage(message, type = 'info') {
    const statusText = document.getElementById('discordStatusText');
    const originalText = statusText.textContent;
    
    statusText.textContent = message;
    statusText.style.color = type === 'error' ? '#dc2626' : type === 'success' ? '#16a34a' : '#64748b';
    
    // Restore original status after 3 seconds
    setTimeout(() => {
      updateStatusUI();
    }, 3000);
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Attach event listeners
   */
  function attachEventListeners() {
    const linkBtn = document.getElementById('linkDiscordBtn');
    const unlinkBtn = document.getElementById('unlinkDiscordBtn');
    const refreshBtn = document.getElementById('refreshMessagesBtn');
    const channelIdInput = document.getElementById('discordChannelId');
    const limitSelect = document.getElementById('messageLimit');
    
    if (linkBtn) {
      linkBtn.addEventListener('click', linkChannel);
    }
    
    if (unlinkBtn) {
      unlinkBtn.addEventListener('click', unlinkChannel);
    }
    
    if (refreshBtn) {
      refreshBtn.addEventListener('click', refreshMessages);
    }
    
    if (channelIdInput) {
      channelIdInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          linkChannel();
        }
      });
    }
    
    if (limitSelect) {
      limitSelect.addEventListener('change', refreshMessages);
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDiscord);
  } else {
    initDiscord();
  }
})();
