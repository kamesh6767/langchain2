const DocuMindDocs = {
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
  },

  async loadDocuments() {
    try {
      const res = await fetch('/api/docs');
      if (!res.ok) throw new Error('Failed to fetch documents');
      const data = await res.json();
      this.renderDocumentList(data);
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
        DocuMindSettings.showToast(`Indexed YouTube video (${data.video.chunks} chunks)!`, 'success');
        input.value = '';
        this.renderDocumentList(data.stats);
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
        const successes = data.uploaded.filter(u => u.success).length;
        DocuMindSettings.showToast(`Indexed ${successes} document(s) successfully!`, 'success');
        this.renderDocumentList(data.stats);
      } else {
        DocuMindSettings.showToast(data.detail || 'Upload failed', 'error');
      }
    } catch (e) {
      DocuMindSettings.showToast('Upload error: ' + e.message, 'error');
    }
  },

  renderDocumentList(stats) {
    const listContainer = document.getElementById('doc-list');
    const badge = document.getElementById('doc-counter-badge');

    if (badge) {
      badge.textContent = `${stats.total_documents || 0} Sources (${stats.total_chunks || 0} chunks)`;
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

    listContainer.innerHTML = '';
    stats.documents.forEach(doc => {
      const isYouTube = doc.file_type === 'youtube' || doc.filename.startsWith('YouTube:');
      const card = document.createElement('div');
      card.className = 'doc-card';
      
      const iconHtml = isYouTube
        ? `<svg viewBox="0 0 24 24" fill="#ef4444" width="16" height="16"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`
        : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;

      card.innerHTML = `
        <div class="doc-info">
          <div class="doc-icon" style="${isYouTube ? 'background: rgba(239, 68, 68, 0.12);' : ''}">
            ${iconHtml}
          </div>
          <div class="doc-details">
            <div class="doc-name" title="${doc.filename}">${doc.filename}</div>
            <div class="doc-meta">${doc.chunks} chunks • ${doc.file_type || 'file'}</div>
          </div>
        </div>
        <button class="doc-delete-btn" title="Delete document" onclick="DocuMindDocs.deleteDocument('${encodeURIComponent(doc.filename)}')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      `;
      listContainer.appendChild(card);
    });
  },

  async deleteDocument(encodedFilename) {
    const filename = decodeURIComponent(encodedFilename);
    if (!confirm(`Delete "${filename}" and its vector embeddings?`)) return;

    try {
      const res = await fetch(`/api/docs/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (res.ok) {
        DocuMindSettings.showToast(`Deleted ${filename}`, 'info');
        this.loadDocuments();
      } else {
        DocuMindSettings.showToast('Failed to delete document', 'error');
      }
    } catch (e) {
      DocuMindSettings.showToast('Delete error: ' + e.message, 'error');
    }
  },

  async clearAll() {
    if (!confirm('Are you sure you want to clear ALL indexed material and vector embeddings?')) return;

    try {
      const res = await fetch('/api/docs', { method: 'DELETE' });
      if (res.ok) {
        DocuMindSettings.showToast('Knowledge base cleared', 'info');
        this.loadDocuments();
      } else {
        DocuMindSettings.showToast('Failed to clear knowledge base', 'error');
      }
    } catch (e) {
      DocuMindSettings.showToast('Error: ' + e.message, 'error');
    }
  }
};

document.addEventListener('DOMContentLoaded', () => DocuMindDocs.init());
