/**
 * Social Media Video Downloader — Frontend Logic
 * Handles platform selection, video info fetching, download management,
 * progress tracking via SSE, and download history.
 */

// ──────────────────────────────────────────────
// State
// ──────────────────────────────────────────────

const state = {
  platform: 'youtube',
  videoInfo: null,
  downloading: false,
  history: JSON.parse(localStorage.getItem('dl_history') || '[]'),
};

const PLATFORMS = {
  youtube:   { name: 'YouTube',   icon: '▶', patterns: ['youtube.com', 'youtu.be'] },
  tiktok:    { name: 'TikTok',    icon: '♪', patterns: ['tiktok.com', 'vm.tiktok.com'] },
  facebook:  { name: 'Facebook',  icon: 'f', patterns: ['facebook.com', 'fb.watch', 'fb.com'] },
  pinterest: { name: 'Pinterest', icon: 'P', patterns: ['pinterest.com', 'pin.it'] },
};

// ──────────────────────────────────────────────
// DOM Elements
// ──────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
  platformBtns:     $$('.platform-btn'),
  urlInput:         $('#url-input'),
  btnPaste:         $('#btn-paste'),
  btnFetch:         $('#btn-fetch'),
  preview:          $('#preview'),
  previewThumb:     $('#preview-thumb'),
  previewTitle:     $('#preview-title'),
  previewMeta:      $('#preview-meta'),
  previewPlatform:  $('#preview-platform'),
  resolutionGroup:  $('#resolution-group'),
  resolutionSelect: $('#resolution-select'),
  audioGroup:       $('#audio-group'),
  audioSelect:      $('#audio-select'),
  tiktokNotice:     $('#tiktok-notice'),
  btnDownload:      $('#btn-download'),
  btnDownloadText:  $('#btn-download-text'),
  btnDownloadSpin:  $('#btn-download-spinner'),
  progressSection:  $('#progress-section'),
  progressTitle:    $('#progress-title'),
  progressPercent:  $('#progress-percent'),
  progressFill:     $('#progress-fill'),
  progressSpeed:    $('#progress-speed'),
  progressEta:      $('#progress-eta'),
  statusMessage:    $('#status-message'),
  statusText:       $('#status-text'),
  historyList:      $('#history-list'),
  historyCount:     $('#history-count'),
};

// ──────────────────────────────────────────────
// Platform Detection
// ──────────────────────────────────────────────

function detectPlatform(url) {
  const lower = url.toLowerCase();
  for (const [key, info] of Object.entries(PLATFORMS)) {
    if (info.patterns.some(p => lower.includes(p))) {
      return key;
    }
  }
  return null;
}

function selectPlatform(platform) {
  state.platform = platform;

  dom.platformBtns.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.platform === platform);
  });

  // Show/hide options based on platform
  const isTikTok = platform === 'tiktok';
  dom.resolutionGroup.style.display = isTikTok ? 'none' : '';
  dom.audioGroup.style.display = isTikTok ? 'none' : '';
  dom.tiktokNotice.classList.toggle('visible', isTikTok);
}

// ──────────────────────────────────────────────
// Video Info
// ──────────────────────────────────────────────

async function fetchVideoInfo() {
  const url = dom.urlInput.value.trim();
  if (!url) return;

  // Auto-detect platform
  const detected = detectPlatform(url);
  if (detected) {
    selectPlatform(detected);
  }

  dom.preview.classList.remove('visible');
  dom.btnDownload.disabled = true;
  dom.btnDownloadText.textContent = 'Obteniendo información...';
  dom.btnDownload.classList.add('loading');

  try {
    const res = await fetch('/api/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    const data = await res.json();

    if (!res.ok) {
      showStatus('error', data.error || 'Error al obtener información');
      dom.btnDownloadText.textContent = 'DESCARGAR VIDEO';
      dom.btnDownload.classList.remove('loading');
      dom.btnDownload.disabled = false;
      return;
    }

    state.videoInfo = data;

    // Update preview
    dom.previewThumb.src = data.thumbnail || '';
    dom.previewThumb.style.display = data.thumbnail ? '' : 'none';
    dom.previewTitle.textContent = data.title;

    const duration = data.duration ? formatDuration(data.duration) : '';
    const uploader = data.uploader || '';
    dom.previewMeta.textContent = [uploader, duration].filter(Boolean).join(' · ');

    dom.previewPlatform.textContent = PLATFORMS[data.platform]?.name || data.platform;
    dom.previewPlatform.dataset.platform = data.platform;

    dom.preview.classList.add('visible');

    // Update resolution options
    if (data.available_resolutions && data.available_resolutions.length > 0) {
      updateResolutions(data.available_resolutions);
    }

    // Auto-select platform if detected
    if (data.platform && data.platform !== 'unknown') {
      selectPlatform(data.platform);
    }

    hideStatus();

  } catch (err) {
    showStatus('error', 'Error de conexión al servidor');
  }

  dom.btnDownloadText.textContent = 'DESCARGAR VIDEO';
  dom.btnDownload.classList.remove('loading');
  dom.btnDownload.disabled = false;
}

function updateResolutions(available) {
  const labels = {
    2160: '4K (2160p)',
    1440: '1440p',
    1080: '1080p',
    720: '720p',
    480: '480p',
    360: '360p',
  };

  // Keep "Mejor disponible" and add available ones
  let options = '<option value="best">✨ Mejor disponible</option>';
  available.forEach(h => {
    const label = labels[h] || `${h}p`;
    options += `<option value="${h}">${label}</option>`;
  });

  dom.resolutionSelect.innerHTML = options;
}

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

// ──────────────────────────────────────────────
// Download
// ──────────────────────────────────────────────

async function startDownload() {
  const url = dom.urlInput.value.trim();
  if (!url || state.downloading) return;

  state.downloading = true;
  dom.btnDownload.disabled = true;
  dom.btnDownloadText.textContent = 'Iniciando descarga...';
  dom.btnDownload.classList.add('loading');
  hideStatus();

  const payload = {
    url,
    platform: state.platform,
    resolution: dom.resolutionSelect.value,
    audio_mode: dom.audioSelect.value,
  };

  try {
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      showStatus('error', data.error || 'Error al iniciar descarga');
      resetDownloadButton();
      return;
    }

    // Show progress and listen via SSE
    showProgress();
    listenProgress(data.task_id);

  } catch (err) {
    showStatus('error', 'Error de conexión al servidor');
    resetDownloadButton();
  }
}

function listenProgress(taskId) {
  const evtSource = new EventSource(`/api/progress/${taskId}`);

  evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.error && data.status !== 'downloading') {
      evtSource.close();
      showStatus('error', data.error);
      resetDownloadButton();
      return;
    }

    // Update progress UI
    const pct = data.progress || 0;
    dom.progressFill.style.width = `${pct}%`;
    dom.progressPercent.textContent = `${pct}%`;
    dom.progressTitle.textContent = data.title
      ? `Descargando: ${truncate(data.title, 40)}`
      : 'Descargando...';
    dom.progressSpeed.textContent = data.speed || '';
    dom.progressEta.textContent = data.eta ? `ETA: ${data.eta}` : '';

    if (data.status === 'processing') {
      dom.progressTitle.textContent = '⚙️ Procesando archivo...';
      dom.progressPercent.textContent = '95%';
    }

    if (data.status === 'completed') {
      evtSource.close();
      dom.progressFill.style.width = '100%';
      dom.progressPercent.textContent = '100%';
      dom.progressTitle.textContent = '✅ ¡Descarga completada!';
      dom.progressFill.style.background = 'linear-gradient(90deg, var(--success), #2ecc71)';

      // Trigger file download
      triggerFileDownload(taskId, data.title || 'video');

      // Add to history
      addHistory(data.title || 'Video', 'success');
      showStatus('success', `✅ "${truncate(data.title || 'Video', 50)}" descargado exitosamente`);

      resetDownloadButton();
    }

    if (data.status === 'error') {
      evtSource.close();
      dom.progressFill.style.width = '100%';
      dom.progressFill.style.background = 'linear-gradient(90deg, var(--error), #c0392b)';
      dom.progressPercent.textContent = '✕';
      dom.progressTitle.textContent = '❌ Error en la descarga';

      addHistory(data.title || 'Video', 'error');
      showStatus('error', data.error || 'Error desconocido');
      resetDownloadButton();
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
    // Don't show error if download already completed
    if (state.downloading) {
      showStatus('error', 'Se perdió la conexión con el servidor');
      resetDownloadButton();
    }
  };
}

function triggerFileDownload(taskId, title) {
  const a = document.createElement('a');
  a.href = `/api/file/${taskId}`;
  a.download = title;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ──────────────────────────────────────────────
// UI Helpers
// ──────────────────────────────────────────────

function showProgress() {
  dom.progressSection.classList.add('visible');
  dom.progressFill.style.width = '0%';
  dom.progressFill.style.background = '';
  dom.progressPercent.textContent = '0%';
  dom.progressTitle.textContent = 'Preparando descarga...';
  dom.progressSpeed.textContent = '';
  dom.progressEta.textContent = '';
}

function showStatus(type, message) {
  dom.statusMessage.className = `status-message visible ${type}`;
  dom.statusText.textContent = message;
}

function hideStatus() {
  dom.statusMessage.classList.remove('visible');
}

function resetDownloadButton() {
  state.downloading = false;
  dom.btnDownload.disabled = false;
  dom.btnDownloadText.textContent = 'DESCARGAR VIDEO';
  dom.btnDownload.classList.remove('loading');
}

function truncate(str, max) {
  return str.length > max ? str.slice(0, max) + '...' : str;
}

// ──────────────────────────────────────────────
// History
// ──────────────────────────────────────────────

function addHistory(title, status) {
  const item = {
    title,
    status,
    platform: state.platform,
    time: new Date().toLocaleTimeString(),
  };

  state.history.unshift(item);
  if (state.history.length > 20) state.history.pop();

  localStorage.setItem('dl_history', JSON.stringify(state.history));
  renderHistory();
}

function renderHistory() {
  if (state.history.length === 0) {
    dom.historyList.innerHTML = '<div class="history-empty">No hay descargas aún. ¡Pega una URL y comienza! 🚀</div>';
    dom.historyCount.textContent = '0 descargas';
    return;
  }

  dom.historyCount.textContent = `${state.history.length} descarga${state.history.length !== 1 ? 's' : ''}`;

  dom.historyList.innerHTML = state.history.map(item => {
    const platform = PLATFORMS[item.platform] || { icon: '?', name: 'Unknown' };
    const statusClass = item.status === 'success' ? 'success' : 'error';
    const statusLabel = item.status === 'success' ? 'Completado' : 'Error';

    return `
      <div class="history-item">
        <span class="history-item__icon" style="color: var(--${item.platform})">${platform.icon}</span>
        <div class="history-item__info">
          <div class="history-item__title">${escapeHtml(item.title)}</div>
          <div class="history-item__time">${item.time}</div>
        </div>
        <span class="history-item__status ${statusClass}">${statusLabel}</span>
      </div>
    `;
  }).join('');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ──────────────────────────────────────────────
// Event Listeners
// ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Platform buttons
  dom.platformBtns.forEach(btn => {
    btn.addEventListener('click', () => selectPlatform(btn.dataset.platform));
  });

  // Paste button
  dom.btnPaste.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      dom.urlInput.value = text.trim();
      // Auto-detect and fetch info
      const detected = detectPlatform(text);
      if (detected) selectPlatform(detected);
      fetchVideoInfo();
    } catch {
      dom.urlInput.focus();
    }
  });

  // URL input — auto-detect platform on paste/type
  dom.urlInput.addEventListener('input', () => {
    const val = dom.urlInput.value.trim();
    const detected = detectPlatform(val);
    if (detected) selectPlatform(detected);
  });

  // URL input — Enter key to fetch info
  dom.urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      fetchVideoInfo();
    }
  });

  // Fetch info button (magnifying glass)
  if (dom.btnFetch) {
    dom.btnFetch.addEventListener('click', fetchVideoInfo);
  }

  // Download button
  dom.btnDownload.addEventListener('click', () => {
    const url = dom.urlInput.value.trim();
    if (!url) {
      showStatus('error', 'Por favor, pega la URL del video que deseas descargar.');
      return;
    }

    // If we don't have video info yet, fetch first then download
    if (!state.videoInfo) {
      fetchVideoInfo().then(() => {
        if (state.videoInfo) startDownload();
      });
    } else {
      startDownload();
    }
  });

  // Initial platform selection
  selectPlatform('youtube');

  // Render history
  renderHistory();
});
