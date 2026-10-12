const DocuMindSettings = {
  currentConfig: null,

  init() {
    this.bindEvents();
    this.loadSettings();
  },

  bindEvents() {
    const modal = document.getElementById('settings-modal');
    const openBtn = document.getElementById('open-settings-btn');
    const closeBtn = document.getElementById('close-settings-btn');
    const cancelBtn = document.getElementById('cancel-settings-btn');
    const saveBtn = document.getElementById('save-settings-btn');
    const activeChip = document.getElementById('active-model-chip');

    openBtn?.addEventListener('click', () => this.open());
    activeChip?.addEventListener('click', () => this.open());
    closeBtn?.addEventListener('click', () => this.close());
    cancelBtn?.addEventListener('click', () => this.close());
    saveBtn?.addEventListener('click', () => this.save());

    // Close on clicking backdrop
    modal?.addEventListener('click', (e) => {
      if (e.target === modal) this.close();
    });

    // Provider select change updates default model suggestion
    const llmSelect = document.getElementById('select-llm-provider');
    llmSelect?.addEventListener('change', (e) => {
      const val = e.target.value;
      const modelInput = document.getElementById('input-llm-model');
      if (val === 'openai') modelInput.value = 'gpt-4o-mini';
      else if (val === 'gemini') modelInput.value = 'gemini-1.5-flash';
      else if (val === 'anthropic') modelInput.value = 'claude-3-5-sonnet-20240620';
      else if (val === 'groq') modelInput.value = 'llama-3.1-8b-instant';
    });

    const embedSelect = document.getElementById('select-embedding-provider');
    embedSelect?.addEventListener('change', (e) => {
      const val = e.target.value;
      const modelInput = document.getElementById('input-embedding-model');
      if (val === 'openai') modelInput.value = 'text-embedding-3-small';
      else if (val === 'gemini') modelInput.value = 'models/embedding-001';
      else if (val === 'huggingface') modelInput.value = 'all-MiniLM-L6-v2';
    });
  },

  open() {
    document.getElementById('settings-modal')?.classList.add('open');
    this.loadSettings();
  },

  close() {
    document.getElementById('settings-modal')?.classList.remove('open');
  },

  async loadSettings() {
    try {
      const res = await fetch('/api/config');
      if (!res.ok) throw new Error('Failed to load configuration');
      const data = await res.json();
      this.currentConfig = data;
      this.populateUI(data);
    } catch (e) {
      this.showToast('Could not load settings: ' + e.message, 'error');
    }
  },

  populateUI(cfg) {
    // Badges & Placeholders
    const providers = ['openai', 'gemini', 'anthropic', 'groq'];
    let anyConfigured = false;

    providers.forEach(p => {
      const isConfigured = cfg.keys_configured?.[p];
      if (isConfigured) anyConfigured = true;

      const badge = document.getElementById(`badge-${p}`);
      const input = document.getElementById(`key-${p}`);

      if (badge) {
        badge.className = `key-status-indicator ${isConfigured ? 'configured' : 'missing'}`;
        badge.textContent = isConfigured ? 'Configured' : 'Not Configured';
      }

      if (input && cfg.masked_keys?.[p]) {
        input.placeholder = cfg.masked_keys[p];
      }
    });

    // Update active model chip in header
    const chipLabel = document.getElementById('active-model-name');
    const chipDot = document.getElementById('system-status-dot');
    if (chipLabel) {
      chipLabel.textContent = `${cfg.default_llm_provider.toUpperCase()} (${cfg.default_llm_model})`;
    }
    if (chipDot) {
      chipDot.className = `status-dot ${anyConfigured ? '' : 'warning'}`;
    }

    // Populate selectors
    const llmSelect = document.getElementById('select-llm-provider');
    const llmModel = document.getElementById('input-llm-model');
    const embSelect = document.getElementById('select-embedding-provider');
    const embModel = document.getElementById('input-embedding-model');
    const chunkSize = document.getElementById('input-chunk-size');
    const chunkOverlap = document.getElementById('input-chunk-overlap');

    if (llmSelect) llmSelect.value = cfg.default_llm_provider || 'openai';
    if (llmModel) llmModel.value = cfg.default_llm_model || 'gpt-4o-mini';
    if (embSelect) embSelect.value = cfg.default_embedding_provider || 'openai';
    if (embModel) embModel.value = cfg.default_embedding_model || 'text-embedding-3-small';
    if (chunkSize) chunkSize.value = cfg.chunk_size || 1000;
    if (chunkOverlap) chunkOverlap.value = cfg.chunk_overlap || 200;

    const guardrailsToggle = document.getElementById('strict-guardrails-toggle');
    if (guardrailsToggle) {
      guardrailsToggle.checked = cfg.strict_guardrails !== false;
    }
  },

  async testKey(provider) {
    const input = document.getElementById(`key-${provider}`);
    const keyVal = input?.value?.trim() || '';

    this.showToast(`Testing ${provider} connection...`);

    try {
      const res = await fetch('/api/config/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: keyVal || null })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        this.showToast(data.message, 'success');
      } else {
        this.showToast(data.message || data.detail || 'Connection test failed', 'error');
      }
    } catch (e) {
      this.showToast('Test failed: ' + e.message, 'error');
    }
  },

  async save() {
    const payload = {};

    const openAiVal = document.getElementById('key-openai')?.value?.trim();
    const geminiVal = document.getElementById('key-gemini')?.value?.trim();
    const anthropicVal = document.getElementById('key-anthropic')?.value?.trim();
    const groqVal = document.getElementById('key-groq')?.value?.trim();

    if (openAiVal) payload.OPENAI_API_KEY = openAiVal;
    if (geminiVal) payload.GEMINI_API_KEY = geminiVal;
    if (anthropicVal) payload.ANTHROPIC_API_KEY = anthropicVal;
    if (groqVal) payload.GROQ_API_KEY = groqVal;

    payload.DEFAULT_LLM_PROVIDER = document.getElementById('select-llm-provider')?.value;
    payload.DEFAULT_LLM_MODEL = document.getElementById('input-llm-model')?.value?.trim();
    payload.DEFAULT_EMBEDDING_PROVIDER = document.getElementById('select-embedding-provider')?.value;
    payload.DEFAULT_EMBEDDING_MODEL = document.getElementById('input-embedding-model')?.value?.trim();
    payload.CHUNK_SIZE = parseInt(document.getElementById('input-chunk-size')?.value) || 1000;
    payload.CHUNK_OVERLAP = parseInt(document.getElementById('input-chunk-overlap')?.value) || 200;
    payload.STRICT_GUARDRAILS = document.getElementById('strict-guardrails-toggle')?.checked ?? true;

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Failed to save settings');
      const data = await res.json();
      this.populateUI(data);
      this.showToast('Settings saved successfully!', 'success');
      this.close();
    } catch (e) {
      this.showToast('Error saving: ' + e.message, 'error');
    }
  },

  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = '0.3s';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
};

document.addEventListener('DOMContentLoaded', () => DocuMindSettings.init());
