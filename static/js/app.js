// Application State
let currentSessionId = null;
let currentTranscript = null;
let currentAnalysis = null;
let activePlayer = null;
let transcriptSegments = [];

// DOM Elements
const dropzone = document.getElementById('dropzone');
const mediaFileInput = document.getElementById('mediaFileInput');
const browseBtn = document.getElementById('browseBtn');
const modelSelect = document.getElementById('modelSelect');
const langSelect = document.getElementById('langSelect');
const progressBanner = document.getElementById('progressBanner');
const progressStatus = document.getElementById('progressStatus');
const progressDetail = document.getElementById('progressDetail');
const uploadSection = document.getElementById('uploadSection');
const workspaceSection = document.getElementById('workspaceSection');

const mediaPlayer = document.getElementById('mediaPlayer');
const audioPlayer = document.getElementById('audioPlayer');
const transcriptList = document.getElementById('transcriptList');
const transcriptSearch = document.getElementById('transcriptSearch');

// Metadata & Intelligence Elements
const stripFileName = document.getElementById('stripFileName');
const stripDuration = document.getElementById('stripDuration');
const stripLanguage = document.getElementById('stripLanguage');
const stripSentiment = document.getElementById('stripSentiment');
const aiMeetingTitle = document.getElementById('aiMeetingTitle');
const aiExecutiveSummary = document.getElementById('aiExecutiveSummary');
const topicsContainer = document.getElementById('topicsContainer');
const takeawaysList = document.getElementById('takeawaysList');
const actionItemsTableBody = document.getElementById('actionItemsTableBody');
const actionItemCount = document.getElementById('actionItemCount');
const decisionsContainer = document.getElementById('decisionsContainer');

// Chat Elements
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendChatBtn = document.getElementById('sendChatBtn');

// Settings Elements
const apiStatusBadge = document.getElementById('apiStatusBadge');
const apiStatusText = document.getElementById('apiStatusText');
const settingsModal = document.getElementById('settingsModal');
const openSettingsBtn = document.getElementById('openSettingsBtn');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const geminiApiKeyInput = document.getElementById('geminiApiKeyInput');
const geminiModelInput = document.getElementById('geminiModelInput');

// ==========================================
// Initialization & Settings
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
  checkApiStatus();
  initTabNavigation();
  initDropzoneEvents();
  initPlayerEvents();
  initChatEvents();
  initExportEvents();
  initSettingsModal();
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
async function processSelectedFile(file) {
  try {
    uploadSection.classList.add('hidden');
    progressBanner.classList.remove('hidden');
    progressStatus.textContent = '1/3 Uploading & Extracting Audio...';
    progressDetail.textContent = `Processing "${file.name}" with FFmpeg (16kHz mono normalization).`;

    // Step 1: Upload media & extract audio
    const formData = new FormData();
    formData.append('file', file);

    const uploadRes = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    if (!uploadRes.ok) throw new Error(await uploadRes.text());
    const uploadData = await uploadRes.json();
    currentSessionId = uploadData.session_id;

    // Setup Media Player
    setupPlayer(uploadData.media_url, uploadData.is_video);
    stripFileName.textContent = uploadData.filename;

    // Step 2: Transcribe
    progressStatus.textContent = '2/3 Generating Timestamped Transcript...';
    progressDetail.textContent = `Running Whisper (${modelSelect.value}) with Silero VAD filtering.`;

    const transcribeRes = await fetch('/api/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: currentSessionId,
        model_size: modelSelect.value,
        language: langSelect.value
      })
    });
    if (!transcribeRes.ok) throw new Error(await transcribeRes.text());
    currentTranscript = await transcribeRes.json();
    transcriptSegments = currentTranscript.segments || [];

    // Render Transcript & Metadata
    renderTranscript(transcriptSegments);
    stripDuration.textContent = formatTime(currentTranscript.duration);
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
// Rendering Functions
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

    row.innerHTML = `
      <div class="transcript-time">${formatTime(seg.start)}</div>
      <div class="transcript-text">${escapeHtml(seg.text)}</div>
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

function renderAnalysis(analysis) {
  // Title & Summary
  aiMeetingTitle.textContent = analysis.meeting_title || 'Meeting Summary';
  aiExecutiveSummary.textContent = analysis.executive_summary || 'No summary available.';

  // Sentiment
  const sentiment = analysis.overall_sentiment || 'Neutral';
  stripSentiment.textContent = `${sentiment} Tone`;
  stripSentiment.className = `sentiment-pill sentiment-${sentiment.toLowerCase()}`;

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

  // Action Items Table
  actionItemsTableBody.innerHTML = '';
  const items = analysis.action_items || [];
  actionItemCount.textContent = `${items.length} Items`;
  if (items.length > 0) {
    items.forEach(item => {
      const tr = document.createElement('tr');
      const pClass = `priority-${(item.priority || 'medium').toLowerCase()}`;
      tr.innerHTML = `
        <td><strong>${item.id}</strong></td>
        <td>${escapeHtml(item.task)}</td>
        <td><i class="fa-regular fa-user" style="margin-right:4px;"></i> ${escapeHtml(item.assignee)}</td>
        <td><i class="fa-regular fa-calendar" style="margin-right:4px;"></i> ${escapeHtml(item.deadline)}</td>
        <td><span class="badge ${pClass}">${escapeHtml(item.priority)}</span></td>
        <td><span class="badge" style="background:rgba(255,255,255,0.06);">${escapeHtml(item.status)}</span></td>
      `;
      actionItemsTableBody.appendChild(tr);
    });
  } else {
    actionItemsTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#9ca3af; padding:20px;">No explicit action items found.</td></tr>';
  }

  // Key Decisions
  decisionsContainer.innerHTML = '';
  const decisions = analysis.key_decisions || [];
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
// Synced Player & Subtitle Highlighting
// ==========================================
function initPlayerEvents() {
  const handleTimeUpdate = (e) => {
    const curTime = e.target.currentTime;
    let activeRow = null;

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
      // Smoothly scroll active row into view within container
      const containerTop = transcriptList.scrollTop;
      const containerHeight = transcriptList.clientHeight;
      const rowTop = activeRow.offsetTop - transcriptList.offsetTop;

      if (rowTop < containerTop || rowTop > (containerTop + containerHeight - 60)) {
        transcriptList.scrollTo({ top: rowTop - 40, behavior: 'smooth' });
      }
    }
  };

  mediaPlayer.addEventListener('timeupdate', handleTimeUpdate);
  audioPlayer.addEventListener('timeupdate', handleTimeUpdate);

  // Keyword search
  transcriptSearch.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    document.querySelectorAll('.transcript-row').forEach(row => {
      const textElem = row.querySelector('.transcript-text');
      const text = textElem.textContent;
      if (!term) {
        row.style.display = 'flex';
        textElem.innerHTML = escapeHtml(text);
      } else if (text.toLowerCase().includes(term)) {
        row.style.display = 'flex';
        const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
        textElem.innerHTML = escapeHtml(text).replace(regex, '<mark class="highlight-term">$1</mark>');
      } else {
        row.style.display = 'none';
      }
    });
  });

  // Copy full transcript
  document.getElementById('copyTranscriptBtn')?.addEventListener('click', () => {
    if (currentTranscript?.plain_text) {
      navigator.clipboard.writeText(currentTranscript.plain_text);
      alert('Full transcript copied to clipboard!');
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

    const assistantMsg = appendChatMessage('assistant', 'Thinking and searching transcript...');

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

      // Convert bracket timestamps like [01:23] into clickable pills
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

function appendChatMessage(sender, text) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${sender === 'user' ? 'user-msg' : 'assistant-msg'}`;
  msgDiv.innerHTML = `
    <div class="msg-avatar"><i class="fa-solid ${sender === 'user' ? 'fa-user' : 'fa-robot'}"></i></div>
    <div class="msg-body">${escapeHtml(text)}</div>
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
// Exports
// ==========================================
function initExportEvents() {
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

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
