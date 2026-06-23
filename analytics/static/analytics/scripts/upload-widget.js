/**
 * upload-widget.js
 * Chunked, resumable file upload widget for the Releases dashboard.
 */
(function () {
  'use strict';

  const MAX_RETRIES_PER_CHUNK = 5;
  const LIST_REFRESH_DELAY_MS = 1000;

  // ── Utilities ──────────────────────────────────────────────────────────

  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // ── API helpers ──────────────────────────────────────────────────────

  async function postForm(url, formData) {
    console.log('[upload] POST to:', url, 'data:', [...formData]);
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      body: formData,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      console.error('[upload] Error response:', data);
      throw new Error(data.error || `Request failed (${resp.status})`);
    }
    return data;
  }

  // ── Upload logic ────────────────────────────────────────────────────

  async function uploadChunkWithRetry(uploadId, chunkIndex, chunkBlob, urls) {
    let lastError = null;
    for (let attempt = 0; attempt < MAX_RETRIES_PER_CHUNK; attempt++) {
      try {
        const form = new FormData();
        form.append('chunk_index', chunkIndex);
        form.append('chunk', chunkBlob);
        return await postForm(urls.chunkUrl(uploadId), form);
      } catch (err) {
        lastError = err;
        await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)));
      }
    }
    throw lastError;
  }

  async function uploadFile(file, urls, chunkSize, onProgress) {
    // Init
    const initForm = new FormData();
    initForm.append('filename', file.name);
    initForm.append('total_size', file.size);
    initForm.append('chunk_size', chunkSize);
    console.log('[upload] Init payload:', { filename: file.name, total_size: file.size, chunk_size: chunkSize });
    const initResp = await postForm(urls.initUrl(), initForm);
    const uploadId = initResp.upload_id;
    const totalChunks = initResp.total_chunks;
    const actualChunkSize = initResp.chunk_size || chunkSize;

    // Chunks
    for (let i = 0; i < totalChunks; i++) {
      const start = i * actualChunkSize;
      const end = Math.min(start + actualChunkSize, file.size);
      const chunkBlob = file.slice(start, end);
      const result = await uploadChunkWithRetry(uploadId, i, chunkBlob, urls);
      onProgress(result.progress_percent, result.bytes_received, file.size);
    }

    // Complete
    const completeResp = await postForm(urls.completeUrl(uploadId), new FormData());
    return completeResp;
  }

  // ── DOM builders ────────────────────────────────────────────────────

  function createProgressRow(filename) {
    const row = document.createElement('div');
    row.className = 'upload-row';
    row.innerHTML = `
      <div class="upload-row-info">
        <span class="upload-row-name">${escapeHtml(filename)}</span>
        <span class="upload-row-status">Starting…</span>
      </div>
      <div class="upload-row-bar-track">
        <div class="upload-row-bar-fill" style="width: 0%"></div>
      </div>
    `;
    return row;
  }

  function createUploadRowFromData(upload, deleteUrlTemplate) {
    const row = document.createElement('div');
    row.className = 'upload-row';
    row.dataset.uploadId = upload.id;
    const statusClass = upload.status === 'completed' ? 'upload-row-completed' : '';
    const progress = upload.progress_percent || 0;
    row.innerHTML = `
      <div class="upload-row-info">
        <span class="upload-row-name">${escapeHtml(upload.filename)}</span>
        <span class="upload-row-status">${escapeHtml(upload.status)}</span>
        <button class="upload-delete-btn" data-id="${escapeHtml(upload.id)}">Delete</button>
      </div>
      <div class="upload-row-bar-track">
        <div class="upload-row-bar-fill" style="width: ${progress}%"></div>
      </div>
    `;
    if (statusClass) row.classList.add(statusClass);

    const deleteBtn = row.querySelector('.upload-delete-btn');
    deleteBtn.addEventListener('click', async function (e) {
      e.stopPropagation();
      const id = this.dataset.id;
      if (!confirm('Delete this upload record and its file?')) return;
      try {
        const url = deleteUrlTemplate.replace('PLACEHOLDER', id);
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
        });
        if (resp.ok) {
          row.remove();
        } else {
          const errData = await resp.json().catch(() => ({}));
          alert('Failed to delete: ' + (errData.error || 'Unknown error'));
        }
      } catch (err) {
        alert('Error deleting: ' + err.message);
      }
    });

    return row;
  }

  // ── Load existing uploads ──────────────────────────────────────────

  async function loadUploads(listElement, listUrl, deleteUrlTemplate) {
    try {
      console.log('[upload] Loading upload list from:', listUrl);
      const resp = await fetch(listUrl);
      if (!resp.ok) throw new Error('Failed to fetch upload list');
      const data = await resp.json();
      if (data.uploads) {
        listElement.innerHTML = '';
        if (data.uploads.length === 0) {
          listElement.innerHTML = '<p class="upload-empty">No uploads yet.</p>';
        } else {
          data.uploads.forEach(upload => {
            const row = createUploadRowFromData(upload, deleteUrlTemplate);
            listElement.appendChild(row);
          });
        }
      }
    } catch (e) {
      console.warn('Could not load upload list:', e);
      listElement.innerHTML = '<p class="upload-error">Could not load upload history.</p>';
    }
  }

  // ── Main initialisation ────────────────────────────────────────────

  function initUploadWidget(dropzoneSelector, listSelector) {
    const dropzone = document.querySelector(dropzoneSelector);
    const list = document.querySelector(listSelector);
    if (!dropzone || !list) {
      console.warn('[upload] Dropzone or list not found');
      return;
    }

    // Read URLs from data attributes
    const initUrl = dropzone.dataset.initUrl;
    const chunkUrlTemplate = dropzone.dataset.chunkUrlTemplate;
    const completeUrlTemplate = dropzone.dataset.completeUrlTemplate;
    const deleteUrlTemplate = dropzone.dataset.deleteUrlTemplate;
    const listUrl = dropzone.dataset.listUrl;
    const chunkSize = parseInt(dropzone.dataset.chunkSize, 10) || (5 * 1024 * 1024);

    console.log('[upload] Init with:', { initUrl, chunkUrlTemplate, completeUrlTemplate, deleteUrlTemplate, listUrl, chunkSize });

    const urls = {
      initUrl: () => initUrl,
      chunkUrl: (id) => chunkUrlTemplate.replace('PLACEHOLDER', id),
      completeUrl: (id) => completeUrlTemplate.replace('PLACEHOLDER', id),
    };

    // Load existing uploads
    loadUploads(list, listUrl, deleteUrlTemplate);

    // File handler
    async function handleFiles(files) {
      for (const file of files) {
        const row = createProgressRow(file.name);
        list.prepend(row);
        const statusEl = row.querySelector('.upload-row-status');
        const barEl = row.querySelector('.upload-row-bar-fill');

        try {
          await uploadFile(file, urls, chunkSize, (percent, received, total) => {
            barEl.style.width = `${percent}%`;
            statusEl.textContent = `${formatBytes(received)} / ${formatBytes(total)} (${percent}%)`;
          });
          statusEl.textContent = 'Completed';
          row.classList.add('upload-row-completed');
          setTimeout(() => loadUploads(list, listUrl, deleteUrlTemplate), LIST_REFRESH_DELAY_MS);
        } catch (err) {
          statusEl.textContent = `Failed: ${err.message}`;
          row.classList.add('upload-row-failed');
        }
      }
    }

    // Drag & drop
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
    });

    // File input
    const fileInput = dropzone.querySelector('input[type="file"]');
    if (fileInput) {
      fileInput.addEventListener('change', () => {
        if (fileInput.files.length) handleFiles(fileInput.files);
        fileInput.value = '';
      });
    }
  }

  // Expose globally
  window.initUploadWidget = initUploadWidget;
})();