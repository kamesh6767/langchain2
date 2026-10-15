const DocuMindDocs = {
  currentStats: null,

  init() {
    this.bindEvents();
    this.loadDocuments();
  },

  bindEvents() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const inlineUpload = document.getElementById('upload-btn-inline');
    const clearAllBtn = document.getElementById('clear-all-docs-btn');
    const addYtBtn = document.getElementById('add-youtube-btn');
    const ytInput = document.getElementById('youtube-url-input');

    dropzone?.addEventListener('click', () => fileInput?.click());
    inlineUpload?.addEventListener('click', () => fileInput?.click());

    fileInput?.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.uploadFiles(Array.from(e.target.files));
        fileInput.value = '';
      }
    });

    // YouTube ingestion events
    addYtBtn?.addEventListener('click', () => this.indexYouTube());
    ytInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.indexYouTube();
      }
    });

    // Drag and Drop
    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone?.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone?.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone?.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        this.uploadFiles(Array.from(dt.files));
      }
    });

    clearAllBtn?.addEventListener('click', () => this.clearAll());

    // Delegated click listener on #doc-list for reliable delete and open actions
    const docList = document.getElementById('doc-list');
    docList?.addEventListener('click', (e) => {
      const deleteBtn = e.target.closest('.doc-delete-btn');
      if (deleteBtn) {
        e.preventDefault();
        e.stopPropagation();
        const filename = deleteBtn.getAttribute('data-filename');
        if (filename) {
          this.deleteDocument(filename);
        }
        return;
      }

      const openBtn = e.target.closest('.doc-open-btn');
      if (openBtn) {
        e.preventDefault();
        e.stopPropagation();
        const filename = openBtn.getAttribute('data-filename');
        const doc = this.currentStats?.documents?.find(d => d.filename === filename);
        if (doc) {
          this.openDocumentWindow(doc, e);
        }
        return;
      }
    });
  },

  async loadDocuments() {
    try {
      const res = await fetch('/api/docs');
      if (!res.ok) throw new Error('Failed to fetch documents');
      const data = await res.json();
      this.currentStats = data;
      this.renderDocumentList(data);

      // Populate open windows for existing indexed items if not already opened
      if (data.documents && data.documents.length > 0 && window.DocuMindApp) {
        data.documents.forEach(doc => {
          // Register window tab for each indexed video/document
          DocuMindApp.openWindow(doc, false);
        });
      }
    } catch (e) {
      console.error('Error loading documents:', e);
    }
  },

  async indexYouTube() {
    const input = document.getElementById('youtube-url-input');
    const url = input?.value?.trim();
    if (!url) {
      DocuMindSettings.showToast('Please enter a YouTube link or video ID', 'error');
      return;
    }

    DocuMindSettings.showToast('Fetching YouTube transcript and embedding...', 'info');

    try {
      const res = await fetch('/api/docs/youtube', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        input.value = '';
        this.currentStats = data.stats;
        this.renderDocumentList(data.stats);

        // Open a SEPARATE NEW WINDOW specifically for this video!
        if (window.DocuMindApp) {
          DocuMindApp.openWindow(data.video, true);
        }

        DocuMindSettings.showToast(`Opened dedicated window for YouTube video (${data.video.chunks} chunks)!`, 'success');
      } else {
        DocuMindSettings.showToast(data.detail || 'Failed to index YouTube video', 'error');
      }
    } catch (e) {
      DocuMindSettings.showToast('YouTube indexing error: ' + e.message, 'error');
    }
  },

  async uploadFiles(files) {
    if (!files.length) return;

    DocuMindSettings.showToast(`Uploading and embedding ${files.length} document(s)...`);

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    try {
      const res = await fetch('/api/docs/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (res.ok) {
        const successes = data.uploaded.filter(u => u.success);
        DocuMindSettings.showToast(`Indexed ${successes.length} document(s) successfully!`, 'success');
        this.currentStats = data.stats;
        this.renderDocumentList(data.stats);

        // Open dedicated separate windows for newly uploaded files
        if (window.DocuMindApp && data.stats && data.stats.documents) {
          successes.forEach(s => {
            const docObj = data.stats.documents.find(d => d.filename === s.filename);
            if (docObj) {
              DocuMindApp.openWindow(docObj, true);
            }
          });
        }
      } else {
        DocuMindSettings.showToast(data.detail || 'Upload failed', 'error');
      }
    } catch (e) {
      DocuMindSettings.showToast('Upload error: ' + e.message, 'error');
    }
  },

  openDocumentWindow(doc, event) {
    if (event) event.stopPropagation();
    if (window.DocuMindApp && doc) {
      DocuMindApp.openWindow(doc, true);
      if (window.innerWidth <= 768) {
        document.getElementById('app-sidebar')?.classList.remove('open');
      }
    }
  },

  highlightActiveCard(activeFilename) {
    const cards = document.querySelectorAll('.doc-card');
    cards.forEach(card => {
      const cardFilename = card.getAttribute('data-filename');
      if (cardFilename === activeFilename) {
        card.classList.add('active');
      } else {
        card.classList.remove('active');
      }
    });
  },

  renderDocumentList(stats) {
    const listContainer = document.getElementById('doc-list');
    const badge = document.getElementById('doc-counter-badge');

    if (badge) {
      badge.textContent = `${stats.total_documents || 0} Docs • ${stats.total_chunks || 0}c`;
      badge.title = `${stats.total_documents || 0} indexed sources (${stats.total_chunks || 0} total chunks)`;
    }

    if (!listContainer) return;

    if (!stats.documents || stats.documents.length === 0) {
      listContainer.innerHTML = `
        <div class="doc-list-empty" id="doc-empty-state">
          No material indexed yet.<br>Paste a YouTube video or drop files to start.
        </div>
      `;
      return;
    }

    const activeWin = window.DocuMindApp ? DocuMindApp.windows[DocuMindApp.activeWindowId] : null;
    const activeFilename = activeWin ? activeWin.filename : null;

    listContainer.innerHTML = '';
    stats.documents.forEach(doc => {
      const isYouTube = doc.file_type === 'youtube' || doc.filename.startsWith('YouTube:');
      const isActive = doc.filename === activeFilename;

      const card = document.createElement('div');
      card.className = `doc-card ${isActive ? 'active' : ''}`;
      card.setAttribute('data-filename', doc.filename);

      const iconHtml = isYouTube
        ? `<svg viewBox="0 0 24 24" fill="#ef4444" width="16" height="16"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`
        : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;

      const safeFilename = this.escapeHtml(doc.filename);
      card.innerHTML = `
        <div class="doc-info">
          <div class="doc-icon" style="${isYouTube ? 'background: rgba(239, 68, 68, 0.12);' : ''}">
            ${iconHtml}
          </div>
          <div class="doc-details">
            <div class="doc-name" title="${safeFilename}">${safeFilename}</div>
            <div class="doc-meta">${doc.chunks} chunks • ${doc.file_type || 'file'}</div>
          </div>
        </div>
        <div class="doc-card-actions">
          <button class="doc-open-btn" data-filename="${safeFilename}" title="Open separate chat window" type="button">Open</button>
          <button class="doc-delete-btn" data-filename="${safeFilename}" title="Delete document" type="button">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;

      // Safe clean event listeners without inline stringified JSON
      card.addEventListener('click', (e) => {
        if (!e.target.closest('.doc-delete-btn') && !e.target.closest('.doc-open-btn')) {
          this.openDocumentWindow(doc, e);
        }
      });

      const openBtn = card.querySelector('.doc-open-btn');
      openBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        this.openDocumentWindow(doc, e);
      });

      const deleteBtn = card.querySelector('.doc-delete-btn');
      deleteBtn?.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.deleteDocument(doc.filename);
      });

      listContainer.appendChild(card);
    });
  },

  deleteDocument(filename) {
    if (!filename) return;

    const executeDelete = async () => {
      try {
        DocuMindSettings.showToast(`Deleting ${filename}...`, 'info');
        const res = await fetch(`/api/docs/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        if (res.ok) {
          DocuMindSettings.showToast(`Deleted "${filename}" successfully`, 'success');

          // Close window in DocuMindApp if open
          if (window.DocuMindApp) {
            const winId = DocuMindApp.getWindowId(filename);
            DocuMindApp.closeWindow(winId);
          }

          this.loadDocuments();
        } else {
          const errData = await res.json().catch(() => ({}));
          DocuMindSettings.showToast(errData.detail || 'Failed to delete document', 'error');
        }
      } catch (e) {
        DocuMindSettings.showToast('Delete error: ' + e.message, 'error');
      }
    };

    if (window.DocuMindConfirm) {
      DocuMindConfirm.show({
        title: 'Delete Document',
        message: `Are you sure you want to delete "${filename}" and its vector embeddings?`,
        confirmText: 'Delete',
        icon: '🗑️',
        isDanger: true,
        onConfirm: executeDelete
      });
    } else {
      if (confirm(`Delete "${filename}" and its vector embeddings?`)) {
        executeDelete();
      }
    }
  },

  clearAll() {
    const executeClear = async () => {
      try {
        DocuMindSettings.showToast('Clearing knowledge base...', 'info');
        const res = await fetch('/api/docs', { method: 'DELETE' });
        if (res.ok) {
          DocuMindSettings.showToast('Knowledge base cleared successfully', 'success');

          // Close all windows and reset to global
          if (window.DocuMindApp) {
            DocuMindApp.windows = {
              'global': {
                id: 'global',
                title: 'Global Vault',
                filename: null,
                fileType: 'vault',
                videoId: null,
                chunks: 0,
                history: [],
                messagesHtml: '',
                playerVisible: false
              }
            };
            DocuMindApp.switchWindow('global');
          }

          this.loadDocuments();
        } else {
          DocuMindSettings.showToast('Failed to clear knowledge base', 'error');
        }
      } catch (e) {
        DocuMindSettings.showToast('Error: ' + e.message, 'error');
      }
    };

    if (window.DocuMindConfirm) {
      DocuMindConfirm.show({
        title: 'Clear Knowledge Base',
        message: 'Are you sure you want to permanently clear ALL indexed documents, YouTube transcripts, and vector embeddings?',
        confirmText: 'Clear All',
        icon: '⚠️',
        isDanger: true,
        onConfirm: executeClear
      });
    } else {
      if (confirm('Are you sure you want to clear ALL indexed material and vector embeddings?')) {
        executeClear();
      }
    }
  },

  escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
};

window.DocuMindDocs = DocuMindDocs;
document.addEventListener('DOMContentLoaded', () => DocuMindDocs.init());
