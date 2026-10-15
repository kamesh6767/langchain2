const DocuMindApp = {
  windows: {},
  activeWindowId: 'global',
  isGenerating: false,

  init() {
    // Initialize default Global Vault window
    this.windows['global'] = {
      id: 'global',
      title: 'Global Vault',
      filename: null,
      fileType: 'vault',
      videoId: null,
      chunks: 0,
      history: [],
      messagesHtml: '',
      playerVisible: false
    };

    this.bindEvents();

    // Register existing indexed document windows if stats are already available
    if (window.DocuMindDocs && DocuMindDocs.currentStats?.documents) {
      DocuMindDocs.currentStats.documents.forEach(doc => {
        this.openWindow(doc, false);
      });
    }

    this.renderTabs();
    this.updateBanner();
  },

  bindEvents() {
    const sendBtn = document.getElementById('send-btn');
    const textarea = document.getElementById('chat-textarea');
    const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
    const sidebar = document.getElementById('app-sidebar');
    const clearWindowBtn = document.getElementById('clear-window-chat-btn');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    const addVaultBtn = document.getElementById('add-vault-tab-btn');
    const togglePlayerBtn = document.getElementById('toggle-player-btn');
    const exportChatBtn = document.getElementById('export-chat-btn');

    sendBtn?.addEventListener('click', () => this.sendMessage());

    exportChatBtn?.addEventListener('click', () => this.exportChat());

    clearWindowBtn?.addEventListener('click', () => {
      if (window.DocuMindConfirm) {
        DocuMindConfirm.show({
          title: 'Clear Chat',
          message: 'Clear the conversation in this window? Your indexed documents and embeddings will remain untouched.',
          confirmText: 'Clear Chat',
          icon: '💬',
          isDanger: false,
          onConfirm: () => this.clearWindowChat()
        });
      } else {
        if (confirm('Clear the conversation for this window?')) {
          this.clearWindowChat();
        }
      }
    });

    clearChatBtn?.addEventListener('click', () => {
      if (window.DocuMindConfirm) {
        DocuMindConfirm.show({
          title: 'Clear Chat',
          message: 'Clear the conversation in this window? Your indexed documents and embeddings will remain untouched.',
          confirmText: 'Clear Chat',
          icon: '💬',
          isDanger: false,
          onConfirm: () => this.clearWindowChat()
        });
      } else {
        if (confirm('Clear the conversation for this window?')) {
          this.clearWindowChat();
        }
      }
    });

    addVaultBtn?.addEventListener('click', () => {
      this.switchWindow('global');
    });

    togglePlayerBtn?.addEventListener('click', () => {
      this.togglePlayer();
    });

    sidebarToggleBtn?.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        sidebar?.classList.toggle('open');
      } else {
        const isCollapsed = sidebar?.classList.toggle('collapsed');
        sidebarToggleBtn.classList.toggle('collapsed', isCollapsed);
        sidebarToggleBtn.title = isCollapsed ? 'Expand Knowledge Vault (Ctrl+B)' : 'Collapse Knowledge Vault (Ctrl+B)';
      }
    });

    // Keyboard shortcut Ctrl+B to toggle sidebar
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        sidebarToggleBtn?.click();
      }
    });

    textarea?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    textarea?.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    });
  },

  /**
   * Generates a stable window ID from filename
   */
  getWindowId(filename) {
    if (!filename) return 'global';
    return 'win_' + encodeURIComponent(filename).replace(/[^a-zA-Z0-9_-]/g, '_');
  },

  /**
   * Opens or focuses a separate new window for a video or file
   */
  openWindow(docInfo, switchNow = true) {
    if (!docInfo || !docInfo.filename) return;

    const winId = this.getWindowId(docInfo.filename);
    const isYouTube = docInfo.file_type === 'youtube' || docInfo.filename.startsWith('YouTube:');
    let videoId = docInfo.video_id;
    if (!videoId && isYouTube) {
      videoId = docInfo.filename.replace('YouTube:', '').trim();
    }

    let displayTitle = docInfo.filename;
    if (isYouTube) {
      displayTitle = `YouTube (${videoId})`;
    }

    if (!this.windows[winId]) {
      this.windows[winId] = {
        id: winId,
        title: displayTitle,
        filename: docInfo.filename,
        fileType: isYouTube ? 'youtube' : (docInfo.file_type || 'file'),
        videoId: videoId || null,
        chunks: docInfo.chunks || 0,
        history: [],
        messagesHtml: '',
        playerVisible: false // default player closed to maximize chat workspace
      };
    } else {
      // Update chunks or videoId if changed
      this.windows[winId].chunks = docInfo.chunks || this.windows[winId].chunks;
      if (videoId) this.windows[winId].videoId = videoId;
    }

    this.renderTabs();

    if (switchNow) {
      this.switchWindow(winId);
    }
  },

  /**
   * Switches the active workspace window
   */
  switchWindow(windowId) {
    if (this.isGenerating) {
      if (window.DocuMindSettings?.showToast) {
        DocuMindSettings.showToast('Please wait for current response to finish before switching tabs.', 'info');
      }
      return;
    }

    if (!this.windows[windowId]) {
      windowId = 'global';
    }

    // Save current window's DOM
    if (this.windows[this.activeWindowId]) {
      const chatHistory = document.getElementById('chat-history');
      if (chatHistory) {
        this.windows[this.activeWindowId].messagesHtml = chatHistory.innerHTML;
      }
    }

    this.activeWindowId = windowId;
    const currentWin = this.windows[windowId];

    this.renderTabs();
    this.updateBanner();

    // Restore or initialize chat history DOM
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
      if (currentWin.messagesHtml && currentWin.messagesHtml.trim()) {
        chatHistory.innerHTML = currentWin.messagesHtml;
      } else {
        this.renderWelcomeHero(currentWin);
      }
      this.scrollToBottom();
    }

    // Update Player & Media Preview
    this.updatePlayerPanel();

    // Update Input Placeholder
    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      if (currentWin.id === 'global') {
        textarea.placeholder = 'Ask a question across all documents... (Shift+Enter for newline)';
      } else {
        textarea.placeholder = `Ask anything about ${currentWin.title}... (Shift+Enter for newline)`;
      }
      textarea.focus();
    }

    // Highlight active card in sidebar if DocuMindDocs is loaded
    if (window.DocuMindDocs && typeof DocuMindDocs.highlightActiveCard === 'function') {
      DocuMindDocs.highlightActiveCard(currentWin.filename);
    }
  },

  /**
   * Closes a window tab
   */
  closeWindow(windowId, event) {
    if (event) event.stopPropagation();
    if (windowId === 'global') return; // Cannot close global vault

    delete this.windows[windowId];

    if (this.activeWindowId === windowId) {
      // Pick another open window, or fallback to global
      const remainingIds = Object.keys(this.windows);
      const nextId = remainingIds.length > 0 ? remainingIds[remainingIds.length - 1] : 'global';
      this.switchWindow(nextId);
    } else {
      this.renderTabs();
    }
  },

  /**
   * Clears chat conversation for the active window
   */
  clearWindowChat() {
    const currentWin = this.windows[this.activeWindowId];
    if (currentWin) {
      currentWin.history = [];
      currentWin.messagesHtml = '';
    }
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
      this.renderWelcomeHero(currentWin);
    }
  },

  /**
   * Renders horizontal workspace tabs
   */
  renderTabs() {
    const tabsContainer = document.getElementById('tabs-scroll-area');
    if (!tabsContainer) return;

    tabsContainer.innerHTML = '';

    const winList = Object.values(this.windows);

    winList.forEach(win => {
      const isActive = win.id === this.activeWindowId;
      const isYouTube = win.fileType === 'youtube';
      const isGlobal = win.id === 'global';

      const tab = document.createElement('div');
      tab.className = `workspace-tab ${isYouTube ? 'youtube' : ''} ${isActive ? 'active' : ''}`;
      tab.title = win.title;
      tab.onclick = () => this.switchWindow(win.id);

      const iconSvg = isYouTube
        ? `<svg viewBox="0 0 24 24" fill="#ef4444" width="14" height="14"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`
        : (isGlobal 
            ? `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`
            : `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`);

      const closeHtml = isGlobal ? '' : `
        <button class="tab-close-btn" title="Close window tab" onclick="DocuMindApp.closeWindow('${win.id}', event)">×</button>
      `;

      tab.innerHTML = `
        <span class="tab-icon">${iconSvg}</span>
        <span class="tab-title">${win.title}</span>
        ${win.chunks > 0 ? `<span class="tab-badge">${win.chunks}c</span>` : ''}
        ${closeHtml}
      `;

      tabsContainer.appendChild(tab);
    });
  },

  /**
   * Updates the active window banner above chat
   */
  updateBanner() {
    const currentWin = this.windows[this.activeWindowId] || this.windows['global'];
    const bannerTitle = document.getElementById('banner-title');
    const bannerSub = document.getElementById('banner-subtitle');
    const bannerIcon = document.getElementById('banner-icon');
    const isolationBadge = document.getElementById('banner-isolation-badge');
    const togglePlayerBtn = document.getElementById('toggle-player-btn');

    if (!bannerTitle) return;

    const isYouTube = currentWin.fileType === 'youtube';
    const isGlobal = currentWin.id === 'global';

    bannerTitle.textContent = currentWin.title;

    if (bannerIcon) {
      bannerIcon.className = `window-banner-icon ${isYouTube ? 'youtube' : ''}`;
      bannerIcon.innerHTML = isYouTube
        ? `<svg viewBox="0 0 24 24" fill="#ef4444" width="16" height="16"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`
        : (isGlobal 
            ? `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`
            : `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`);
    }

    if (isolationBadge) {
      if (isGlobal) {
        isolationBadge.textContent = 'Multi-Vault';
        isolationBadge.className = 'window-badge-isolated global';
      } else {
        isolationBadge.textContent = 'Isolated Window';
        isolationBadge.className = 'window-badge-isolated';
      }
    }

    if (bannerSub) {
      if (isGlobal) {
        bannerSub.textContent = 'Searching across all indexed documents and videos';
      } else {
        bannerSub.textContent = `Strictly isolated to this material (${currentWin.chunks || 0} chunks indexed)`;
      }
    }

    if (togglePlayerBtn) {
      if (isYouTube && currentWin.videoId) {
        togglePlayerBtn.style.display = 'inline-flex';
        const label = document.getElementById('toggle-player-label');
        if (label) {
          label.textContent = currentWin.playerVisible ? 'Hide Player' : 'Show Player';
        }
      } else {
        togglePlayerBtn.style.display = 'none';
      }
    }
  },

  /**
   * Toggles video player visibility
   */
  togglePlayer() {
    const currentWin = this.windows[this.activeWindowId];
    if (!currentWin || !currentWin.videoId) return;

    currentWin.playerVisible = !currentWin.playerVisible;
    this.updatePlayerPanel();
    this.updateBanner();
  },

  /**
   * Updates the embedded player iframe
   */
  updatePlayerPanel() {
    const panel = document.getElementById('media-preview-panel');
    const iframe = document.getElementById('youtube-player-iframe');
    const currentWin = this.windows[this.activeWindowId];

    if (!panel || !iframe) return;

    if (currentWin && currentWin.fileType === 'youtube' && currentWin.videoId && currentWin.playerVisible) {
      panel.style.display = 'block';
      const targetSrc = `https://www.youtube.com/embed/${currentWin.videoId}?enablejsapi=1`;
      if (!iframe.src || !iframe.src.includes(currentWin.videoId)) {
        iframe.src = targetSrc;
      }
    } else {
      panel.style.display = 'none';
    }
  },

  /**
   * Jumps YouTube player to specific timestamp, opening/switching window if needed
   */
  seekTimestamp(tsStr, videoId = null) {
    let currentWin = this.windows[this.activeWindowId];

    // If target video ID specified and current window isn't that video, switch to it
    if (videoId && (!currentWin || currentWin.videoId !== videoId)) {
      const targetDoc = {
        filename: `YouTube: ${videoId}`,
        file_type: 'youtube',
        video_id: videoId
      };
      this.openWindow(targetDoc, true);
      currentWin = this.windows[this.activeWindowId];
    }

    if (!currentWin || !currentWin.videoId) return;

    // Convert MM:SS or HH:MM:SS to seconds
    const parts = tsStr.replace(/[\[\]]/g, '').split(':').map(Number);
    let seconds = 0;
    if (parts.length === 2) {
      seconds = parts[0] * 60 + parts[1];
    } else if (parts.length === 3) {
      seconds = parts[0] * 3600 + parts[1] * 60 + parts[2];
    }

    // Ensure player is visible
    currentWin.playerVisible = true;
    this.updatePlayerPanel();
    this.updateBanner();

    const iframe = document.getElementById('youtube-player-iframe');
    if (iframe) {
      iframe.src = `https://www.youtube.com/embed/${currentWin.videoId}?autoplay=1&start=${seconds}&enablejsapi=1`;
    }
  },

  /**
   * Renders welcome hero customized for the active window
   */
  renderWelcomeHero(win) {
    const chatHistory = document.getElementById('chat-history');
    if (!chatHistory) return;

    const isYouTube = win.fileType === 'youtube';
    const isGlobal = win.id === 'global';

    let heroTitle = isGlobal ? 'Talk to your Knowledge Vault' : `Talk to ${win.title}`;
    let heroSub = isGlobal
      ? 'Upload files or paste YouTube videos, and ask questions across all your data.'
      : (isYouTube
          ? `Ask any question about this YouTube video. Answers are strictly isolated to this video's transcript.`
          : `Ask any question about this document. Context is strictly isolated to this file.`);

    chatHistory.innerHTML = `
      <div id="welcome-hero" class="welcome-hero">
        <div class="hero-badge">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          ${isGlobal ? 'Multi-Source Vault' : 'Isolated Workspace'}
        </div>
        <h2 class="hero-title">${heroTitle}</h2>
        <p class="hero-subtitle">${heroSub}</p>
        <div class="suggested-grid">
          <div class="suggested-card" onclick="DocuMindApp.insertPrompt('${isYouTube ? 'Summarize the core takeaways of this video with timestamps.' : 'Summarize the key points in this material.'}')">
            <div class="suggested-card-title">📝 Executive Summary</div>
            <div class="suggested-card-desc">Get a quick briefing and main concepts.</div>
          </div>
          <div class="suggested-card" onclick="DocuMindApp.insertPrompt('What are the critical points and actionable advice?')">
            <div class="suggested-card-title">🎯 Key Takeaways</div>
            <div class="suggested-card-desc">Extract bullet points and notable details.</div>
          </div>
          <div class="suggested-card" onclick="DocuMindApp.insertPrompt('Explain the technical concepts described here.')">
            <div class="suggested-card-title">💡 Deep Dive</div>
            <div class="suggested-card-desc">Explain concepts clearly and thoroughly.</div>
          </div>
          <div class="suggested-card" onclick="DocuMindSettings.open()">
            <div class="suggested-card-title">⚙️ Configure API Keys</div>
            <div class="suggested-card-desc">Verify LLM & Embedding provider keys.</div>
          </div>
        </div>
      </div>
    `;
  },

  insertPrompt(text) {
    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      textarea.value = text;
      textarea.focus();
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }
  },

  async sendMessage() {
    if (this.isGenerating) return;

    const textarea = document.getElementById('chat-textarea');
    const message = textarea?.value?.trim();
    if (!message) return;

    // Clear input
    textarea.value = '';
    textarea.style.height = 'auto';

    // Hide hero
    const hero = document.getElementById('welcome-hero');
    if (hero) hero.style.display = 'none';

    const currentWin = this.windows[this.activeWindowId];

    // Capture prior history before appending the new user message
    const priorHistory = [...currentWin.history];

    // Append user message
    this.appendUserMessage(message);
    currentWin.history.push({ role: 'user', content: message });

    // Prepare AI response container
    const { bubbleEl, sourcesContainer } = this.appendAIMessage();
    this.setGenerating(true);

    const useRag = document.getElementById('rag-toggle')?.checked ?? true;
    const strictGuardrails = document.getElementById('strict-guardrails-main-toggle')?.checked ?? 
                             document.getElementById('strict-guardrails-toggle')?.checked ?? false;

    // Strict Scope: if this window is a specific video or file, scope queries ONLY to this filename!
    const scope = currentWin.id === 'global' ? null : currentWin.filename;

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          history: priorHistory,
          use_rag: useRag,
          strict_guardrails: strictGuardrails,
          scope: scope
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = '';
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.replace('data: ', '').trim();
          if (!dataStr) continue;

          try {
            const data = JSON.parse(dataStr);
            if (data.type === 'token') {
              accumulatedText += data.content;
              bubbleEl.innerHTML = this.renderMarkdown(accumulatedText);
              this.scrollToBottom();
            } else if (data.type === 'sources') {
              if (data.sources && data.sources.length > 0) {
                this.renderSources(sourcesContainer, data.sources);
              }
            } else if (data.type === 'error') {
              accumulatedText += `\n\n> ⚠️ **Error:** ${data.error}`;
              bubbleEl.innerHTML = this.renderMarkdown(accumulatedText);
            }
          } catch (err) {
            console.error('Error parsing SSE event:', err);
          }
        }
      }

      currentWin.history.push({ role: 'assistant', content: accumulatedText });

    } catch (e) {
      bubbleEl.innerHTML = `<p style="color: #f43f5e;">⚠️ Error: ${e.message}. Please verify your API key in Settings.</p>`;
    } finally {
      this.setGenerating(false);
      this.scrollToBottom();
      // Persist window DOM
      const chatHistory = document.getElementById('chat-history');
      if (chatHistory) {
        currentWin.messagesHtml = chatHistory.innerHTML;
      }
    }
  },

  appendUserMessage(text) {
    const chatHistory = document.getElementById('chat-history');
    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `
      <div class="message-bubble">${this.escapeHtml(text)}</div>
      <div class="message-avatar">You</div>
    `;
    chatHistory?.appendChild(row);
    this.scrollToBottom();
  },

  appendAIMessage() {
    const chatHistory = document.getElementById('chat-history');
    const row = document.createElement('div');
    row.className = 'message-row ai';
    row.innerHTML = `
      <div class="message-avatar">AI</div>
      <div class="message-bubble">
        <div class="ai-content"><span style="opacity: 0.6;">Thinking...</span></div>
        <div class="sources-container" style="display:none;"></div>
      </div>
    `;
    chatHistory?.appendChild(row);
    this.scrollToBottom();

    return {
      bubbleEl: row.querySelector('.ai-content'),
      sourcesContainer: row.querySelector('.sources-container')
    };
  },

  renderSources(container, sources) {
    container.style.display = 'block';
    container.innerHTML = `
      <div class="sources-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        <span>${sources.length} Retrieved Source(s)</span>
      </div>
      <div class="sources-list">
        ${sources.map(s => {
          let snippetWithTimestamps = this.escapeHtml(s.snippet);
          const vidId = s.file_type === 'youtube'
            ? (s.video_id || (s.filename && s.filename.startsWith('YouTube:') ? s.filename.replace('YouTube:', '').trim() : ''))
            : '';

          // Highlight timestamps and make them clickable across windows
          snippetWithTimestamps = snippetWithTimestamps.replace(/\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g, (match, p1) => {
            return `<span class="timestamp-link" onclick="DocuMindApp.seekTimestamp('${p1}', '${vidId}')" title="Play video from ${p1}">[${p1}]</span>`;
          });

          return `
            <div class="source-item">
              <div class="source-meta">
                ${s.file_type === 'youtube' ? '🎬' : '📄'} ${this.escapeHtml(s.filename)} 
                ${s.page ? `(Page ${s.page})` : `(Chunk ${s.chunk})`}
              </div>
              <div class="source-snippet">"${snippetWithTimestamps}"</div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  },

  setGenerating(isGenerating) {
    this.isGenerating = isGenerating;
    const sendBtn = document.getElementById('send-btn');
    const textarea = document.getElementById('chat-textarea');
    if (sendBtn) sendBtn.disabled = isGenerating;
    if (textarea && !isGenerating) textarea.focus();
  },

  scrollToBottom() {
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
      chatHistory.scrollTop = chatHistory.scrollHeight;
      requestAnimationFrame(() => {
        chatHistory.scrollTop = chatHistory.scrollHeight;
      });
    }
  },

  renderMarkdown(text) {
    if (window.marked && typeof window.marked.parse === 'function') {
      try {
        let parsed = window.marked.parse(text);
        // Make timestamp references like [01:25] clickable in markdown output
        const currentWin = this.windows[this.activeWindowId];
        const vidId = currentWin?.videoId || '';
        parsed = parsed.replace(/\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g, (match, p1) => {
          return `<span class="timestamp-link" onclick="DocuMindApp.seekTimestamp('${p1}', '${vidId}')" title="Play video from ${p1}">[${p1}]</span>`;
        });
        return parsed;
      } catch (e) {
        console.warn('Marked parse error, using fallback:', e);
      }
    }
    // Resilient offline fallback with headers, blockquotes, lists, code
    return this.escapeHtml(text)
      .replace(/^### (.*$)/gim, '<h3 style="font-size:1.02rem;font-weight:600;margin:6px 0;">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 style="font-size:1.15rem;font-weight:700;margin:8px 0;">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 style="font-size:1.25rem;font-weight:700;margin:10px 0;">$1</h1>')
      .replace(/^\> (.*$)/gim, '<blockquote style="border-left:3px solid var(--accent-primary);padding-left:10px;margin:6px 0;opacity:0.85;">$1</blockquote>')
      .replace(/^\- (.*$)/gim, '<li style="margin-left:18px;">$1</li>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08);padding:2px 5px;border-radius:4px;font-family:monospace;">$1</code>')
      .replace(/\n\n/g, '<p style="margin:6px 0;"></p>')
      .replace(/\n/g, '<br>');
  },

  escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },

  /**
   * Exports conversation of the current active window as Markdown notes
   */
  exportChat() {
    const currentWin = this.windows[this.activeWindowId];
    if (!currentWin || !currentWin.history || currentWin.history.length === 0) {
      if (window.DocuMindSettings?.showToast) {
        DocuMindSettings.showToast('No chat history to export in this window yet!', 'error');
      } else {
        alert('No chat history to export in this window yet!');
      }
      return;
    }

    const title = currentWin.title || 'DocuMind_Chat';
    const dateStr = new Date().toLocaleString();
    let md = `# DocuMind Notes: ${title}\n\n`;
    md += `*Generated on: ${dateStr}*\n`;
    if (currentWin.filename) {
      md += `*Source Document: ${currentWin.filename}*\n`;
    }
    md += `\n---\n\n`;

    currentWin.history.forEach((msg) => {
      if (msg.role === 'user') {
        md += `### 👤 Question\n${msg.content}\n\n`;
      } else if (msg.role === 'assistant') {
        md += `### 🤖 DocuMind Answer\n${msg.content}\n\n---\n\n`;
      }
    });

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const sanitizedTitle = title.replace(/[^a-zA-Z0-9_\-\.]/g, '_').substring(0, 40);
    a.download = `${sanitizedTitle}_Notes.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    if (window.DocuMindSettings?.showToast) {
      DocuMindSettings.showToast('Exported chat notes successfully (.md)!', 'success');
    }
  }
};

window.DocuMindApp = DocuMindApp;
document.addEventListener('DOMContentLoaded', () => DocuMindApp.init());
