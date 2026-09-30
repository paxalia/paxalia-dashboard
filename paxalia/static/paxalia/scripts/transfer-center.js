/* Paxalia Transfer Center: chunked, resumable, checksum-verified browser transfers. */
(function () {
  'use strict';

  var K = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];

  function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }

  function Sha256() {
    this.h = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
    this.buffer = new Uint8Array(64);
    this.bufferLength = 0;
    this.bytesHashed = 0;
    this.finished = false;
    this.w = new Uint32Array(64);
  }

  Sha256.prototype.update = function (data) {
    if (this.finished) throw new Error('SHA-256 instance already finalized');
    var input = data instanceof Uint8Array ? data : new Uint8Array(data);
    var offset = 0;
    this.bytesHashed += input.length;
    while (offset < input.length) {
      var take = Math.min(64 - this.bufferLength, input.length - offset);
      this.buffer.set(input.subarray(offset, offset + take), this.bufferLength);
      this.bufferLength += take;
      offset += take;
      if (this.bufferLength === 64) {
        this._process(this.buffer);
        this.bufferLength = 0;
      }
    }
    return this;
  };

  Sha256.prototype._process = function (chunk) {
    var i;
    for (i = 0; i < 16; i++) {
      var j = i * 4;
      this.w[i] = (((chunk[j] << 24) | (chunk[j + 1] << 16) | (chunk[j + 2] << 8) | chunk[j + 3]) >>> 0);
    }
    for (i = 16; i < 64; i++) {
      var x = this.w[i - 15];
      var y = this.w[i - 2];
      var s0 = rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3);
      var s1 = rotr(y, 17) ^ rotr(y, 19) ^ (y >>> 10);
      this.w[i] = (this.w[i - 16] + s0 + this.w[i - 7] + s1) >>> 0;
    }
    var a=this.h[0], b=this.h[1], c=this.h[2], d=this.h[3], e=this.h[4], f=this.h[5], g=this.h[6], h=this.h[7];
    for (i = 0; i < 64; i++) {
      var S1 = rotr(e,6) ^ rotr(e,11) ^ rotr(e,25);
      var ch = (e & f) ^ (~e & g);
      var temp1 = (h + S1 + ch + K[i] + this.w[i]) >>> 0;
      var S0 = rotr(a,2) ^ rotr(a,13) ^ rotr(a,22);
      var maj = (a & b) ^ (a & c) ^ (b & c);
      var temp2 = (S0 + maj) >>> 0;
      h=g; g=f; f=e; e=(d + temp1) >>> 0; d=c; c=b; b=a; a=(temp1 + temp2) >>> 0;
    }
    this.h[0]=(this.h[0]+a)>>>0; this.h[1]=(this.h[1]+b)>>>0; this.h[2]=(this.h[2]+c)>>>0; this.h[3]=(this.h[3]+d)>>>0;
    this.h[4]=(this.h[4]+e)>>>0; this.h[5]=(this.h[5]+f)>>>0; this.h[6]=(this.h[6]+g)>>>0; this.h[7]=(this.h[7]+h)>>>0;
  };

  Sha256.prototype.hex = function () {
    if (!this.finished) {
      var bitLengthHi = Math.floor((this.bytesHashed * 8) / 0x100000000);
      var bitLengthLo = (this.bytesHashed * 8) >>> 0;
      this.buffer[this.bufferLength++] = 0x80;
      while (this.bufferLength !== 56) {
        if (this.bufferLength === 64) { this._process(this.buffer); this.bufferLength = 0; }
        this.buffer[this.bufferLength++] = 0;
      }
      this.buffer[56]=(bitLengthHi>>>24)&255; this.buffer[57]=(bitLengthHi>>>16)&255; this.buffer[58]=(bitLengthHi>>>8)&255; this.buffer[59]=bitLengthHi&255;
      this.buffer[60]=(bitLengthLo>>>24)&255; this.buffer[61]=(bitLengthLo>>>16)&255; this.buffer[62]=(bitLengthLo>>>8)&255; this.buffer[63]=bitLengthLo&255;
      this._process(this.buffer);
      this.bufferLength = 0;
      this.finished = true;
    }
    var out = '';
    for (var i=0;i<8;i++) out += ('00000000' + this.h[i].toString(16)).slice(-8);
    return out;
  };

  function csrfToken() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? (meta.getAttribute('content') || '') : '';
  }

  function parseJsonResponse(response) {
    var contentType = response.headers.get('content-type') || '';
    if (response.redirected || contentType.indexOf('application/json') === -1) {
      var redirectError = new Error(response.redirected ? 'Your administrator session has expired. Sign in again and reopen Transfer Center.' : 'The transfer server returned an unexpected response.');
      redirectError.status = response.status;
      throw redirectError;
    }
    return response.json();
  }

  function post(url, formData) {
    var options = {
      method:'POST',
      credentials:'same-origin',
      headers:{'X-CSRFToken':csrfToken(), 'X-Requested-With':'XMLHttpRequest'},
      cache:'no-store'
    };
    if (formData !== undefined && formData !== null) options.body = formData;
    return fetch(url, options)
      .then(function (r) {
        return parseJsonResponse(r).then(function(data){
          if(!r.ok) { var err = new Error(data.error || ('Request failed ('+r.status+')')); err.status = r.status; err.data = data; throw err; }
          return data;
        });
      });
  }

  function postNoBody(url) {
    return post(url, null);
  }

  function getJson(url) {
    return fetch(url, { method:'GET', credentials:'same-origin', headers:{'X-Requested-With':'XMLHttpRequest', 'Accept':'application/json'}, cache:'no-store' })
      .then(function (r) {
        return parseJsonResponse(r).then(function(data){
          if(!r.ok) { var err = new Error(data.error || ('Request failed ('+r.status+')')); err.status = r.status; err.data = data; throw err; }
          return data;
        });
      });
  }

  function postBinary(url) {
    return fetch(url, { method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrfToken(), 'X-Requested-With':'XMLHttpRequest', 'Accept':'application/octet-stream'}, cache:'no-store' })
      .then(function (r) {
        if (!r.ok) {
          return r.json().catch(function(){return {};}).then(function(data){
            var err = new Error(data.error || ('Request failed ('+r.status+')'));
            err.status = r.status;
            err.data = data;
            throw err;
          });
        }
        var contentType = r.headers.get('content-type') || '';
        if (r.redirected || contentType.indexOf('application/octet-stream') === -1) {
          var err = new Error(r.redirected ? 'Your administrator session has expired. Sign in again and reopen Transfer Center.' : 'The transfer server returned an unexpected response.');
          err.status = r.status;
          throw err;
        }
        return r.arrayBuffer();
      });
  }

  function setFeedback(el, message, state) { if (!el) return; el.hidden=false; el.dataset.state=state || 'ok'; el.textContent=message; }
  function formatSpeed(bytes, ms) { if (!bytes || !ms) return ''; return (bytes / (ms / 1000) / 1024 / 1024).toFixed(1) + ' MB/s'; }
  function clearLegacyResumeState() {
    try {
      for (var i = window.localStorage.length - 1; i >= 0; i -= 1) {
        var key = window.localStorage.key(i) || '';
        if (key.indexOf('paxalia-transfer:v') === 0) window.localStorage.removeItem(key);
      }
    } catch (_) {}
  }

  function removeResumeStateForTransfer(transferId) {
    if (!transferId) return;
    try {
      for (var i = window.localStorage.length - 1; i >= 0; i -= 1) {
        var key = window.localStorage.key(i) || '';
        if (key.indexOf('paxalia-transfer:resume:') !== 0) continue;
        if (window.localStorage.getItem(key) === String(transferId)) {
          window.localStorage.removeItem(key);
        }
      }
    } catch (_) {}
  }

  function resumeStorageKey(file) {
    var encoder = window.TextEncoder ? new TextEncoder() : null;
    var source = [file.name, file.size, file.lastModified || 0].join('|');
    var bytes;
    if (encoder) {
      bytes = encoder.encode(source);
    } else {
      bytes = new Uint8Array(source.length);
      for (var i = 0; i < source.length; i += 1) bytes[i] = source.charCodeAt(i) & 255;
    }
    var digest = new Sha256().update(bytes).hex();
    return 'paxalia-transfer:resume:' + digest;
  }

  function transferFailureFromResult(result) {
    var transfer = result && result.transfer ? result.transfer : null;
    if (!transfer || transfer.status !== 'failed') return null;
    var message = String(transfer.error_message || 'Transfer finalization failed on the server.');
    var err = new Error(message);
    err.transferId = transfer.id || '';
    if (transfer.error_code) err.transferErrorCode = String(transfer.error_code).slice(0, 80);
    else if (/already exists/i.test(message)) err.transferErrorCode = 'destination_exists';
    else if (/checksum/i.test(message)) err.transferErrorCode = 'verification_failed';
    else err.transferErrorCode = 'finalization_failed';
    err.status = 409;
    err.data = result;
    return err;
  }
  function retryableError(err) {
    var status = Number(err && err.status);
    if (!status) return true;
    return status === 408 || status === 425 || status === 429 || (status >= 500 && status <= 599);
  }

  function retry(fn, retriesLeft, delay, retryIndex) {
    var attemptIndex = Number(retryIndex || 0);
    return fn().catch(function (err) {
      if (retriesLeft <= 0 || !retryableError(err)) throw err;
      var waitMs = delay * Math.pow(2, Math.min(attemptIndex, 8));
      return new Promise(function(resolve){setTimeout(resolve, waitMs);}).then(function(){
        return retry(fn, retriesLeft - 1, delay, attemptIndex + 1);
      });
    });
  }

  function handleSendVerificationState(info, feedback) {
    var transfer = info && info.transfer ? info.transfer : null;
    if (!transfer) return Promise.reject(new Error('The transfer finalization response is incomplete.'));
    if (transfer.status === 'completed') return Promise.resolve(transfer);
    if (transfer.status === 'failed') {
      return Promise.reject(transferFailureFromResult(info) || new Error(transfer.error_message || 'Transfer verification failed.'));
    }
    if (transfer.status !== 'verifying') {
      return Promise.reject(new Error('The transfer server did not enter a valid verification state.'));
    }

    // Large-file verification is server-owned background work. Do not block the
    // browser on an arbitrary poll count: Active Transfers is already the
    // read-only live state channel and will show the terminal result.
    upsertActiveTransfer(transfer);
    setFeedback(
      feedback,
      'Upload complete. Server SHA-256 verification is running in the background; Active transfers will update automatically.',
      'ok'
    );
    return Promise.resolve(transfer);
  }

  function uploadSendFile(file, info, feedback, chunkSize, storageKey) {
    var root = document.querySelector('[data-transfer-center]');
    var transfer = info.transfer || {};
    var transferId = transfer.id || '';
    var total = Number(transfer.total_chunks);
    var actualChunk = Number(transfer.chunk_size || chunkSize);
    var startChunk = Number(info.resume_chunk_index || 0);
    var uploadId = info.upload_id;
    if (!uploadId || !info.upload_chunk_url || !info.upload_complete_url || !info.finalize_url) {
      throw new Error('The server returned an incomplete transfer upload session.');
    }
    if (file.name !== transfer.filename || file.size !== Number(transfer.size)) {
      throw new Error('Select the original file with the same filename and size to resume this transfer.');
    }
    if (file.size <= 0) throw new Error('The selected file is empty.');

    var hasher = new Sha256();
    var started = performance.now();
    var retryDelay = Number(root.dataset.retryDelayMs || 1000);
    var retryBudget = Math.max(0, Number(transfer.max_retries || 5));

    function primeHash(targetChunkCount) {
      function next(i) {
        if (i >= targetChunkCount) return Promise.resolve();
        var blob = file.slice(i * actualChunk, Math.min((i + 1) * actualChunk, file.size));
        return blob.arrayBuffer().then(function(buf){
          hasher.update(new Uint8Array(buf));
          return next(i + 1);
        });
      }
      return next(0);
    }

    function completeUpload() {
      return postNoBody(info.upload_complete_url).then(function(uploadResult){
        var uploadState = uploadResult && uploadResult.upload ? uploadResult.upload.status : '';
        if (uploadState && uploadState !== 'completed') {
          throw new Error('The upload engine did not report a completed staging session.');
        }
        var finalize = new FormData();
        finalize.append('source_checksum', hasher.hex());
        return post(info.finalize_url, finalize)
          .then(function(result){
              var failure = transferFailureFromResult(result);
            if (!result.transfer) {
              var incomplete = new Error('The transfer finalization response is incomplete.');
              incomplete.transferId = transferId;
              throw incomplete;
            }
            upsertActiveTransfer(result.transfer);
            if (result.transfer.status === 'verifying' || result.transfer.status === 'completed' || result.transfer.status === 'failed') {
              if (storageKey) {
                try { window.localStorage.removeItem(storageKey); } catch (_) {}
              }
              removeResumeStateForTransfer(transferId);
            }
            if (failure) {
              throw failure;
            }
            return handleSendVerificationState(result, feedback);
          });
      });
    }

    function next(i) {
      if (i >= total) return completeUpload();
      var start = i * actualChunk;
      var end = Math.min(start + actualChunk, file.size);
      var blob = file.slice(start, end);
      return blob.arrayBuffer().then(function(buf){
        var bytes = new Uint8Array(buf);
        return retry(function(){
          var form = new FormData();
          form.append('chunk_index', String(i));
          form.append('chunk', blob, file.name + '.part');
          return post(info.upload_chunk_url, form);
        }, retryBudget, retryDelay, 0).then(function(result){
          hasher.update(bytes);
          var received = Number(result.bytes_received || end);
          updateActiveTransferProgress(transferId, received, file.size, 'transferring');
          setFeedback(
            feedback,
            'Uploading ' + Math.round((received / file.size) * 100) + '%' +
              (formatSpeed(received, performance.now() - started) ? ' · ' + formatSpeed(received, performance.now() - started) : ''),
            'ok'
          );
          return next(i + 1);
        });
      });
    }

    return primeHash(startChunk).then(function(){ return next(startChunk); }).then(function(result){
      if (storageKey) {
        try { window.localStorage.removeItem(storageKey); } catch (_) {}
      }
      return result;
    }).catch(function(err){
      if (!err.transferId) err.transferId = transferId;
      throw err;
    });
  }

  function sendFile(file, feedback, chunkSize, maxSize) {
    if (!file) throw new Error('Choose a file first.');
    if (file.size <= 0 || file.size > maxSize) throw new Error('The selected file exceeds the configured transfer limit.');
    var root = document.querySelector('[data-transfer-center]');
    var storageKey = resumeStorageKey(file);
    var savedId = null;
    try { savedId = window.localStorage.getItem(storageKey); } catch (_) {}

    function initNew() {
      var init = new FormData();
      init.append('filename', file.name);
      init.append('total_size', String(file.size));
      return post(root.dataset.sendInitUrl, init).then(function(info){
        if (info && info.transfer) upsertActiveTransfer(info.transfer);
        return info;
      });
    }

    function initTransfer() {
      if (!savedId) return initNew();
      var resume = new FormData();
      resume.append('transfer_id', savedId);
      return post(root.dataset.sendResumeUrl, resume).then(function(info){
        if (info && info.transfer) upsertActiveTransfer(info.transfer);
        return info;
      }).catch(function(err){
        if (!err || err.status !== 404) throw err;
        try { window.localStorage.removeItem(storageKey); } catch (_) {}
        savedId = null;
        return initNew();
      });
    }

    return initTransfer().then(function(info){
      if (!info || !info.transfer || !info.transfer.id) throw new Error('The transfer initialization response is incomplete.');
      try { window.localStorage.setItem(storageKey, info.transfer.id); } catch (_) {}
      return uploadSendFile(file, info, feedback, chunkSize, storageKey).then(function(transfer){
        return {transfer: transfer};
      });
    }).catch(function(err){
      var errorCode = err && (err.transferErrorCode || (err.data && err.data.error_code));
      if (errorCode === 'destination_exists' || errorCode === 'verification_failed') {
        try { window.localStorage.removeItem(storageKey); } catch (_) {}
      }
      throw err;
    });
  }

  var transferTerminalStatuses = {completed: true, failed: true, cancelled: true, expired: true};

  function transferChecksumText(state) {
    if (state === 'verified') return 'Verified';
    if (state === 'mismatch') return 'Mismatch';
    if (state === 'pending') return 'Verification pending';
    return 'Not available';
  }

  function activeTransferRow(transferId) {
    var root = document.querySelector('[data-transfer-center]');
    if (!root || !transferId) return null;
    var rows = root.querySelectorAll('.transfer-row[data-transfer-id]');
    for (var i = 0; i < rows.length; i += 1) {
      if (rows[i].dataset.transferId === String(transferId)) return rows[i];
    }
    return null;
  }

  function updateActiveTransferCount() {
    var root = document.querySelector('[data-transfer-center]');
    if (!root) return;
    var list = root.querySelector('[data-active-list]');
    var badge = root.querySelector('[data-active-count]');
    var empty = root.querySelector('[data-active-empty]');
    var count = list ? list.querySelectorAll('.transfer-row[data-transfer-id]').length : 0;
    if (badge) badge.textContent = String(count) + ' active';
    if (empty) empty.hidden = count > 0;
  }

  function createActiveTransferRow(transfer) {
    var root = document.querySelector('[data-transfer-center]');
    var list = root && root.querySelector('[data-active-list]');
    if (!root || !list || !transfer || !transfer.id) return null;
    var direction = transfer.direction === 'receive' ? 'receive' : 'send';
    var template = root.querySelector('[data-transfer-row-template="' + direction + '"]');
    if (!template || !template.content || !template.content.firstElementChild) return null;
    var row = template.content.firstElementChild.cloneNode(true);
    row.dataset.transferId = String(transfer.id);
    row.dataset.transferDirection = direction;
    list.appendChild(row);
    return row;
  }

  function renderActiveTransferRow(row, transfer) {
    if (!row || !transfer) return;
    var root = document.querySelector('[data-transfer-center]');
    if (!root) return;
    var direction = transfer.direction === 'receive' ? 'receive' : 'send';
    var status = String(transfer.status || 'preparing');
    var label = String(transfer.status_label || transfer.status || 'Preparing');
    var progress = Math.max(0, Math.min(100, Number(transfer.progress_percent || 0)));
    var size = Math.max(0, Number(transfer.size || 0));
    var bytes = Math.max(0, Number(transfer.bytes_transferred || 0));
    var appHash = transfer.app_checksum || transfer.client_checksum || '';
    var serverHash = transfer.server_checksum || '';
    var checksumState = transfer.checksum_status || 'not_available';

    row.className = 'transfer-row transfer-row--' + direction;
    row.dataset.transferId = String(transfer.id);
    row.dataset.transferDirection = direction;
    var directionNode = row.querySelector('[data-transfer-direction]');
    var filenameNode = row.querySelector('[data-transfer-filename]');
    var metaNode = row.querySelector('[data-transfer-meta]');
    var statusNode = row.querySelector('[data-transfer-status]');
    var liveNode = row.querySelector('[data-transfer-live-label]');
    var bar = row.querySelector('[data-transfer-progress]');
    var value = row.querySelector('[data-transfer-progress-value]');
    var totalNode = row.querySelector('[data-transfer-progress-total]');
    var appNode = row.querySelector('[data-transfer-app-checksum]');
    var serverNode = row.querySelector('[data-transfer-server-checksum]');
    var integrityNode = row.querySelector('[data-transfer-checksum-status]');
    if (directionNode) directionNode.textContent = direction === 'receive' ? 'Inbound' : 'Outbound';
    if (filenameNode) filenameNode.textContent = String(transfer.filename || 'Unnamed file');
    if (metaNode) metaNode.textContent = size.toLocaleString() + ' bytes · ' + label;
    if (statusNode) {
      statusNode.textContent = label;
      statusNode.className = 'transfer-status transfer-status--' + status;
    }
    if (liveNode) liveNode.textContent = status === 'verifying' ? 'Server verification running' : (status === 'transferring' ? 'Live transfer' : label);
    if (bar) bar.value = progress;
    if (value) value.textContent = Math.round(progress) + '%';
    if (totalNode) totalNode.textContent = bytes.toLocaleString() + ' / ' + size.toLocaleString() + ' bytes';
    if (appNode) { appNode.textContent = appHash || '—'; appNode.title = appHash || ''; }
    if (serverNode) { serverNode.textContent = serverHash || '—'; serverNode.title = serverHash || ''; }
    if (integrityNode) {
      integrityNode.textContent = transferChecksumText(checksumState);
      integrityNode.className = 'transfer-integrity transfer-integrity--' + checksumState;
    }

    var copyButtons = row.querySelectorAll('[data-copy-hash]');
    if (copyButtons.length > 0) { copyButtons[0].hidden = !appHash; copyButtons[0].dataset.copyHash = appHash; }
    if (copyButtons.length > 1) { copyButtons[1].hidden = !serverHash; copyButtons[1].dataset.copyHash = serverHash; }

    var canControl = direction === 'send' ? root.dataset.canSend === '1' : root.dataset.canReceive === '1';
    var pause = row.querySelector('[data-pause-transfer]');
    var cancel = row.querySelector('[data-cancel-transfer]');
    var resume = row.querySelector('[data-resume-transfer]');
    var retryButton = row.querySelector('[data-retry-transfer]');
    if (pause) {
      pause.dataset.pauseTransfer = String(transfer.id);
      pause.hidden = !canControl || transferTerminalStatuses[status] || status === 'paused' || status === 'interrupted' || status === 'verifying';
    }
    if (cancel) {
      cancel.dataset.cancelTransfer = String(transfer.id);
      cancel.hidden = !canControl || !!transferTerminalStatuses[status] || status === 'verifying';
    }
    if (resume) {
      resume.dataset.resumeTransfer = String(transfer.id);
      resume.dataset.resumeDirection = direction;
      resume.hidden = !canControl || status !== 'paused';
    }
    if (retryButton) {
      retryButton.dataset.retryTransfer = String(transfer.id);
      retryButton.dataset.retryDirection = direction;
      retryButton.hidden = !canControl || status !== 'interrupted';
    }
  }

  function upsertActiveTransfer(transfer) {
    if (!transfer || !transfer.id) return;
    var row = activeTransferRow(transfer.id);
    if (transferTerminalStatuses[transfer.status]) {
      if (row) row.remove();
      updateActiveTransferCount();
      return;
    }
    if (!row) row = createActiveTransferRow(transfer);
    if (!row) return;
    renderActiveTransferRow(row, transfer);
    updateActiveTransferCount();
  }

  function updateActiveTransferProgress(transferId, bytes, total, status) {
    var row = activeTransferRow(transferId);
    if (!row) return;
    var totalNumber = Math.max(0, Number(total || 0));
    var bytesNumber = Math.max(0, Number(bytes || 0));
    var progress = totalNumber ? Math.max(0, Math.min(100, bytesNumber / totalNumber * 100)) : 0;
    var bar = row.querySelector('[data-transfer-progress]');
    var value = row.querySelector('[data-transfer-progress-value]');
    var statusNode = row.querySelector('[data-transfer-status]');
    var liveNode = row.querySelector('[data-transfer-live-label]');
    var totalNode = row.querySelector('[data-transfer-progress-total]');
    if (bar) bar.value = progress;
    if (value) value.textContent = Math.round(progress) + '%';
    if (statusNode) { statusNode.textContent = status === 'transferring' ? 'Transferring' : String(status || 'Transferring'); statusNode.className = 'transfer-status transfer-status--' + (status || 'transferring'); }
    if (liveNode) liveNode.textContent = 'Live transfer';
    if (totalNode) totalNode.textContent = bytesNumber.toLocaleString() + ' / ' + totalNumber.toLocaleString() + ' bytes';
  }

  function receiveFileFromInfo(info, feedback, maxSize, browserMaxReceiveMb) {
    var t = info.transfer;
    if (!t || !info.chunk_url_template || !info.complete_url) {
      throw new Error('The server returned an incomplete receive session. Refresh Transfer Center and try again.');
    }
    if (t.size > maxSize) throw new Error('The selected server file exceeds the configured transfer limit.');
    if (t.size > browserMaxReceiveMb * 1024 * 1024) throw new Error('The selected receive is larger than the configured browser buffering limit.');
    var chunks = [], hasher = new Sha256();

    function triggerDownload() {
      var blob = new Blob(chunks, {type:'application/octet-stream'});
      chunks.length = 0;
      var url = URL.createObjectURL(blob), a = document.createElement('a');
      a.href = url;
      a.download = t.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function(){ URL.revokeObjectURL(url); }, 5000);
    }

    function waitForVerification() {
      var statusUrl = document.querySelector('[data-transfer-center]').dataset.statusBase
        .replace('00000000-0000-0000-0000-000000000000', t.id);
      function poll() {
        return getJson(statusUrl)
          .then(function(data){
            var current = data && data.transfer;
            if (!current) throw new Error('Transfer verification status is unavailable.');
            if (current.status === 'completed') {
              return current;
            }
            if (current.status === 'failed') {
              throw new Error('Receive failed integrity verification: the app and server SHA-256 values do not match.');
            }
            setFeedback(feedback, 'Download complete. Server SHA-256 verification is running; the download remains locked until verification completes.', 'ok');
            return new Promise(function(resolve){ setTimeout(function(){ resolve(poll()); }, 2000); });
          });
      }
      return poll();
    }

    function completeDownload() {
      var browserChecksum = hasher.hex();
      var complete = new FormData();
      complete.append('destination_checksum', browserChecksum);
      return post(info.complete_url, complete).then(function(result){
        if (result && result.transfer) upsertActiveTransfer(result.transfer);
        var status = result.transfer && result.transfer.status;
        if (status === 'failed') throw new Error('Receive failed integrity verification: the app and server SHA-256 values do not match.');
        // The server is the authority for completion. Even when the POST response
        // already says completed, route through the same verification gate so the
        // browser download can never become the source of truth for completion.
        return waitForVerification().then(function(){
          triggerDownload();
          setFeedback(feedback, 'Receive complete. App and server SHA-256 values match.', 'ok');
          return result;
        }).catch(function(err){
          throw err;
        });
      });
    }

    function next(i) {
      if (i >= t.total_chunks) return completeDownload();
      var url = info.chunk_url_template.replace('CHUNK_INDEX', String(i));
      return retry(function(){
        return postBinary(url);
      }, Math.max(0, Number(t.max_retries || 5)), Number(document.querySelector('[data-transfer-center]').dataset.retryDelayMs || 1000), 0).then(function(buf){
        var bytes = new Uint8Array(buf);
        hasher.update(bytes);
        chunks.push(buf);
        updateActiveTransferProgress(t.id, Math.min(t.size, (i + 1) * t.chunk_size), t.size, 'transferring');
        setFeedback(feedback, 'Receiving ' + Math.round(((i + 1) / t.total_chunks) * 100) + '%', 'ok');
        return next(i + 1);
      });
    }

    // The browser deliberately starts from chunk zero after a page reload:
    // received_chunks is server-side delivery state, not durable browser data.
    // Re-reading earlier chunks guarantees the reconstructed file/hash is complete.
    return next(0);
  }

  function receiveFile(filename, feedback, maxSize, browserMaxReceiveMb) {
    var form = new FormData();
    form.append('filename', filename);
    var root = document.querySelector('[data-transfer-center]');
    return root.dataset.receiveInitUrl
      ? post(root.dataset.receiveInitUrl, form).then(function(info){
           if (info && info.transfer) upsertActiveTransfer(info.transfer);
           return receiveFileFromInfo(info, feedback, maxSize, browserMaxReceiveMb);
         })
      : Promise.reject(new Error('The transfer receive endpoint is unavailable.'));
  }

  function chooseResumeFile() {
    return new Promise(function(resolve, reject){
      var input = document.createElement('input');
      input.type = 'file';
      input.style.position = 'fixed';
      input.style.left = '-10000px';
      input.style.opacity = '0';
      input.addEventListener('change', function(){
        var file = input.files && input.files[0];
        input.remove();
        if (file) resolve(file); else reject(new Error('Choose the original transfer file to continue.'));
      }, {once:true});
      document.body.appendChild(input);
      input.click();
    });
  }

  function resumeSendFromBrowser(transferId, feedback, chunkSize, maxSize) {
    return chooseResumeFile().then(function(file){
      if (file.size <= 0 || file.size > maxSize) throw new Error('The selected file exceeds the configured transfer limit.');
      var fd = new FormData();
      fd.append('transfer_id', transferId);
      return post(document.querySelector('[data-transfer-center]').dataset.sendResumeUrl, fd).then(function(info){
        return uploadSendFile(file, info, feedback, chunkSize, null).then(function(result){
          var transfer = result && result.transfer ? result.transfer : result;
          if (transfer && (transfer.status === 'verifying' || transfer.status === 'completed' || transfer.status === 'failed')) {
            removeResumeStateForTransfer(transferId);
          }
          return result;
        });
      });
    });
  }

  function resumeReceiveFromServer(transferId, feedback, maxSize, browserMaxReceiveMb) {
    var fd = new FormData();
    fd.append('transfer_id', transferId);
    return post(document.querySelector('[data-transfer-center]').dataset.receiveResumeUrl, fd)
      .then(function(info){
        if (info && info.transfer) upsertActiveTransfer(info.transfer);
        return receiveFileFromInfo(info, feedback, maxSize, browserMaxReceiveMb);
      });
  }

  function copiedHashFallback(value, done) {
    var area = document.createElement('textarea');
    area.value = value; area.setAttribute('readonly', ''); area.style.position = 'fixed'; area.style.opacity = '0';
    document.body.appendChild(area); area.select();
    try { document.execCommand('copy'); done(); } finally { area.remove(); }
  }

  function boot() {
    var root = document.querySelector('[data-transfer-center]');
    if (!root) return;
    clearLegacyResumeState();

    var sendForm = document.querySelector('[data-send-form]');
    var receiveForm = document.querySelector('[data-receive-form]');
    var sendFeedback = document.querySelector('[data-send-feedback]');
    var receiveFeedback = document.querySelector('[data-receive-feedback]');
    var chunkSize = Number(root.dataset.chunkSize) || 5242880;
    var maxSize = Number(root.dataset.maxSize) || 2147483648;
    var browserMaxReceiveMb = Number(root.dataset.browserMaxReceiveMb) || 512;

    function withBusy(button, promise) {
      if (button) {
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
      }
      return promise.finally(function () {
        if (button) {
          button.disabled = false;
          button.removeAttribute('aria-busy');
        }
      });
    }

    if (sendForm) {
      var sendFileInput = sendForm.querySelector('[data-send-file]');
      var sendFileName = sendForm.querySelector('[data-send-file-name]');
      if (sendFileInput) {
        sendFileInput.addEventListener('change', function () {
          var selected = sendFileInput.files && sendFileInput.files[0] ? sendFileInput.files[0] : null;
          if (!sendFileName) return;
          if (!selected) {
            sendFileName.textContent = 'Select one file to begin.';
            return;
          }
          var sizeMb = selected.size / (1024 * 1024);
          sendFileName.textContent = selected.name + ' · ' + (
            sizeMb >= 1 ? sizeMb.toFixed(sizeMb >= 100 ? 0 : 1) + ' MB' : Math.max(1, Math.round(selected.size / 1024)) + ' KB'
          );
        });
      }

      sendForm.addEventListener('submit', function (event) {
        event.preventDefault();
        sendFeedback.hidden = true;
        var submitButton = sendForm.querySelector('button[type="submit"]');
        var fileInput = sendForm.querySelector('[data-send-file]');
        var file = fileInput && fileInput.files ? fileInput.files[0] : null;
        try {
          withBusy(submitButton, sendFile(file, sendFeedback, chunkSize, maxSize))
            .then(function(info){
              var transfer = info && info.transfer ? info.transfer : null;
              if (!transfer) {
                throw new Error('The transfer completed without a valid server response.');
              }
              if (transfer.status === 'failed') {
                setFeedback(
                  sendFeedback,
                  transfer.error_message || 'Transfer failed during server-side finalization.',
                  'error'
                );
                return;
              }
              setFeedback(
                sendFeedback,
                transfer.status === 'completed'
                  ? 'Transfer completed and verified successfully.'
                  : transfer.status === 'verifying'
                    ? 'Upload complete. Server SHA-256 verification is running in the background; Active transfers will update automatically.'
                    : 'Transfer is still being processed by the server.',
                'ok'
              );
            })
            .catch(function(err){
              setFeedback(sendFeedback, err.message, 'error');
            });
        } catch(err) {
          setFeedback(sendFeedback, err.message, 'error');
        }
      });
    }

    if (receiveForm) {
      var selectionName = receiveForm.querySelector('[data-receive-selection-name]');
      var submitButton = receiveForm.querySelector('[data-receive-submit]');
      var choices = receiveForm.querySelectorAll('[data-receive-file]');

      choices.forEach(function(choice){
        choice.addEventListener('change', function(){
          var checked = receiveForm.querySelector('[data-receive-file]:checked');
          if(selectionName) selectionName.textContent = checked ? checked.value : 'Nothing selected';
          if(submitButton) submitButton.disabled = !checked;
        });
      });

      receiveForm.addEventListener('submit',function(event){
        event.preventDefault();
        receiveFeedback.hidden = true;
        var checked = receiveForm.querySelector('[data-receive-file]:checked');
        if(!checked) {
          setFeedback(receiveFeedback, 'Choose a file from the transfer exchange first.', 'error');
          return;
        }
        withBusy(submitButton, receiveFile(checked.value, receiveFeedback, maxSize, browserMaxReceiveMb))
          .then(function(){
            setFeedback(receiveFeedback, 'Receive complete. App and server SHA-256 values match.', 'ok');
          })
          .catch(function(err){ setFeedback(receiveFeedback, err.message, 'error'); });
      });
    }

    var refreshExchange = document.querySelector('[data-refresh-exchange]');
    if(refreshExchange) refreshExchange.addEventListener('click',function(){ refreshExchange.disabled = true; window.location.reload(); });

    var activePollInFlight = false;

    function refreshActiveTransfers() {
      if (!root.dataset.statusBase || document.hidden || activePollInFlight) {
        updateActiveTransferCount();
        return;
      }
      var rows = Array.prototype.slice.call(root.querySelectorAll('.transfer-row[data-transfer-id]'));
      updateActiveTransferCount();
      if (!rows.length) return;
      activePollInFlight = true;
      Promise.all(rows.map(function(row){
        var id = row.dataset.transferId;
        var url = root.dataset.statusBase.replace('00000000-0000-0000-0000-000000000000', id);
        return getJson(url).then(function(data){
          var t = data && data.transfer;
          if (!t) throw new Error('Transfer status response is unavailable.');
          upsertActiveTransfer(t);
          if (t.status === 'failed') {
            setFeedback(t.direction === 'receive' ? receiveFeedback : sendFeedback, t.error_message || 'The transfer failed.', 'error');
          } else if (t.status === 'completed' && t.direction === 'send') {
            setFeedback(sendFeedback, 'Transfer completed and verified successfully.', 'ok');
          }
          return t;
        }).catch(function(err){
          var current = activeTransferRow(id);
          if (current && err && /session has expired/i.test(err.message || '')) {
            var statusNode = current.querySelector('[data-transfer-status]');
            if (statusNode) {
              statusNode.textContent = 'Session expired';
              statusNode.className = 'transfer-status transfer-status--failed';
            }
          }
          return null;
        });
      })).finally(function(){
        activePollInFlight = false;
        updateActiveTransferCount();
      });
    }

    refreshActiveTransfers();
    window.setInterval(refreshActiveTransfers, 2000);

    function continueTransfer(transferId, direction, feedback) {
      if (direction === 'receive') return resumeReceiveFromServer(transferId, feedback, maxSize, browserMaxReceiveMb);
      return resumeSendFromBrowser(transferId, feedback, chunkSize, maxSize);
    }

    var activeList = root.querySelector('[data-active-list]');
    if (activeList) activeList.addEventListener('click', function(event){
      var node = event.target;
      var button = null;
      while (node && node !== activeList) {
        if (node.nodeType === 1 && node.tagName === 'BUTTON' && (
          node.dataset.cancelTransfer !== undefined ||
          node.dataset.pauseTransfer !== undefined ||
          node.dataset.retryTransfer !== undefined ||
          node.dataset.resumeTransfer !== undefined ||
          node.dataset.copyHash !== undefined
        )) {
          button = node;
          break;
        }
        node = node.parentNode;
      }
      if (!button) return;

      if (button.dataset.copyHash !== undefined) {
        var value = button.dataset.copyHash || '';
        function copied(){
          var old = button.textContent;
          button.textContent = 'Copied';
          window.setTimeout(function(){ button.textContent = old; }, 1200);
        }
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(value).then(copied).catch(function(){ copiedHashFallback(value, copied); });
        } else {
          copiedHashFallback(value, copied);
        }
        return;
      }

      var id = button.dataset.cancelTransfer || button.dataset.pauseTransfer || button.dataset.retryTransfer || button.dataset.resumeTransfer;
      if (!id) return;
      if (button.dataset.cancelTransfer !== undefined) {
        if (!window.confirm('Cancel this transfer?')) return;
        button.disabled = true;
        withBusy(button, postNoBody((root.dataset.cancelBase || '').replace('TRANSFER_ID', id)))
          .then(function(result){ if (result && result.transfer) upsertActiveTransfer(result.transfer); })
          .catch(function(err){ button.disabled = false; setFeedback(sendFeedback, err.message, 'error'); });
        return;
      }
      if (button.dataset.pauseTransfer !== undefined) {
        button.disabled = true;
        withBusy(button, postNoBody((root.dataset.pauseBase || '').replace('TRANSFER_ID', id)))
          .then(function(result){ if (result && result.transfer) upsertActiveTransfer(result.transfer); })
          .catch(function(err){ button.disabled = false; setFeedback(sendFeedback, err.message, 'error'); });
        return;
      }

      var direction = button.dataset.retryDirection || button.dataset.resumeDirection || 'send';
      var feedback = direction === 'receive' ? receiveFeedback : sendFeedback;
      if (button.dataset.retryTransfer !== undefined) {
        setFeedback(feedback, 'Preparing transfer retry…', 'ok');
        withBusy(button, postNoBody((root.dataset.retryBase || '').replace('TRANSFER_ID', id))
          .then(function(info){
            if (info && info.transfer) upsertActiveTransfer(info.transfer);
            return continueTransfer(id, direction, feedback).then(function(result){ return result || info; });
          }))
          .then(function(result){
            if (result && result.transfer) {
              upsertActiveTransfer(result.transfer);
              if (result.transfer.status === 'verifying' && result.transfer.direction === 'send') {
                setFeedback(feedback, 'Upload complete. Server SHA-256 verification is running in the background; Active transfers will update automatically.', 'ok');
              } else if (result.transfer.status === 'completed') {
                setFeedback(feedback, 'Transfer completed and verified successfully.', 'ok');
              } else {
                setFeedback(feedback, 'Transfer resumed successfully.', 'ok');
              }
            }
          })
          .catch(function(err){ setFeedback(feedback, err.message, 'error'); });
        return;
      }

      setFeedback(feedback, 'Preparing transfer resume…', 'ok');
      withBusy(button, continueTransfer(id, direction, feedback))
        .then(function(result){
          if (result && result.transfer) {
            upsertActiveTransfer(result.transfer);
            if (result.transfer.status === 'verifying' && result.transfer.direction === 'send') {
              setFeedback(feedback, 'Upload complete. Server SHA-256 verification is running in the background; Active transfers will update automatically.', 'ok');
            } else if (result.transfer.status === 'completed') {
              setFeedback(feedback, 'Transfer completed and verified successfully.', 'ok');
            } else {
              setFeedback(feedback, 'Transfer resumed successfully.', 'ok');
            }
          }
        })
        .catch(function(err){ setFeedback(feedback, err.message, 'error'); });
    });

  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();

