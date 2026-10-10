/* ============================================================
   ExamPrep — Frontend Application Logic
   Clean, Professional, Functional Architecture
   ============================================================ */

const API = '/api';

// ── Application State ──────────────────────────────────────────
let syllabus = [];
let allPapers = [];
let currentFile = null;
let charts = {};

// ── Lifecycle Initialization ───────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
  await fetchStatus();
  
  const topicInput = document.getElementById('topic-input');
  if (topicInput) {
    topicInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') addTopic();
    });
  }
});

// ── Server Status & Health Check ──────────────────────────────
async function fetchStatus() {
  try {
    const data = await api('/status');
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const modeSelect = document.getElementById('mode-select');

    if (data.ai_available) {
      if (dot) dot.className = 'status-dot active';
      if (text) text.textContent = 'Vision Engine Active';
      if (modeSelect) modeSelect.value = 'ai';
    } else {
      if (dot) dot.className = 'status-dot demo';
      if (text) text.textContent = 'Sample Test Mode';
      if (modeSelect) modeSelect.value = 'demo';
    }

    if (data.syllabus && data.syllabus.length > 0) {
      syllabus = data.syllabus;
      renderTopics();
    }

    if (data.papers > 0) {
      await refreshAnalysis();
    }
  } catch (err) {
    toast('Unable to connect to backend server (localhost:5000).', 'error');
  }
}

// ── Universal API Client ───────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Server request failed');
  }
  return res.json();
}

// ── Syllabus Topic Management ──────────────────────────────────
function addTopic() {
  const inp = document.getElementById('topic-input');
  const val = inp.value.trim();
  if (!val || syllabus.includes(val)) {
    inp.value = '';
    return;
  }
  syllabus.push(val);
  inp.value = '';
  renderTopics();
  saveSyllabus(true);
}

function removeTopic(topic) {
  syllabus = syllabus.filter(t => t !== topic);
  renderTopics();
  saveSyllabus(true);
}

function renderTopics() {
  const list = document.getElementById('topic-list');
  const countEl = document.getElementById('topics-count');
  const syncBtn = document.getElementById('sync-papers-btn');

  if (countEl) countEl.textContent = `${syllabus.length} Topics`;
  if (syncBtn) {
    syncBtn.style.display = allPapers.length > 0 ? 'inline-flex' : 'none';
  }

  if (!syllabus.length) {
    list.innerHTML = '<span class="topic-chip-empty">No syllabus topics added yet. Add above or click "Load Sample Syllabus".</span>';
    return;
  }

  list.innerHTML = syllabus.map(t => {
    const safeTopic = t.replace(/'/g, "\\'");
    return `
      <span class="topic-chip">
        <span>${escapeHtml(t)}</span>
        <span class="topic-chip-remove" onclick="removeTopic('${safeTopic}')" title="Remove topic">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </span>
      </span>`;
  }).join('');
}

async function saveSyllabus(showToast = false) {
  try {
    await api('/syllabus', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topics: syllabus })
    });

    // Immediately refresh analysis so all papers and priority tables re-evaluate
    await refreshAnalysis();
    if (showToast) {
      toast(`Syllabus synced! Existing papers automatically updated with new topic(s).`, 'success');
    }
  } catch (e) {
    console.error('Failed to save syllabus:', e);
  }
}

async function syncSyllabusWithPapers() {
  if (!allPapers.length) {
    toast('No uploaded papers found yet.', 'info');
    return;
  }
  try {
    await api('/papers/remap', { method: 'POST' });
    await refreshAnalysis();
    toast(`Successfully re-synced ${allPapers.length} paper(s) with ${syllabus.length} syllabus topics!`, 'success');
  } catch (e) {
    toast('Failed to re-sync papers: ' + e.message, 'error');
  }
}

async function clearSyllabus() {
  if (!syllabus.length) return;
  syllabus = [];
  renderTopics();
  await api('/syllabus', { method: 'DELETE' });
  if (allPapers.length > 0) {
    await refreshAnalysis();
  }
  toast('Syllabus topics cleared.', 'info');
}

function loadDefaultSyllabus() {
  const sampleTopics = [
    'Thermodynamics',
    'Electromagnetism',
    'Quantum Mechanics',
    'Fluid Dynamics',
    'Classical Mechanics',
    'Optics'
  ];
  syllabus = [...new Set([...syllabus, ...sampleTopics])];
  renderTopics();
  saveSyllabus(true);
}

// ── File Selection & Drag-and-Drop ────────────────────────────
function handleFile(file) {
  if (!file) return;

  if (file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf') {
    toast('PDF upload is coming soon! Please upload PNG or JPG exam paper photos for now.', 'info');
    clearSelectedFile();
    return;
  }

  currentFile = file;

  const preview = document.getElementById('file-preview');
  const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
  const sizeText = file.size > 1024 * 1024 ? `${sizeMb} MB` : `${(file.size / 1024).toFixed(1)} KB`;

  preview.innerHTML = `
    <div class="selected-file-info">
      <div style="display:flex; align-items:center; gap:8px;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
        </svg>
        <span style="font-weight:500;">${escapeHtml(file.name)}</span>
        <span style="color:var(--text-dim);">(${sizeText})</span>
      </div>
      <button class="btn btn-subtle btn-sm" onclick="clearSelectedFile()" style="padding:2px 6px;">Change</button>
    </div>`;
}

function clearSelectedFile() {
  currentFile = null;
  const fileInput = document.getElementById('file-input');
  if (fileInput) fileInput.value = '';
  document.getElementById('file-preview').innerHTML = '';
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('dropzone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
}

// ── Upload Paper Execution ────────────────────────────────────
async function uploadPaper() {
  if (!currentFile) {
    toast('Please select an exam paper image (PNG or JPG) first.', 'error');
    return;
  }

  const year = parseInt(document.getElementById('year-input').value) || 2024;
  const mode = document.getElementById('mode-select').value;
  const isDemo = mode === 'demo';

  const btn = document.getElementById('upload-btn');
  const btnText = document.getElementById('upload-btn-text');

  btn.disabled = true;
  btnText.textContent = isDemo ? 'Processing sample data...' : 'Extracting questions via Gemini...';

  try {
    const fd = new FormData();
    fd.append('file', currentFile);
    fd.append('year', year);
    fd.append('mock', isDemo ? 'true' : 'false');

    const result = await fetch(API + '/upload', { method: 'POST', body: fd }).then(r => r.json());

    if (result.error) {
      throw new Error(result.error + (result.hint ? '\n' + result.hint : ''));
    }

    const questionCount = result.paper?.questions?.length || 0;
    toast(`Paper (${year}) processed successfully — ${questionCount} questions extracted.`, 'success');

    clearSelectedFile();
    await refreshAnalysis();
  } catch (err) {
    toast(err.message || 'Error occurred while processing exam paper.', 'error');
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Extract & Analyze Paper';
  }
}

// ── Dashboard & Analytics Engine ──────────────────────────────
async function refreshAnalysis() {
  try {
    const [papersData, analysisData] = await Promise.all([
      api('/papers'),
      api('/analysis').catch(() => null)
    ]);

    allPapers = papersData || [];
    const papersCountEl = document.getElementById('papers-count');
    if (papersCountEl) papersCountEl.textContent = `${allPapers.length} Papers`;

    renderPapersList();

    if (analysisData && !analysisData.error && allPapers.length > 0) {
      document.getElementById('empty-state').style.display = 'none';
      document.getElementById('dashboard').style.display = 'block';

      renderKPIs(analysisData.summary);
      renderPriorityTable(analysisData.priorities);
      renderCharts(analysisData.priorities, analysisData.stats);
      populateFilters(analysisData.priorities);
      renderQuestions();
    } else {
      document.getElementById('empty-state').style.display = 'block';
      document.getElementById('dashboard').style.display = 'none';
    }
  } catch (err) {
    console.error('Failed to refresh analytics dashboard:', err);
  }
}

// ── Uploaded Papers List Rendering ────────────────────────────
function renderPapersList() {
  const card = document.getElementById('papers-card');
  const list = document.getElementById('papers-list');
  const sub = document.getElementById('papers-sub');

  if (!allPapers.length) {
    card.style.display = 'none';
    return;
  }

  card.style.display = 'block';
  sub.textContent = `${allPapers.length} paper${allPapers.length !== 1 ? 's' : ''} loaded`;

  list.innerHTML = allPapers.map((p, i) => `
    <div class="paper-item">
      <div class="paper-meta-group">
        <span class="paper-year-badge">${p.year}</span>
        <div>
          <div class="paper-name" title="${escapeHtml(p.filename || '')}">${escapeHtml(p.filename || 'Exam Paper ' + (i + 1))}</div>
          <div class="paper-count">${p.questions ? p.questions.length : 0} questions cataloged</div>
        </div>
      </div>
      <span class="paper-mode-badge">${p.mock ? 'Sample' : 'Vision'}</span>
    </div>`).join('');
}

async function clearPapers() {
  if (!confirm('Are you sure you want to clear all uploaded papers and reset analytics?')) return;
  await api('/papers', { method: 'DELETE' });
  allPapers = [];
  document.getElementById('papers-count').textContent = '0 Papers';
  document.getElementById('empty-state').style.display = 'block';
  document.getElementById('dashboard').style.display = 'none';
  document.getElementById('papers-card').style.display = 'none';
  destroyCharts();
  toast('All examination papers cleared.', 'info');
}

// ── Metric Summary Cards ──────────────────────────────────────
function renderKPIs({ total_papers, total_questions, total_marks, topics_covered }) {
  const kpis = [
    { label: 'Papers Analyzed', value: total_papers },
    { label: 'Questions Identified', value: total_questions },
    { label: 'Total Marks Evaluated', value: total_marks },
    { label: 'Syllabus Topics Covered', value: topics_covered },
  ];

  document.getElementById('kpi-grid').innerHTML = kpis.map(k => `
    <div class="kpi-card">
      <div class="kpi-label">${escapeHtml(k.label)}</div>
      <div class="kpi-value">${k.value}</div>
    </div>`).join('');
}

// ── Analytical Priority Table ─────────────────────────────────
function renderPriorityTable(priorities) {
  const tbody = document.getElementById('priority-table-body');
  if (!tbody) return;

  const maxScore = priorities[0]?.score || 1;

  tbody.innerHTML = priorities.map((p, idx) => {
    const rankClass = idx === 0 ? 'rank-1' : idx === 1 ? 'rank-2' : idx === 2 ? 'rank-3' : '';
    const pct = ((p.score / maxScore) * 100).toFixed(0);

    const typeBadges = Object.entries(p.types || {}).map(([type, count]) => {
      const cls = type === 'theory' ? 'type-theory' : type === 'numerical' ? 'type-numerical' : 'type-derivation';
      return `<span class="type-pill ${cls}">${count} ${type}</span>`;
    }).join('');

    return `
      <tr>
        <td>
          <span class="rank-indicator ${rankClass}">${idx + 1}</span>
        </td>
        <td class="topic-name-cell">
          ${escapeHtml(p.topic)}
        </td>
        <td>
          <span style="font-weight:600; color:var(--text-main);">${p.marks}</span>
          <span style="color:var(--text-muted); font-size:12px;"> marks</span>
        </td>
        <td>
          <span style="font-weight:500;">${p.frequency}×</span>
          <span style="color:var(--text-dim); font-size:12px;"> asked</span>
        </td>
        <td>
          ${typeBadges || '<span style="color:var(--text-dim); font-size:12px;">-</span>'}
        </td>
        <td style="text-align: right;">
          <div style="display:inline-flex; align-items:center; justify-content:flex-end;">
            <div class="score-progress-bar">
              <div class="score-progress-fill" style="width: ${pct}%;"></div>
            </div>
            <span style="font-weight:600; min-width:32px;">${p.score}</span>
          </div>
        </td>
      </tr>`;
  }).join('');
}

// ── Chart.js Visualizations (Clean Professional Palette) ──────
const COLOR_BLUE = '#2563eb';
const COLOR_SLATE = '#64748b';
const COLOR_SKY = '#0284c7';
const COLOR_EMERALD = '#059669';
const COLOR_AMBER = '#d97706';
const COLOR_PURPLE = '#7c3aed';
const COLOR_ROSE = '#e11d48';
const COLOR_INDIGO = '#4f46e5';

const PALETTE = [COLOR_BLUE, COLOR_SKY, COLOR_EMERALD, COLOR_AMBER, COLOR_PURPLE, COLOR_ROSE, COLOR_SLATE, COLOR_INDIGO];

function destroyCharts() {
  Object.values(charts).forEach(c => c && c.destroy && c.destroy());
  charts = {};
}

function renderCharts(priorities, stats) {
  destroyCharts();

  const labels = priorities.map(p => p.topic);
  const marks = priorities.map(p => p.marks);
  const freqs = priorities.map(p => p.frequency);

  const baseScales = {
    x: {
      ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11, weight: 600 } },
      grid: { display: false }
    },
    y: {
      ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11, weight: 600 }, precision: 0 },
      grid: { color: '#f1f5f9' },
      beginAtZero: true
    }
  };

  // 1. Marks Distribution Bar
  const marksCanvas = document.getElementById('marks-chart');
  if (marksCanvas) {
    charts.marks = new Chart(marksCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: marks,
          backgroundColor: '#0a192f',
          borderRadius: 6,
          maxBarThickness: 38
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: baseScales
      }
    });
  }

  // 2. Question Frequency Bar
  const freqCanvas = document.getElementById('freq-chart');
  if (freqCanvas) {
    charts.freq = new Chart(freqCanvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: freqs,
          backgroundColor: '#2563eb',
          borderRadius: 6,
          maxBarThickness: 38
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: baseScales
      }
    });
  }

  // 3. Question Type Donut
  const typeCanvas = document.getElementById('type-chart');
  if (typeCanvas) {
    const typeTotals = {};
    Object.values(stats || {}).forEach(s => {
      Object.entries(s.types || {}).forEach(([t, count]) => {
        typeTotals[t] = (typeTotals[t] || 0) + count;
      });
    });

    const typeKeys = Object.keys(typeTotals);
    const typeValues = Object.values(typeTotals);

    charts.type = new Chart(typeCanvas, {
      type: 'doughnut',
      data: {
        labels: typeKeys.map(k => k.charAt(0).toUpperCase() + k.slice(1)),
        datasets: [{
          data: typeValues,
          backgroundColor: ['#0a192f', '#2563eb', '#10b981', '#f59e0b'],
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#334155', boxWidth: 12, padding: 14, font: { family: 'Plus Jakarta Sans', size: 12, weight: 600 } }
          }
        },
        cutout: '68%'
      }
    });
  }

  // 4. Radar Coverage Chart
  const radarCanvas = document.getElementById('radar-chart');
  if (radarCanvas) {
    charts.radar = new Chart(radarCanvas, {
      type: 'radar',
      data: {
        labels,
        datasets: [{
          label: 'Priority Score',
          data: priorities.map(p => p.score),
          backgroundColor: 'rgba(37, 99, 235, 0.12)',
          borderColor: '#2563eb',
          pointBackgroundColor: '#2563eb',
          pointBorderColor: '#ffffff',
          pointRadius: 4,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          r: {
            ticks: { color: '#94a3b8', font: { size: 10 }, backdropColor: 'transparent', precision: 0 },
            grid: { color: '#e2e8f0' },
            angleLines: { color: '#e2e8f0' },
            pointLabels: { color: '#0a1628', font: { family: 'Plus Jakarta Sans', size: 11, weight: 700 } }
          }
        }
      }
    });
  }
}

// ── Question Explorer Filtering ────────────────────────────────
function populateFilters(priorities) {
  const sel = document.getElementById('filter-topic');
  if (!sel) return;

  const currentVal = sel.value;
  sel.innerHTML = '<option value="">All Topics</option>' +
    priorities.map(p => `<option value="${escapeHtml(p.topic)}">${escapeHtml(p.topic)}</option>`).join('');

  if (currentVal && priorities.some(p => p.topic === currentVal)) {
    sel.value = currentVal;
  }
}

function renderQuestions() {
  const filterTopic = document.getElementById('filter-topic')?.value || '';
  const filterType = document.getElementById('filter-type')?.value || '';
  const filterSearch = (document.getElementById('filter-search')?.value || '').trim().toLowerCase();

  const allQs = allPapers.flatMap((p, paperIdx) =>
    (p.questions || []).map((q, questionIdx) => ({ ...q, year: p.year, paperIdx, questionIdx }))
  );

  const filtered = allQs.filter(q => {
    const matchesTopic = !filterTopic || (q.topic || '').toLowerCase() === filterTopic.toLowerCase();
    const matchesType = !filterType || q.question_type === filterType;
    const matchesSearch = !filterSearch ||
      (q.text || '').toLowerCase().includes(filterSearch) ||
      (q.topic || '').toLowerCase().includes(filterSearch);
    return matchesTopic && matchesType && matchesSearch;
  });

  const container = document.getElementById('questions-list');
  if (!container) return;

  if (!filtered.length) {
    container.innerHTML = '<p style="color:var(--text-dim); text-align:center; padding:32px 0; font-size:13px;">No questions match the selected filter criteria.</p>';
    return;
  }

  container.innerHTML = filtered.map(q => {
    const typeCls = q.question_type === 'theory' ? 'type-theory' : q.question_type === 'numerical' ? 'type-numerical' : 'type-derivation';

    const currentTopic = q.topic || '';
    // Build options list with current syllabus topics
    const optionsHtml = syllabus.map(s => `
      <option value="${escapeHtml(s)}" ${s.toLowerCase() === currentTopic.toLowerCase() ? 'selected' : ''}>
        ${escapeHtml(s)}
      </option>
    `).join('');

    return `
      <div class="question-card">
        <div class="question-card-top">
          <div class="question-card-text">${escapeHtml(q.text)}</div>
          <span class="question-card-marks">${q.marks} Marks</span>
        </div>
        <div class="question-card-meta">
          <span class="type-pill ${typeCls}">${escapeHtml(q.question_type)}</span>
          <span class="meta-tag">Exam Year: ${q.year}</span>
          <div style="display:inline-flex; align-items:center; gap:6px; margin-left:auto; flex-wrap:wrap;">
            <span style="font-size:11px; font-weight:700; color:var(--text-muted);">Topic:</span>
            <select class="select-input" onchange="changeQuestionTopic(${q.paperIdx}, ${q.questionIdx}, this.value)" style="padding:2px 8px; font-size:11.5px; height:28px; width:auto; border-radius:var(--radius-pill); background:var(--bg-subtle); border-color:var(--border);">
              ${optionsHtml}
              ${!syllabus.includes(currentTopic) && currentTopic ? `<option value="${escapeHtml(currentTopic)}" selected>${escapeHtml(currentTopic)}</option>` : ''}
            </select>
          </div>
        </div>
      </div>`;
  }).join('');
}

async function changeQuestionTopic(paperIdx, questionIdx, newTopic) {
  if (!newTopic) return;
  try {
    await api('/questions/update-topic', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paper_idx: paperIdx, question_idx: questionIdx, topic: newTopic })
    });
    // Update local state and re-render dashboard
    if (allPapers[paperIdx]?.questions?.[questionIdx]) {
      allPapers[paperIdx].questions[questionIdx].topic = newTopic;
    }
    await refreshAnalysis();
    toast(`Question re-mapped to "${newTopic}".`, 'success');
  } catch (e) {
    toast('Failed to change question topic: ' + e.message, 'error');
  }
}

// ── Clean Toast Notifications ──────────────────────────────────
function toast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;

  container.appendChild(el);

  setTimeout(() => {
    el.style.animation = 'toast-out 0.2s ease-in forwards';
    setTimeout(() => el.remove(), 200);
  }, 3500);
}

// ── Security Helper: HTML Entity Escaping ───────────────────────
function escapeHtml(str) {
  if (typeof str !== 'string') return String(str || '');
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
