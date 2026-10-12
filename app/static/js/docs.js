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

    dropzone?.addEventListener('click', () => fileInput?.click());
    inlineUpload?.addEventListener('click', () => fileInput?.click());

    fileInput?.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.uploadFiles(Array.from(e.target.files));
        fileInput.value = '';
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
      badge.textContent = `${stats.total_documents || 0} Docs (${stats.total_chunks || 0} chunks)`;
    }

    if (!listContainer) return;

    if (!stats.documents || stats.documents.length === 0) {
      listContainer.innerHTML = `
        <div class="doc-list-empty" id="doc-empty-state">
          No documents indexed yet.<br>Upload files to start chatting with your data.
        </div>
      `;
      return;
    }

    listContainer.innerHTML = '';
    stats.documents.forEach(doc => {
      const card = document.createElement('div');
      card.className = 'doc-card';
      card.innerHTML = `
        <div class="doc-info">
          <div class="doc-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
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
    if (!confirm('Are you sure you want to clear ALL indexed documents and vector embeddings?')) return;

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
