const DocuMindApp = {
  conversationHistory: [],
  isGenerating: false,

  init() {
    this.bindEvents();
  },

  bindEvents() {
    const sendBtn = document.getElementById('send-btn');
    const textarea = document.getElementById('chat-textarea');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
    const sidebar = document.getElementById('app-sidebar');

    sendBtn?.addEventListener('click', () => this.sendMessage());

    clearChatBtn?.addEventListener('click', () => {
      if (confirm('Clear the current conversation?')) {
        this.clearConversation();
      }
    });

    sidebarToggleBtn?.addEventListener('click', () => {
      sidebar?.classList.toggle('open');
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

  insertPrompt(text) {
    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      textarea.value = text;
      textarea.focus();
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }
  },

  clearConversation() {
    this.conversationHistory = [];
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
      chatHistory.innerHTML = `
        <div id="welcome-hero" class="welcome-hero">
          <div class="hero-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
            Private & Self-Hosted AI
          </div>
          <h2 class="hero-title">Talk to your Documents</h2>
          <p class="hero-subtitle">Upload files, configure your preferred LLM & Embedding keys, and experience seamless RAG retrieval.</p>
          <div class="suggested-grid">
            <div class="suggested-card" onclick="DocuMindApp.insertPrompt('Summarize the key insights from the uploaded documents.')">
              <div class="suggested-card-title">📄 Document Summary</div>
              <div class="suggested-card-desc">Get a high-level briefing of your files.</div>
            </div>
            <div class="suggested-card" onclick="DocuMindApp.insertPrompt('What are the main action items or takeaways?')">
              <div class="suggested-card-title">🎯 Action Items</div>
              <div class="suggested-card-desc">Extract bullet points and critical decisions.</div>
            </div>
            <div class="suggested-card" onclick="DocuMindApp.insertPrompt('Explain the complex technical concepts described in the documents.')">
              <div class="suggested-card-title">💡 Deep Dive</div>
              <div class="suggested-card-desc">Explain technical concepts in simple terms.</div>
            </div>
            <div class="suggested-card" onclick="DocuMindSettings.open()">
              <div class="suggested-card-title">⚙️ Configure API Keys</div>
              <div class="suggested-card-desc">Set up OpenAI, Gemini, Claude, or Groq.</div>
            </div>
          </div>
        </div>
      `;
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

    // Append user message
    this.appendUserMessage(message);
    this.conversationHistory.push({ role: 'user', content: message });

    // Prepare AI response container
    const { bubbleEl, sourcesContainer } = this.appendAIMessage();
    this.setGenerating(true);

    const useRag = document.getElementById('rag-toggle')?.checked ?? true;
    const strictGuardrails = document.getElementById('strict-guardrails-toggle')?.checked ?? true;

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          history: this.conversationHistory,
          use_rag: useRag,
          strict_guardrails: strictGuardrails
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
              bubbleEl.innerHTML = marked.parse(accumulatedText);
              this.scrollToBottom();
            } else if (data.type === 'sources') {
              if (data.sources && data.sources.length > 0) {
                this.renderSources(sourcesContainer, data.sources);
              }
            } else if (data.type === 'error') {
              accumulatedText += `\n\n> ⚠️ **Error:** ${data.error}`;
              bubbleEl.innerHTML = marked.parse(accumulatedText);
            }
          } catch (err) {
            console.error('Error parsing SSE event:', err);
          }
        }
      }

      this.conversationHistory.push({ role: 'assistant', content: accumulatedText });

    } catch (e) {
      bubbleEl.innerHTML = `<p style="color: #f43f5e;">⚠️ Error: ${e.message}. Please verify your API key in Settings.</p>`;
    } finally {
      this.setGenerating(false);
      this.scrollToBottom();
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
        ${sources.map(s => `
          <div class="source-item">
            <div class="source-meta">📄 ${s.filename} ${s.page ? `(Page ${s.page})` : `(Chunk ${s.chunk})`}</div>
            <div class="source-snippet">"${this.escapeHtml(s.snippet)}"</div>
          </div>
        `).join('')}
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
    }
  },

  escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
};

document.addEventListener('DOMContentLoaded', () => DocuMindApp.init());
