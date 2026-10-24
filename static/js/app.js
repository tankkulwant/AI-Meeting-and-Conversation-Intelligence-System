// Application State
let currentSessionId = null;
let currentTranscript = null;
let currentAnalysis = null;
let activePlayer = null;
let transcriptSegments = [];
let actionItemsList = [];
let currentActionFilter = 'all';

// DOM Elements
const dropzone = document.getElementById('dropzone');
const mediaFileInput = document.getElementById('mediaFileInput');
const browseBtn = document.getElementById('browseBtn');
const modelSelect = document.getElementById('modelSelect');
const langSelect = document.getElementById('langSelect');
const progressBanner = document.getElementById('progressBanner');
const progressStatus = document.getElementById('progressStatus');
const progressDetail = document.getElementById('progressDetail');
const progressPctBadge = document.getElementById('progressPctBadge');
const progressBarFill = document.getElementById('progressBarFill');
const progStepUpload = document.getElementById('progStepUpload');
const progStepTranscribe = document.getElementById('progStepTranscribe');
const progStepAnalyze = document.getElementById('progStepAnalyze');
const progressLiveTicker = document.getElementById('progressLiveTicker');
const tickerText = document.getElementById('tickerText');
const uploadSection = document.getElementById('uploadSection');
const workspaceSection = document.getElementById('workspaceSection');

const mediaPlayer = document.getElementById('mediaPlayer');
const audioPlayer = document.getElementById('audioPlayer');
const audioVisualizer = document.getElementById('audioVisualizer');
const transcriptList = document.getElementById('transcriptList');
const transcriptSearch = document.getElementById('transcriptSearch');
const searchCount = document.getElementById('searchCount');

// Strip & KPI Elements
const stripFileName = document.getElementById('stripFileName');
const stripLanguage = document.getElementById('stripLanguage');
const stripSentiment = document.getElementById('stripSentiment');
const kpiDuration = document.getElementById('kpiDuration');
const kpiWords = document.getElementById('kpiWords');
const kpiPace = document.getElementById('kpiPace');
const kpiActionCount = document.getElementById('kpiActionCount');
const kpiDecisionCount = document.getElementById('kpiDecisionCount');
const kpiSentimentText = document.getElementById('kpiSentimentText');

// Intelligence Tab Elements
const aiMeetingTitle = document.getElementById('aiMeetingTitle');
const aiExecutiveSummary = document.getElementById('aiExecutiveSummary');
const topicsContainer = document.getElementById('topicsContainer');
const takeawaysList = document.getElementById('takeawaysList');
const actionItemsTableBody = document.getElementById('actionItemsTableBody');
const actionItemCountBadge = document.getElementById('actionItemCountBadge');
const decisionsContainer = document.getElementById('decisionsContainer');

// Chat Elements
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendChatBtn = document.getElementById('sendChatBtn');

// Settings & Preview Modal Elements
const apiStatusBadge = document.getElementById('apiStatusBadge');
const apiStatusText = document.getElementById('apiStatusText');
const settingsModal = document.getElementById('settingsModal');
const openSettingsBtn = document.getElementById('openSettingsBtn');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const geminiApiKeyInput = document.getElementById('geminiApiKeyInput');
const geminiModelInput = document.getElementById('geminiModelInput');

const docPreviewModal = document.getElementById('docPreviewModal');
const closePreviewBtn = document.getElementById('closePreviewBtn');
const previewDocBody = document.getElementById('previewDocBody');
const copyPreviewContentBtn = document.getElementById('copyPreviewContentBtn');
const downloadFromPreviewBtn = document.getElementById('downloadFromPreviewBtn');

// ==========================================
// Initialization
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
  checkApiStatus();
  initTabNavigation();
  initDropzoneEvents();
  initPlayerEvents();
  initSpeedControls();
  initActionFilters();
  initChatEvents();
  initExportEvents();
  initSettingsModal();
  initPreviewModal();
});

async function checkApiStatus() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    if (data.has_gemini_key) {
      apiStatusBadge.className = 'status-badge status-success';
      apiStatusText.textContent = 'Gemini AI Ready';
    } else {
      apiStatusBadge.className = 'status-badge status-warning';
      apiStatusText.textContent = 'Set Gemini API Key';
    }
  } catch (err) {
    console.error('Failed to fetch settings:', err);
  }
}

function initSettingsModal() {
  openSettingsBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));
  closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
  saveSettingsBtn.addEventListener('click', async () => {
    const key = geminiApiKeyInput.value.trim();
    const model = geminiModelInput.value;
    if (key) {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gemini_api_key: key, gemini_model: model })
      });
      settingsModal.classList.add('hidden');
      checkApiStatus();
      alert('Settings updated successfully!');
    } else {
      settingsModal.classList.add('hidden');
    }
  });
}

function initPreviewModal() {
  closePreviewBtn.addEventListener('click', () => docPreviewModal.classList.add('hidden'));
  copyPreviewContentBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(previewDocBody.innerText);
    alert('Document content copied to clipboard!');
  });
  downloadFromPreviewBtn.addEventListener('click', () => {
    if (currentSessionId) window.open(`/api/export/${currentSessionId}/pdf`, '_blank');
  });
}

// ==========================================
// Tabs Navigation
// ==========================================
function initTabNavigation() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  document.getElementById('newMeetingBtn')?.addEventListener('click', () => {
    if (confirm('Start a new meeting session?')) {
      location.reload();
    }
  });

  document.getElementById('reanalyzeBtn')?.addEventListener('click', () => {
    if (currentSessionId) runAIAnalysis(currentSessionId);
  });
}

// ==========================================
// Drag & Drop Upload
// ==========================================
function initDropzoneEvents() {
  browseBtn.addEventListener('click', () => mediaFileInput.click());

  mediaFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      processSelectedFile(e.target.files[0]);
    }
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt.files && dt.files.length > 0) {
      processSelectedFile(dt.files[0]);
    }
  });
}

// ==========================================
// Processing Pipeline
// ==========================================
function setProgress({ percent, title, detail, step, ticker }) {
  if (percent !== undefined) {
    const clamped = Math.max(0, Math.min(100, Math.round(percent)));
    if (progressPctBadge) progressPctBadge.textContent = `${clamped}%`;
    if (progressBarFill) progressBarFill.style.width = `${clamped}%`;
  }
  if (title && progressStatus) progressStatus.textContent = title;
  if (detail && progressDetail) progressDetail.textContent = detail;
  if (ticker !== undefined && progressLiveTicker) {
    if (ticker) {
      progressLiveTicker.classList.remove('hidden');
      if (tickerText) tickerText.textContent = ticker;
    } else {
      progressLiveTicker.classList.add('hidden');
    }
  }
  if (step) {
    if (progStepUpload) {
      progStepUpload.className = step === 'upload' ? 'prog-step active' : (step === 'transcribe' || step === 'analyze' || step === 'done' ? 'prog-step completed' : 'prog-step');
    }
    if (progStepTranscribe) {
      progStepTranscribe.className = step === 'transcribe' ? 'prog-step active' : (step === 'analyze' || step === 'done' ? 'prog-step completed' : 'prog-step');
    }
    if (progStepAnalyze) {
      progStepAnalyze.className = step === 'analyze' ? 'prog-step active' : (step === 'done' ? 'prog-step completed' : 'prog-step');
    }
  }
}

function uploadMediaWithProgress(file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        const loadedMb = (e.loaded / (1024 * 1024)).toFixed(1);
        const totalMb = (e.total / (1024 * 1024)).toFixed(1);
        setProgress({
          percent: pct,
          title: `1/3 Uploading Media (${pct}%)`,
          detail: `Uploaded ${loadedMb} MB of ${totalMb} MB (${pct}% complete)...`,
          step: 'upload',
          ticker: `Uploading ${file.name} to server...`
        });
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const res = JSON.parse(xhr.responseText);
          resolve(res);
        } catch (err) {
          reject(new Error('Invalid server response format during upload.'));
        }
      } else {
        reject(new Error(xhr.responseText || `Upload failed with status ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network connection error during upload.')));
    xhr.addEventListener('abort', () => reject(new Error('Upload operation was aborted.')));

    xhr.open('POST', '/api/upload');
    xhr.send(formData);
  });
}

function transcribeAudioWithProgress(sessionId, modelSize, language) {
  return new Promise((resolve, reject) => {
    setProgress({
      percent: 0,
      title: '2/3 Whisper Transcribing (0%)',
      detail: `Loading Faster-Whisper ${modelSize} model with Silero VAD...`,
      step: 'transcribe',
      ticker: 'Warming up Whisper neural model...'
    });

    const params = new URLSearchParams();
    if (modelSize) params.append('model_size', modelSize);
    if (language && language !== 'auto') params.append('language', language);

    const sseUrl = `/api/transcribe-stream/${sessionId}?${params.toString()}`;
    const eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
          const pct = data.percent || 0;
          const curr = formatTime(data.current_time || 0);
          const total = formatTime(data.total_duration || 0);
          setProgress({
            percent: pct,
            title: `2/3 Whisper Transcribing (${pct}%)`,
            detail: `Transcribed ${curr} / ${total} audio (${pct}%)`,
            step: 'transcribe',
            ticker: data.text ? `"${data.text}"` : 'Transcribing speech segments...'
          });
        } else if (data.type === 'complete') {
          eventSource.close();
          setProgress({
            percent: 100,
            title: '2/3 Transcription Complete (100%)',
            detail: 'Timestamped transcript with word alignments generated.',
            step: 'transcribe',
            ticker: 'Speech-to-text complete!'
          });
          resolve(data.transcript);
        } else if (data.type === 'error') {
          eventSource.close();
          reject(new Error(data.message || 'Transcription error occurred.'));
        }
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    eventSource.onerror = (err) => {
      eventSource.close();
      reject(new Error('Transcription stream connection interrupted.'));
    };
  });
}

async function processSelectedFile(file) {
  try {
    uploadSection.classList.add('hidden');
    progressBanner.classList.remove('hidden');

    // Step 1: Upload media & extract audio with live upload percentage
    setProgress({
      percent: 0,
      title: '1/3 Uploading Media (0%)',
      detail: `Preparing "${file.name}" for upload...`,
      step: 'upload',
      ticker: 'Initiating file transfer...'
    });

    const uploadData = await uploadMediaWithProgress(file);
    currentSessionId = uploadData.session_id;

    // Setup Media Player
    setupPlayer(uploadData.media_url, uploadData.is_video);
    stripFileName.textContent = uploadData.filename;

    // Step 2: Transcribe with live streaming percentage (0% to 100%)
    currentTranscript = await transcribeAudioWithProgress(
      currentSessionId,
      modelSelect.value,
      langSelect.value
    );
    transcriptSegments = currentTranscript.segments || [];

    // Calculate Metrics & Render Transcript
    updateKPIMetrics(currentTranscript);
    renderTranscript(transcriptSegments);
    stripLanguage.textContent = (currentTranscript.language || 'en').toUpperCase();

    // Show workspace
    progressBanner.classList.add('hidden');
    workspaceSection.classList.remove('hidden');

    // Step 3: Run AI Analysis in Background
    runAIAnalysis(currentSessionId);

  } catch (err) {
    console.error(err);
    alert('Processing Error: ' + err.message);
    progressBanner.classList.add('hidden');
    uploadSection.classList.remove('hidden');
  }
}

function updateKPIMetrics(transcript) {
  const durationSec = transcript.duration || 0;
  kpiDuration.textContent = formatTime(durationSec);

  // Total word count
  let totalWords = 0;
  if (transcript.segments) {
    transcript.segments.forEach(s => {
      if (s.words && s.words.length > 0) totalWords += s.words.length;
      else if (s.text) totalWords += s.text.trim().split(/\s+/).length;
    });
  }
  kpiWords.textContent = totalWords.toLocaleString();

  // Words per minute (WPM)
  const durationMinutes = durationSec / 60;
  const wpm = durationMinutes > 0 ? Math.round(totalWords / durationMinutes) : 0;
  kpiPace.textContent = `Words (~${wpm} WPM)`;
}

async function runAIAnalysis(sessionId) {
  try {
    aiMeetingTitle.textContent = 'Analyzing with Gemini AI...';
    aiExecutiveSummary.textContent = 'Extracting summary, key topics, action items, and decisions...';

    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    });

    if (!res.ok) {
      const err = await res.json();
      aiMeetingTitle.textContent = 'Analysis Needs API Key';
      aiExecutiveSummary.innerHTML = `<span style="color:#f43f5e">AI Analysis skipped: ${err.detail || 'Missing Gemini API Key'}</span>. Click <b>Settings</b> at the top right to configure your API key.`;
      return;
    }

    currentAnalysis = await res.json();
    renderAnalysis(currentAnalysis);

  } catch (err) {
    console.error('AI Analysis failed:', err);
    aiMeetingTitle.textContent = 'Meeting Intelligence';
    aiExecutiveSummary.textContent = 'Analysis could not be generated. Check your Gemini API connection.';
  }
}

// ==========================================
// Rendering Functions & Word Karaoke
// ==========================================
function setupPlayer(mediaUrl, isVideo) {
  if (isVideo) {
    mediaPlayer.classList.remove('hidden');
    audioPlayer.classList.add('hidden');
    mediaPlayer.src = mediaUrl;
    activePlayer = mediaPlayer;
  } else {
    mediaPlayer.classList.add('hidden');
    audioPlayer.classList.remove('hidden');
    audioPlayer.src = mediaUrl;
    activePlayer = audioPlayer;
  }

  // Audio visualizer hook
  const onPlay = () => audioVisualizer.classList.add('playing');
  const onPause = () => audioVisualizer.classList.remove('playing');

  activePlayer.addEventListener('play', onPlay);
  activePlayer.addEventListener('pause', onPause);
  activePlayer.addEventListener('ended', onPause);
}

function initSpeedControls() {
  document.querySelectorAll('.speed-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.speed-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const rate = parseFloat(pill.dataset.speed) || 1.0;
      if (activePlayer) activePlayer.playbackRate = rate;
    });
  });
}

function renderTranscript(segments) {
  transcriptList.innerHTML = '';
  if (!segments || segments.length === 0) {
    transcriptList.innerHTML = '<div style="padding:20px; color:#9ca3af; text-align:center;">No speech detected in this recording.</div>';
    return;
  }

  segments.forEach(seg => {
    const row = document.createElement('div');
    row.className = 'transcript-row';
    row.dataset.start = seg.start;
    row.dataset.end = seg.end;
    row.id = `seg-${seg.id}`;

    // Render word spans for word-level karaoke if words are present
    let wordsHtml = '';
    if (seg.words && seg.words.length > 0) {
      wordsHtml = seg.words.map((w, wIdx) => {
        return `<span class="word-span" data-start="${w.start}" data-end="${w.end}" id="w-${seg.id}-${wIdx}">${escapeHtml(w.word)}</span>`;
      }).join(' ');
    } else {
      wordsHtml = escapeHtml(seg.text);
    }

    row.innerHTML = `
      <div class="transcript-time">${formatTime(seg.start)}</div>
      <div class="transcript-text">${wordsHtml}</div>
      <button class="copy-line-btn" title="Copy quote with timestamp" onclick="event.stopPropagation(); copyLine(${seg.start}, '${escapeQuote(seg.text)}')">
        <i class="fa-regular fa-copy"></i>
      </button>
    `;

    row.addEventListener('click', () => {
      if (activePlayer) {
        activePlayer.currentTime = seg.start;
        activePlayer.play();
      }
    });

    transcriptList.appendChild(row);
  });
}

window.copyLine = function(sec, text) {
  const line = `[${formatTime(sec)}] "${text}"`;
  navigator.clipboard.writeText(line);
  alert(`Copied: ${line}`);
};

function renderAnalysis(analysis) {
  // Title & Summary
  aiMeetingTitle.textContent = analysis.meeting_title || 'Meeting Summary';
  aiExecutiveSummary.textContent = analysis.executive_summary || 'No summary available.';

  // Sentiment
  const sentiment = analysis.overall_sentiment || 'Neutral';
  stripSentiment.textContent = `${sentiment} Tone`;
  stripSentiment.className = `sentiment-pill sentiment-${sentiment.toLowerCase()}`;
  kpiSentimentText.textContent = sentiment;

  // Key Topics
  topicsContainer.innerHTML = '';
  if (analysis.key_topics && analysis.key_topics.length > 0) {
    analysis.key_topics.forEach(t => {
      const card = document.createElement('div');
      card.className = 'topic-card';
      const pointsHtml = (t.key_points || []).map(p => `<li>${escapeHtml(p)}</li>`).join('');
      card.innerHTML = `
        <h4><i class="fa-solid fa-hashtag"></i> ${escapeHtml(t.topic)}</h4>
        <p>${escapeHtml(t.summary)}</p>
        <ul class="topic-points">${pointsHtml}</ul>
      `;
      topicsContainer.appendChild(card);
    });
  } else {
    topicsContainer.innerHTML = '<p style="color:#9ca3af;">No specific topic categories detected.</p>';
  }

  // Key Takeaways
  takeawaysList.innerHTML = '';
  if (analysis.key_takeaways && analysis.key_takeaways.length > 0) {
    analysis.key_takeaways.forEach(tk => {
      const li = document.createElement('li');
      li.textContent = tk;
      takeawaysList.appendChild(li);
    });
  }

  // Action Items
  actionItemsList = analysis.action_items || [];
  kpiActionCount.textContent = actionItemsList.length;
  actionItemCountBadge.textContent = `${actionItemsList.length} Tasks`;
  renderActionItemsTable();

  // Key Decisions
  decisionsContainer.innerHTML = '';
  const decisions = analysis.key_decisions || [];
  kpiDecisionCount.textContent = decisions.length;
  if (decisions.length > 0) {
    decisions.forEach(d => {
      const card = document.createElement('div');
      card.className = 'decision-card';
      card.innerHTML = `
        <h5><i class="fa-solid fa-check"></i> Decision ${d.id}: ${escapeHtml(d.decision)}</h5>
        <p>${escapeHtml(d.rationale || '')}</p>
      `;
      decisionsContainer.appendChild(card);
    });
  } else {
    decisionsContainer.innerHTML = '<p style="color:#9ca3af;">No major decisions recorded.</p>';
  }
}

// ==========================================
// Interactive Action Items Tracker
// ==========================================
function initActionFilters() {
  document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentActionFilter = btn.dataset.filter;
      renderActionItemsTable();
    });
  });
}

function renderActionItemsTable() {
  actionItemsTableBody.innerHTML = '';
  if (!actionItemsList || actionItemsList.length === 0) {
    actionItemsTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#9ca3af; padding:20px;">No action items detected.</td></tr>';
    return;
  }

  const filtered = actionItemsList.filter(item => {
    if (currentActionFilter === 'all') return true;
    if (currentActionFilter === 'high') return (item.priority || '').toLowerCase() === 'high';
    if (currentActionFilter === 'open') return (item.status || '').toLowerCase() === 'open';
    if (currentActionFilter === 'completed') return (item.status || '').toLowerCase() === 'completed';
    return true;
  });

  if (filtered.length === 0) {
    actionItemsTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#9ca3af; padding:20px;">No items match the selected filter.</td></tr>';
    return;
  }

  filtered.forEach(item => {
    const tr = document.createElement('tr');
    const isDone = (item.status || '').toLowerCase() === 'completed';
    if (isDone) tr.className = 'task-completed';

    const pClass = `priority-${(item.priority || 'medium').toLowerCase()}`;
    const statusClass = isDone ? 'status-completed' : (item.status === 'In Progress' ? 'status-in-progress' : 'status-open');
    const statusIcon = isDone ? 'fa-circle-check' : (item.status === 'In Progress' ? 'fa-spinner' : 'fa-circle-dot');

    tr.innerHTML = `
      <td><strong>${item.id}</strong></td>
      <td class="task-text-col">${escapeHtml(item.task)}</td>
      <td><i class="fa-regular fa-user" style="margin-right:4px;"></i> ${escapeHtml(item.assignee)}</td>
      <td><i class="fa-regular fa-calendar" style="margin-right:4px;"></i> ${escapeHtml(item.deadline)}</td>
      <td><span class="badge ${pClass}">${escapeHtml(item.priority)}</span></td>
      <td>
        <button class="task-status-btn ${statusClass}" onclick="toggleTaskStatus(${item.id})">
          <i class="fa-regular ${statusIcon}"></i> ${escapeHtml(item.status || 'Open')}
        </button>
      </td>
    `;
    actionItemsTableBody.appendChild(tr);
  });
}

window.toggleTaskStatus = function(taskId) {
  const item = actionItemsList.find(i => i.id === taskId);
  if (!item) return;

  // Cycle status: Open -> In Progress -> Completed -> Open
  if (item.status === 'Open') item.status = 'In Progress';
  else if (item.status === 'In Progress') item.status = 'Completed';
  else item.status = 'Open';

  renderActionItemsTable();
};

// ==========================================
// Synced Player & Word Karaoke Engine
// ==========================================
function initPlayerEvents() {
  let activeWordSpan = null;

  const handleTimeUpdate = (e) => {
    const curTime = e.target.currentTime;
    let activeRow = null;

    // Line-level highlight
    document.querySelectorAll('.transcript-row').forEach(row => {
      const start = parseFloat(row.dataset.start);
      const end = parseFloat(row.dataset.end);
      if (curTime >= start && curTime <= end) {
        row.classList.add('active');
        activeRow = row;
      } else {
        row.classList.remove('active');
      }
    });

    if (activeRow) {
      // Word-level karaoke highlight inside the active row
      const wordSpans = activeRow.querySelectorAll('.word-span');
      wordSpans.forEach(w => {
        const wStart = parseFloat(w.dataset.start);
        const wEnd = parseFloat(w.dataset.end);
        if (curTime >= wStart && curTime <= wEnd) {
          if (activeWordSpan !== w) {
            if (activeWordSpan) activeWordSpan.classList.remove('word-active');
            w.classList.add('word-active');
            activeWordSpan = w;
          }
        } else {
          w.classList.remove('word-active');
        }
      });

      // Smooth scrolling
      const containerTop = transcriptList.scrollTop;
      const containerHeight = transcriptList.clientHeight;
      const rowTop = activeRow.offsetTop - transcriptList.offsetTop;

      if (rowTop < containerTop || rowTop > (containerTop + containerHeight - 80)) {
        transcriptList.scrollTo({ top: rowTop - 50, behavior: 'smooth' });
      }
    }
  };

  mediaPlayer.addEventListener('timeupdate', handleTimeUpdate);
  audioPlayer.addEventListener('timeupdate', handleTimeUpdate);

  // Keyword search with match counter
  transcriptSearch.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    let matches = 0;

    document.querySelectorAll('.transcript-row').forEach(row => {
      const textElem = row.querySelector('.transcript-text');
      const text = textElem.textContent;
      if (!term) {
        row.style.display = 'flex';
        searchCount.classList.add('hidden');
      } else if (text.toLowerCase().includes(term)) {
        row.style.display = 'flex';
        matches++;
        const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
        textElem.innerHTML = escapeHtml(text).replace(regex, '<mark class="highlight-term">$1</mark>');
      } else {
        row.style.display = 'none';
      }
    });

    if (term) {
      searchCount.textContent = `${matches} match${matches === 1 ? '' : 'es'}`;
      searchCount.classList.remove('hidden');
    }
  });

  // Copy full transcript
  document.getElementById('copyTranscriptBtn')?.addEventListener('click', () => {
    if (currentTranscript?.plain_text) {
      navigator.clipboard.writeText(currentTranscript.plain_text);
      alert('Full transcript copied to clipboard!');
    }
  });

  // Copy Executive Summary
  document.getElementById('copySummaryBtn')?.addEventListener('click', () => {
    if (aiExecutiveSummary.innerText) {
      navigator.clipboard.writeText(aiExecutiveSummary.innerText);
      alert('Executive summary copied to clipboard!');
    }
  });
}

// ==========================================
// Interactive Q&A ("Ask the Meeting")
// ==========================================
function initChatEvents() {
  const sendQuestion = async () => {
    const q = chatInput.value.trim();
    if (!q || !currentSessionId) return;

    appendChatMessage('user', q);
    chatInput.value = '';

    // Show wave typing indicator
    const assistantMsg = appendChatMessage('assistant', '<div class="typing-dots"><span></span><span></span><span></span></div>', true);

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: currentSessionId, query: q })
      });

      if (!res.ok) {
        const err = await res.json();
        assistantMsg.querySelector('.msg-body').innerHTML = `<span style="color:#f43f5e">Error: ${err.detail || 'Q&A failed'}</span>`;
        return;
      }

      const data = await res.json();
      let formattedAnswer = escapeHtml(data.answer);

      // Convert bracket timestamps into clickable pills
      formattedAnswer = formattedAnswer.replace(/\[(\d{1,2}:\d{2})(?:\s*-\s*\d{1,2}:\d{2})?\]/g, (match, startTime) => {
        const seconds = parseTimeToSeconds(startTime);
        return `<span class="timestamp-cite" onclick="seekTo(${seconds})">${match}</span>`;
      });

      assistantMsg.querySelector('.msg-body').innerHTML = formattedAnswer;

    } catch (err) {
      assistantMsg.querySelector('.msg-body').textContent = 'Failed to get answer. Check your connection or API key.';
    }
  };

  sendChatBtn.addEventListener('click', sendQuestion);
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendQuestion();
  });
}

function askPreset(question) {
  chatInput.value = question;
  document.querySelector('[data-tab="tabQA"]').click();
  sendChatBtn.click();
}

function appendChatMessage(sender, text, isHtml = false) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${sender === 'user' ? 'user-msg' : 'assistant-msg'}`;
  msgDiv.innerHTML = `
    <div class="msg-avatar"><i class="fa-solid ${sender === 'user' ? 'fa-user' : 'fa-robot'}"></i></div>
    <div class="msg-body">${isHtml ? text : escapeHtml(text)}</div>
  `;
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return msgDiv;
}

window.seekTo = function(seconds) {
  if (activePlayer) {
    document.querySelector('[data-tab="tabTranscript"]').click();
    activePlayer.currentTime = seconds;
    activePlayer.play();
  }
};

// ==========================================
// Exports & Live Document Preview
// ==========================================
function initExportEvents() {
  // Live Preview PDF Modal
  document.getElementById('previewPdfBtn')?.addEventListener('click', () => {
    if (!currentAnalysis) {
      alert('Meeting analysis is not ready yet.');
      return;
    }
    const docText = generateMoMDocumentText();
    previewDocBody.innerText = docText;
    docPreviewModal.classList.remove('hidden');
  });

  // Copy Markdown
  document.getElementById('copyMdBtn')?.addEventListener('click', () => {
    const docText = generateMoMDocumentText();
    navigator.clipboard.writeText(docText);
    alert('Full Markdown report copied to clipboard!');
  });

  document.getElementById('downloadPdfBtn')?.addEventListener('click', () => {
    if (currentSessionId) window.open(`/api/export/${currentSessionId}/pdf`, '_blank');
  });
  document.getElementById('downloadMdBtn')?.addEventListener('click', () => {
    if (currentSessionId) window.open(`/api/export/${currentSessionId}/md`, '_blank');
  });
  document.getElementById('exportSrtBtn')?.addEventListener('click', () => {
    if (currentSessionId) window.open(`/api/export/${currentSessionId}/srt`, '_blank');
  });
  document.getElementById('exportVttBtn')?.addEventListener('click', () => {
    if (currentSessionId) window.open(`/api/export/${currentSessionId}/vtt`, '_blank');
  });
  document.getElementById('downloadSrtBtn')?.addEventListener('click', () => {
    if (currentSessionId) window.open(`/api/export/${currentSessionId}/srt`, '_blank');
  });
}

function generateMoMDocumentText() {
  if (!currentAnalysis) return 'No analysis available.';
  let out = `MINUTES OF MEETING: ${currentAnalysis.meeting_title}\n`;
  out += `=========================================================\n\n`;
  out += `OVERALL TONE: ${currentAnalysis.overall_sentiment}\n\n`;
  out += `1. EXECUTIVE SUMMARY\n---------------------------------------------------------\n`;
  out += `${currentAnalysis.executive_summary}\n\n`;

  out += `2. KEY TOPICS\n---------------------------------------------------------\n`;
  (currentAnalysis.key_topics || []).forEach(t => {
    out += `• ${t.topic}: ${t.summary}\n`;
    (t.key_points || []).forEach(p => out += `   - ${p}\n`);
  });
  out += `\n`;

  out += `3. ACTION ITEMS\n---------------------------------------------------------\n`;
  (actionItemsList || []).forEach(item => {
    out += `[${item.status}] #${item.id}: ${item.task} | Assignee: ${item.assignee} | Due: ${item.deadline} | Priority: ${item.priority}\n`;
  });
  out += `\n`;

  out += `4. KEY DECISIONS\n---------------------------------------------------------\n`;
  (currentAnalysis.key_decisions || []).forEach(d => {
    out += `• Decision ${d.id}: ${d.decision} (${d.rationale || ''})\n`;
  });

  return out;
}

// ==========================================
// Helper Utilities
// ==========================================
function formatTime(sec) {
  if (isNaN(sec)) return "00:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function parseTimeToSeconds(timeStr) {
  const parts = timeStr.split(':').map(Number);
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return 0;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag));
}

function escapeQuote(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
