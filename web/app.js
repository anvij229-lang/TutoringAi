const $ = (selector) => document.querySelector(selector);
const input = $('#file-input');
const zone = $('#drop-zone');
const status = $('#upload-status');
const libraryPage = $('.main-content > .page:not(#tutor-page):not(#quiz-page):not(#dashboard-page):not(#flashcards-page):not(#mindmap-page)');
const tutorPage = $('#tutor-page');
const quizPage = $('#quiz-page');
const dashboardPage = $('#dashboard-page');
const flashcardsPage = $('#flashcards-page');
const mindmapPage = $('#mindmap-page');

// The backend's default CORS origin is http://localhost:5173. Serve this folder
// with `py -m http.server 5173` and open /web/ while FastAPI runs on port 8001.
const API_BASE = (window.STUDYROOM_API_BASE || 'http://127.0.0.1:8001').replace(/\/$/, '');
const MATERIALS_KEY = 'studyroom.backend.materials.v1';
const ACTIVE_MATERIAL_KEY = 'studyroom.backend.active-material.v1';
const USER_ID = 'demo';
let sources = readMaterials();
let activeMaterialId = localStorage.getItem(ACTIVE_MATERIAL_KEY) || sources[0]?.id || '';
let activeQuizId = null;
let topicCache = [];
let flashcardSession = null;

function readMaterials() {
  try {
    const value = JSON.parse(localStorage.getItem(MATERIALS_KEY) || '[]');
    return Array.isArray(value) ? value : [];
  } catch (_) {
    return [];
  }
}

function saveMaterials() {
  localStorage.setItem(MATERIALS_KEY, JSON.stringify(sources));
  if (activeMaterialId) localStorage.setItem(ACTIVE_MATERIAL_KEY, activeMaterialId);
}

function currentMaterial() {
  return sources.find((source) => source.id === activeMaterialId) || null;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

const VIDEO_EXTENSIONS = new Set(['mp4', 'mov', 'mkv', 'webm', 'm4v']);

function extensionOf(fileName) {
  return String(fileName || '').split('.').pop().toLowerCase();
}

function materialType(fileName, reportedType = '') {
  const ext = extensionOf(fileName);
  const reported = String(reportedType || '').toLowerCase();
  if (reported === 'video' || VIDEO_EXTENSIONS.has(ext)) return 'video';
  if (reported === 'pptx' || ext === 'pptx') return 'pptx';
  if (reported === 'pdf' || ext === 'pdf') return 'pdf';
  return '';
}

function materialTypeLabel(type) {
  return type === 'video' ? 'VIDEO' : (type || 'file').toUpperCase();
}

function defaultUnit(type) {
  if (type === 'video') return 'transcript segments';
  if (type === 'pptx') return 'slides';
  return 'pages';
}

function countedUnit(unit, count) {
  const label = String(unit || 'units').trim();
  if (count === 1 && label.endsWith('s')) return label.slice(0, -1);
  if (count !== 1 && !label.endsWith('s')) return `${label}s`;
  return label;
}

function sourceIcon(source, small = false) {
  const type = materialType(source.name, source.type);
  const className = small ? 'tiny-file' : 'file-icon';
  return `<span class="${className} ${type || 'other'}">${materialTypeLabel(type)}</span>`;
}

function formatTimestamp(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value);
  const totalSeconds = Math.max(0, Math.floor(value));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function citationLocation(source) {
  if (source.source_location) return String(source.source_location);
  const timestamp = source.timestamp ?? source.start_time ?? source.start_seconds;
  if (timestamp != null) return `timestamp ${formatTimestamp(timestamp)}`;
  const slide = source.slide_number ?? source.slide;
  if (slide != null) return `slide ${slide}`;
  const page = source.page ?? source.page_number ?? source.source_page;
  if (page != null) return `page ${page}`;
  return '';
}

function prettyDate(value) {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (_) {
    throw new Error(`Could not reach the backend at ${API_BASE}. Check that FastAPI is running.`);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data.error || `Request failed (${response.status}).`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

function jsonOptions(body) {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

function render() {
  const query = $('#search-input').value.trim().toLowerCase();
  const visible = sources.filter((source) => source.name.toLowerCase().includes(query));
  const topics = new Set(sources.flatMap((source) => source.topics || []));
  $('#source-count').textContent = sources.length;
  $('#unit-count').textContent = sources.reduce((sum, source) => sum + (source.unit_count || 0), 0);
  $('#topic-count').textContent = topics.size;
  $('#empty-state').classList.toggle('hidden', visible.length > 0);
  $('#empty-state').innerHTML = query
    ? '<div class="empty-icon">⌕</div><b>No matching sources</b><span>Try another search term.</span>'
    : '<div class="empty-icon">▤</div><b>Your library is ready for its first source</b><span>Upload a document or lecture video to start a grounded tutor and adaptive quiz.</span>';
  $('#source-list').innerHTML = visible.map((source) => {
    const active = source.id === activeMaterialId;
    const topicsForSource = (source.topics || []).slice(0, 3);
    const unitCount = Number(source.unit_count) || 0;
    const unit = countedUnit(source.unit_label || defaultUnit(materialType(source.name, source.type)), unitCount);
    return `<article class="source-card ${active ? 'active-source' : ''}">
      ${sourceIcon(source)}
      <div class="source-meta"><b title="${escapeHtml(source.name)}">${escapeHtml(source.name)}</b><small>Added ${prettyDate(source.uploaded_at)} · ${unitCount} processed ${escapeHtml(unit)}</small></div>
      <div class="source-topics">${topicsForSource.map((topic) => `<span class="topic-pill">${escapeHtml(topic)}</span>`).join('')}</div>
      <div class="source-actions"><button class="source-select" data-select-material="${escapeHtml(source.id)}" ${active ? 'aria-pressed="true"' : 'aria-pressed="false"'}>${active ? 'Selected' : 'Use this course'}</button></div>
    </article>`;
  }).join('');
  renderTutorSources();
}

function renderTutorSources() {
  const count = $('#tutor-source-count');
  if (!count) return;
  count.textContent = sources.length;
  $('#tutor-sources').innerHTML = sources.length
    ? sources.map((source) => `<button class="tutor-source ${source.id === activeMaterialId ? 'selected-tutor-source' : ''}" data-select-material="${escapeHtml(source.id)}">${sourceIcon(source, true)}<span title="${escapeHtml(source.name)}">${escapeHtml(source.name)}</span></button>`).join('')
    : '<p class="no-sources">Upload course material in the library to ask grounded questions.</p>';
}

function requireMaterial() {
  const material = currentMaterial();
  if (!material) throw new Error('Upload course material in Course library first, then select it as your active course.');
  return material;
}

async function loadQuizTopics() {
  const select = $('#quiz-topic');
  const previous = select.value;
  try {
    const material = requireMaterial();
    const data = await api(`/api/quiz/topics/${encodeURIComponent(material.id)}`);
    topicCache = data.topics || [];
    material.topics = topicCache.map((topic) => topic.name);
    saveMaterials();
    render();
    select.innerHTML = '<option value="">Mixed topics</option>' + topicCache.map((topic) => `<option value="${escapeHtml(topic.id)}">${escapeHtml(topic.name)}</option>`).join('');
    if (topicCache.some((topic) => topic.id === previous)) select.value = previous;
  } catch (error) {
    topicCache = [];
    select.innerHTML = '<option value="">Mixed topics</option>';
    $('#quiz-status').textContent = error.message;
  }
}

async function loadToolTopics(selectId, emptyLabel) {
  const select = $(selectId);
  const previous = select.value;
  select.innerHTML = `<option value="">${escapeHtml(emptyLabel)}</option>`;
  const material = currentMaterial();
  if (!material) return;
  const data = await api(`/api/quiz/topics/${encodeURIComponent(material.id)}`);
  const topics = data.topics || [];
  select.innerHTML = `<option value="">${escapeHtml(emptyLabel)}</option>` + topics.map((topic) => `<option value="${escapeHtml(topic.id)}">${escapeHtml(topic.name)}</option>`).join('');
  if (topics.some((topic) => topic.id === previous)) select.value = previous;
}

function renderFlashcard() {
  const session = flashcardSession;
  const section = $('#flashcard-session');
  if (!session) {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');
  if (session.index >= session.cards.length) {
    $('#flashcard-progress').textContent = `${session.cards.length} cards reviewed`;
    $('#flashcard-mode').textContent = session.mode || 'Study set complete';
    $('#flashcard-face-label').textContent = 'SESSION COMPLETE';
    $('#flashcard-face').textContent = `You marked ${session.known} of ${session.cards.length} cards as known.`;
    $('#flashcard-source').textContent = 'Generate another set to keep practicing.';
    $('#flashcard-reveal').classList.add('hidden');
    $('#flashcard-review-actions').classList.add('hidden');
    return;
  }
  const card = session.cards[session.index];
  $('#flashcard-progress').textContent = `Card ${session.index + 1} of ${session.cards.length}`;
  $('#flashcard-mode').textContent = session.mode || 'Course review';
  $('#flashcard-face-label').textContent = session.revealed ? 'ANSWER' : 'QUESTION';
  $('#flashcard-face').textContent = session.revealed ? card.back : card.front;
  $('#flashcard-source').textContent = card.source ? `Source: ${card.source}` : (card.topic || 'From your uploaded material');
  $('#flashcard-reveal').classList.toggle('hidden', session.revealed);
  $('#flashcard-review-actions').classList.toggle('hidden', !session.revealed);
}

async function generateFlashcards() {
  const material = requireMaterial();
  const status = $('#flashcard-status');
  status.textContent = 'Generating grounded flashcards…';
  $('#flashcard-session').classList.add('hidden');
  const request = {
    material_id: material.id,
    number_of_cards: Number($('#flashcard-count').value),
    weak_only: $('#flashcard-weak-only').checked,
    user_id: USER_ID,
  };
  const topicId = $('#flashcard-topic').value;
  if (topicId) request.topic_id = topicId;
  const result = await api('/api/flashcards/generate', jsonOptions(request));
  const cards = result.cards || [];
  if (!cards.length) throw new Error('No flashcards were returned for this material.');
  flashcardSession = { cards, index: 0, revealed: false, known: 0, mode: result.mode };
  status.textContent = `${cards.length} flashcards ready.`;
  renderFlashcard();
}

function renderMindmapNode(node) {
  const state = node.status ? statusClass(node.status) : '';
  const mastery = node.mastery == null ? '' : `<span class="status-chip ${state}">${Number(node.mastery)}% · ${escapeHtml(node.status || 'mastery')}</span>`;
  const source = node.source ? `<small>${escapeHtml(node.source)}</small>` : '';
  const children = node.children?.length ? `<ul>${node.children.map(renderMindmapNode).join('')}</ul>` : '';
  return `<li class="mindmap-node"><article class="mindmap-node-card ${state}"><b>${escapeHtml(node.title || 'Topic')}</b>${mastery}${source}</article>${children}</li>`;
}

async function generateMindmap(refresh = false) {
  const material = requireMaterial();
  const status = $('#mindmap-status');
  const output = $('#mindmap-output');
  status.textContent = refresh ? 'Refreshing the topic map…' : 'Building a map from your course…';
  output.innerHTML = '';
  const request = { material_id: material.id, refresh, user_id: USER_ID };
  const topicId = $('#mindmap-topic').value;
  if (topicId) request.topic_id = topicId;
  const result = await api('/api/mindmap/generate', jsonOptions(request));
  if (!result.tree) throw new Error('No topic map was returned for this material.');
  const root = result.tree;
  const children = (root.children || []).map(renderMindmapNode).join('');
  output.innerHTML = `<div class="mindmap-summary"><b>${escapeHtml(root.title || material.name)}</b><span>${Number(result.node_count) || 0} connected concepts</span><span>${result.cached ? 'Saved map' : 'Generated just now'}</span></div><ul class="mindmap-tree"><li class="mindmap-node mindmap-root"><article class="mindmap-node-card"><b>${escapeHtml(root.title || material.name)}</b></article><ul>${children}</ul></li></ul>`;
  status.textContent = 'Topic map ready.';
}

function statusClass(value) {
  return ['weak', 'developing', 'strong', 'not_started'].includes(value) ? value : 'not_started';
}

function renderTrend(items) {
  const container = $('#mastery-trend');
  if (!items?.length) {
    container.innerHTML = '<div class="dashboard-empty">Complete a quiz to start your mastery trend.</div>';
    return;
  }
  const width = 680;
  const height = 190;
  const padX = 34;
  const padY = 22;
  const points = items.map((item, index) => ({
    x: items.length === 1 ? width / 2 : padX + index * (width - padX * 2) / (items.length - 1),
    y: height - padY - Math.max(0, Math.min(100, Number(item.after))) * (height - padY * 2) / 100,
    item,
  }));
  const grid = [0, 25, 50, 75, 100].map((value) => {
    const y = height - padY - value * (height - padY * 2) / 100;
    return `<line x1="${padX}" y1="${y}" x2="${width - padX}" y2="${y}" class="trend-grid"/><text x="3" y="${y + 3}" class="trend-axis">${value}%</text>`;
  }).join('');
  const line = points.map((point) => `${point.x},${point.y}`).join(' ');
  const circles = points.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="4" class="trend-dot"><title>${escapeHtml(point.item.topic)}: ${point.item.before} → ${point.item.after}% · ${prettyDate(point.item.at)}</title></circle>`).join('');
  container.innerHTML = `<div class="trend-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Mastery changes over time">${grid}<polyline points="${line}" class="trend-line"/>${circles}</svg></div><div class="trend-caption">${escapeHtml(items[0].topic)} through ${escapeHtml(items[items.length - 1].topic)} · chronological</div>`;
}

async function loadDashboard() {
  $('#dashboard-summary').innerHTML = '<div class="dashboard-empty">Loading your progress…</div>';
  try {
    const material = currentMaterial();
    const suffix = material ? `?material_id=${encodeURIComponent(material.id)}` : '';
    const data = await api(`/api/progress/${encodeURIComponent(USER_ID)}${suffix}`);
    const recommendation = data.recommendation || {};
    const canRecommend = Boolean(recommendation.topic_id && recommendation.difficulty);
    $('#dashboard-summary').innerHTML = `
      <article class="dashboard-stat"><b>${Number(data.overall_mastery) || 0}%</b><span>Overall mastery</span></article>
      <article class="dashboard-stat"><b>${Number(data.topics_started) || 0}</b><span>Topics started</span></article>
      <article class="dashboard-stat recommendation"><span>RECOMMENDED NEXT</span><b>${escapeHtml(recommendation.message || 'Upload course material to get a recommendation.')}</b>${canRecommend ? `<button class="primary-button recommendation-quiz" data-topic-id="${escapeHtml(recommendation.topic_id)}" data-difficulty="${escapeHtml(recommendation.difficulty)}">Take recommended quiz</button>` : ''}</article>`;

    $('#mastery-list').innerHTML = data.topics?.length ? data.topics.map((item) => {
      const state = statusClass(item.status);
      const percent = item.mastery == null ? 0 : Math.max(0, Math.min(100, Number(item.mastery)));
      return `<article class="mastery-row ${state}"><div class="mastery-label"><span><b>${escapeHtml(item.name)}</b><em class="status-chip ${state}">${state.replace('_', ' ')}</em></span><span>${item.mastery == null ? 'Not started' : `${percent}% mastery`}</span></div><div class="mastery-track"><i style="width:${percent}%"></i></div><div class="mastery-detail">${item.questions_attempted || 0} questions · ${item.accuracy == null ? 'No accuracy yet' : `${item.accuracy}% accuracy`} · next: ${escapeHtml(item.recommended_difficulty || 'medium')}</div><button class="text-button teach-button" data-teach-topic="${escapeHtml(item.topic_id)}">Teach me</button></article>`;
    }).join('') : '<div class="dashboard-empty">Upload course material to see topic mastery.</div>';

    $('#attempt-list').innerHTML = data.recent_attempts?.length ? data.recent_attempts.map((attempt) => `<article class="attempt-row"><span class="attempt-icon">◷</span><span class="attempt-meta"><b>${escapeHtml(attempt.topic || 'Mixed topics')} quiz</b><small>${prettyDate(attempt.taken_at)} · ${escapeHtml(attempt.difficulty || 'adaptive')}</small></span><span class="attempt-score">${attempt.score}% <small>(${attempt.correct}/${attempt.total})</small></span></article>`).join('') : '<div class="dashboard-empty">Quiz results will appear here after your first attempt.</div>';
    $('#dashboard-topic-chips').innerHTML = `<div class="topic-chip-group"><b>Strong</b>${(data.strong_topics || []).map((topic) => `<span class="status-chip strong">${escapeHtml(topic)}</span>`).join('') || '<span class="muted-chip">None yet</span>'}</div><div class="topic-chip-group"><b>Needs practice</b>${(data.weak_topics || []).map((topic) => `<span class="status-chip weak">${escapeHtml(topic)}</span>`).join('') || '<span class="muted-chip">None</span>'}</div>`;
    renderTrend(data.mastery_trend || []);
  } catch (error) {
    $('#dashboard-summary').innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message)}</div>`;
    $('#mastery-list').innerHTML = '';
    $('#attempt-list').innerHTML = '';
    $('#dashboard-topic-chips').innerHTML = '';
    renderTrend([]);
  }
}

function setActiveMaterial(id) {
  activeMaterialId = id;
  topicCache = [];
  saveMaterials();
  render();
  $('#quiz-topic').innerHTML = '<option value="">Mixed topics</option>';
  if (!$('#quiz-page').classList.contains('hidden')) loadQuizTopics();
  if (!$('#dashboard-page').classList.contains('hidden')) loadDashboard();
  if (!flashcardsPage.classList.contains('hidden')) {
    flashcardSession = null;
    renderFlashcard();
    loadToolTopics('#flashcard-topic', 'All topics').catch((error) => { $('#flashcard-status').textContent = error.message; });
  }
  if (!mindmapPage.classList.contains('hidden')) {
    $('#mindmap-output').innerHTML = '';
    loadToolTopics('#mindmap-topic', 'Whole course').catch((error) => { $('#mindmap-status').textContent = error.message; });
  }
}

function showView(view) {
  if (!['library', 'tutor', 'quiz', 'dashboard', 'flashcards', 'mindmap'].includes(view)) view = 'library';
  libraryPage.classList.toggle('hidden', view !== 'library');
  tutorPage.classList.toggle('hidden', view !== 'tutor');
  quizPage.classList.toggle('hidden', view !== 'quiz');
  dashboardPage.classList.toggle('hidden', view !== 'dashboard');
  flashcardsPage.classList.toggle('hidden', view !== 'flashcards');
  mindmapPage.classList.toggle('hidden', view !== 'mindmap');
  document.querySelectorAll('.nav-item[data-view]').forEach((button) => button.classList.toggle('selected', button.dataset.view === view));
  $('.breadcrumb b').textContent = ({ tutor: 'Ask your tutor', quiz: 'Practice quiz', dashboard: 'My progress', flashcards: 'Flashcards', mindmap: 'Topic map' })[view] || 'Course library';
  if (view === 'tutor') $('#question-input').focus();
  if (view === 'quiz') loadQuizTopics();
  if (view === 'dashboard') loadDashboard();
  if (view === 'flashcards') loadToolTopics('#flashcard-topic', 'All topics').catch((error) => { $('#flashcard-status').textContent = error.message; });
  if (view === 'mindmap') loadToolTopics('#mindmap-topic', 'Whole course').catch((error) => { $('#mindmap-status').textContent = error.message; });
}

function addQuestion(text) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message student-message';
  const bubble = document.createElement('div');
  bubble.className = 'student-bubble';
  bubble.textContent = text;
  wrapper.append(bubble);
  $('#chat-messages').append(wrapper);
  wrapper.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function addTutorAnswer(result) {
  const grounded = Boolean(result.grounded);
  const wrapper = document.createElement('div');
  wrapper.className = `message tutor-message ${grounded ? '' : 'unsupported-message'}`;
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = grounded ? '✳' : '!';
  const body = document.createElement('div');
  body.className = 'message-body';
  const answer = document.createElement('p');
  answer.textContent = result.answer || 'No answer was returned.';
  body.append(answer);
  for (const citation of result.sources || []) {
    const card = document.createElement('article');
    card.className = 'citation-card';
    const title = document.createElement('b');
    const location = citationLocation(citation);
    title.textContent = location
      ? `${currentMaterial()?.name || 'Uploaded material'} · ${location}`
      : (currentMaterial()?.name || 'Uploaded material');
    const excerpt = document.createElement('blockquote');
    excerpt.textContent = citation.text || '';
    const similarity = document.createElement('span');
    similarity.className = 'citation-topic';
    similarity.textContent = `Source match ${Math.round((Number(citation.similarity) || 0) * 100)}%`;
    card.append(title, excerpt, similarity);
    body.append(card);
  }
  const label = document.createElement('small');
  label.textContent = grounded ? 'Based on uploaded material' : 'Not supported by the uploaded material';
  body.append(label);
  wrapper.append(avatar, body);
  $('#chat-messages').append(wrapper);
  wrapper.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

async function upload(file) {
  if (!file) return;
  status.classList.remove('error');
  const selectedType = materialType(file.name);
  if (!selectedType) {
    status.classList.add('error');
    status.textContent = 'Supported files: PDF, PPTX, MP4, MOV, MKV, WEBM, and M4V.';
    input.value = '';
    return;
  }
  status.textContent = `Uploading and processing ${file.name}…`;
  const form = new FormData();
  form.append('file', file);
  try {
    const result = await api('/api/materials/upload', { method: 'POST', body: form });
    const type = materialType(file.name, result.file_type) || selectedType;
    const unitCount = Number(result.units_processed ?? result.pages_processed ?? result.chunks_created ?? 0);
    const material = {
      id: result.material_id,
      name: file.name,
      type,
      uploaded_at: new Date().toISOString(),
      unit_count: unitCount,
      unit_label: result.unit || defaultUnit(type),
      topics: [],
    };
    sources = [material, ...sources.filter((item) => item.id !== material.id)];
    activeMaterialId = material.id;
    saveMaterials();
    render();
    const chunkCount = Number(result.chunks_created) || 0;
    status.textContent = `Added ${file.name} — ${unitCount} ${countedUnit(material.unit_label, unitCount)} processed${chunkCount ? `, ${chunkCount} chunks created` : ''}.`;
  } catch (error) {
    status.classList.add('error');
    status.textContent = error.message;
  } finally {
    input.value = '';
  }
}

async function generateQuiz({ topicId = '', difficulty = $('#quiz-difficulty').value } = {}) {
  const material = requireMaterial();
  $('#quiz-status').textContent = 'Building a quiz from your uploaded material…';
  $('#quiz-form').classList.add('hidden');
  $('#quiz-results').classList.add('hidden');
  const request = {
    material_id: material.id,
    difficulty,
    number_of_questions: Number($('#quiz-count').value),
    user_id: USER_ID,
  };
  if (topicId || $('#quiz-topic').value) request.topic_id = topicId || $('#quiz-topic').value;
  const quiz = await api('/api/quiz/generate', jsonOptions(request));
  activeQuizId = quiz.quiz_id;
  $('#quiz-questions').innerHTML = (quiz.questions || []).map((question, index) => {
    const options = (question.options || []).map((choice, optionIndex) => {
      const letter = String.fromCharCode(65 + optionIndex);
      return `<label class="quiz-option"><input type="radio" name="${escapeHtml(question.question_id)}" value="${letter}" required><span><b>${letter}.</b> ${escapeHtml(choice)}</span></label>`;
    }).join('');
    return `<article class="quiz-question" data-question-id="${escapeHtml(question.question_id)}"><div class="question-top"><span>QUESTION ${index + 1}</span><span class="question-type">${escapeHtml(question.topic || 'Course topic')}</span></div><h2>${escapeHtml(question.question)}</h2><div class="quiz-options">${options}</div></article>`;
  }).join('');
  $('#quiz-status').textContent = `${quiz.questions?.length || 0} questions · ${quiz.difficulty} difficulty${quiz.adaptive ? ' · adapted to your progress' : ''}`;
  $('#quiz-form').classList.remove('hidden');
  $('#quiz-form').scrollIntoView({ block: 'start', behavior: 'smooth' });
}

function optionText(options, letter) {
  const index = String(letter || '').toUpperCase().charCodeAt(0) - 65;
  return index >= 0 && index < (options || []).length ? `${String.fromCharCode(65 + index)}. ${options[index]}` : 'No answer';
}

function renderQuizResults(result) {
  const cards = (result.results || []).map((item, index) => {
    const correct = Boolean(item.is_correct);
    const materialName = currentMaterial()?.name || 'Uploaded material';
    const location = citationLocation(item);
    const citation = location ? `${materialName} · ${location}` : materialName;
    return `<article class="result-question ${correct ? 'correct' : 'incorrect'}"><div class="question-top"><span>QUESTION ${index + 1} · ${escapeHtml(item.topic || 'Topic')}</span><b>${correct ? 'Correct' : 'Review this'}</b></div><h2>${escapeHtml(item.question)}</h2><p><strong>Your answer:</strong> ${escapeHtml(optionText(item.options, item.your_answer))}</p><p><strong>Correct answer:</strong> ${escapeHtml(optionText(item.options, item.correct_answer))}</p><blockquote>${escapeHtml(item.explanation || 'Review the cited material for the explanation.')}</blockquote><span class="result-citation">${escapeHtml(citation)}</span></article>`;
  }).join('');
  const changes = (result.mastery_changes || []).map((item) => `<span class="mastery-change">${escapeHtml(item.topic)}: ${item.before ?? '—'} → ${item.after ?? '—'} (${item.change > 0 ? '+' : ''}${item.change ?? 0}) · next ${escapeHtml(item.next_difficulty || 'medium')}</span>`).join('');
  const breakdown = (result.topic_breakdown || []).map((item) => `<span class="status-chip ${statusClass(item.status)}">${escapeHtml(item.topic)} · ${item.accuracy}%</span>`).join('');
  $('#quiz-results').innerHTML = `<div class="score-card"><div class="score-number">${Number(result.score) || 0}<span>%</span></div><div><b>Quiz complete · ${result.correct ?? 0}/${result.total ?? 0} correct</b><small>${escapeHtml(result.recommendation || 'Your progress has been saved.')}</small></div></div><div class="weak-topic-note"><b>Weak topics:</b> ${(result.weak_topics || []).map(escapeHtml).join(', ') || 'None'}<br><b>Strong topics:</b> ${(result.strong_topics || []).map(escapeHtml).join(', ') || 'Keep practicing to build mastery.'}</div><div class="result-breakdown">${breakdown}</div>${changes ? `<section class="mastery-change-box"><b>Mastery changes</b><div>${changes}</div></section>` : ''}${cards}<button type="button" class="secondary-button" id="new-quiz">Try another quiz</button>`;
  $('#quiz-results').classList.remove('hidden');
  $('#quiz-results').scrollIntoView({ block: 'start', behavior: 'smooth' });
  $('#new-quiz').addEventListener('click', () => {
    $('#quiz-results').classList.add('hidden');
    $('#quiz-status').textContent = 'Choose your settings to build another quiz.';
    if (!dashboardPage.classList.contains('hidden')) loadDashboard();
  });
}

$('#choose-file').addEventListener('click', () => input.click());
input.addEventListener('change', () => upload(input.files[0]));
$('#search-input').addEventListener('input', render);
document.querySelectorAll('.nav-item[data-view]').forEach((button) => button.addEventListener('click', () => showView(button.dataset.view)));
for (const eventName of ['dragenter', 'dragover']) zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.add('drag-over'); });
for (const eventName of ['dragleave', 'drop']) zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.remove('drag-over'); });
zone.addEventListener('drop', (event) => upload(event.dataTransfer.files[0]));

$('#flashcard-setup').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await generateFlashcards();
  } catch (error) {
    $('#flashcard-status').textContent = error.message;
  }
});

$('#flashcard-reveal').addEventListener('click', () => {
  if (!flashcardSession || flashcardSession.index >= flashcardSession.cards.length) return;
  flashcardSession.revealed = true;
  renderFlashcard();
});

$('#flashcard-review-actions').addEventListener('click', async (event) => {
  const button = event.target.closest('[data-card-review]');
  if (!button || !flashcardSession || !flashcardSession.revealed) return;
  const card = flashcardSession.cards[flashcardSession.index];
  const known = button.dataset.cardReview === 'true';
  button.disabled = true;
  try {
    await api('/api/flashcards/review', jsonOptions({ card_id: card.card_id, known, user_id: USER_ID }));
    if (known) flashcardSession.known += 1;
    flashcardSession.index += 1;
    flashcardSession.revealed = false;
    renderFlashcard();
  } catch (error) {
    $('#flashcard-status').textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

$('#mindmap-setup').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await generateMindmap(false);
  } catch (error) {
    $('#mindmap-status').textContent = error.message;
  }
});

$('#mindmap-refresh').addEventListener('click', async () => {
  try {
    await generateMindmap(true);
  } catch (error) {
    $('#mindmap-status').textContent = error.message;
  }
});

document.addEventListener('click', async (event) => {
  const materialButton = event.target.closest('[data-select-material]');
  if (materialButton) {
    setActiveMaterial(materialButton.dataset.selectMaterial);
    status.textContent = `Active course: ${currentMaterial()?.name || 'selected'}.`;
    return;
  }
  const teachButton = event.target.closest('[data-teach-topic]');
  if (teachButton) {
    const button = teachButton;
    button.disabled = true;
    button.textContent = 'Preparing lesson…';
    const output = $('#teach-output');
    output.classList.remove('hidden');
    output.innerHTML = '<div class="dashboard-empty">Building a lesson from your course material…</div>';
    try {
      const lesson = await api('/api/tutor/teach', jsonOptions({ topic_id: button.dataset.teachTopic, user_id: USER_ID }));
      const citations = (lesson.sources || []).map((source) => `<article class="citation-card"><b>${escapeHtml(citationLocation(source) || 'Source location')}</b><blockquote>${escapeHtml(source.text || '')}</blockquote></article>`).join('');
      output.innerHTML = `<div class="teach-heading"><div><span class="eyebrow">${escapeHtml(lesson.level || 'personalized')} EXPLANATION</span><h2>${escapeHtml(lesson.topic || 'Topic lesson')}</h2></div><span class="status-chip ${lesson.grounded ? 'strong' : 'weak'}">${lesson.grounded ? 'Grounded' : 'Not covered'}</span></div><p class="teach-lesson">${escapeHtml(lesson.lesson || '')}</p>${citations ? `<div class="teach-citations"><b>Sources</b>${citations}</div>` : ''}`;
      output.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } catch (error) {
      output.innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message)}</div>`;
    } finally {
      button.disabled = false;
      button.textContent = 'Teach me';
    }
    return;
  }
  const recommended = event.target.closest('[data-topic-id][data-difficulty]');
  if (recommended) {
    showView('quiz');
    try {
      await loadQuizTopics();
      await generateQuiz({ topicId: recommended.dataset.topicId, difficulty: recommended.dataset.difficulty });
    } catch (error) {
      $('#quiz-status').textContent = error.message;
    }
  }
});

$('#chat-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = $('#question-input').value.trim();
  if (!question) return;
  addQuestion(question);
  $('#question-input').value = '';
  const button = $('#chat-form button');
  button.disabled = true;
  button.textContent = '…';
  try {
    const material = requireMaterial();
    const result = await api('/api/tutor/ask', jsonOptions({ material_id: material.id, question }));
    addTutorAnswer(result);
  } catch (error) {
    addTutorAnswer({ grounded: false, answer: error.message, sources: [] });
  } finally {
    button.disabled = false;
    button.textContent = '↑';
    $('#question-input').focus();
  }
});

$('#question-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    $('#chat-form').requestSubmit();
  }
});

$('#quiz-setup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await generateQuiz();
  } catch (error) {
    $('#quiz-status').textContent = error.message;
  }
});

$('#quiz-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!activeQuizId) return;
  const submitButton = $('#quiz-form button[type="submit"]');
  submitButton.disabled = true;
  const answers = [...document.querySelectorAll('.quiz-question')].map((card) => ({
    question_id: card.dataset.questionId,
    answer: card.querySelector('input[type="radio"]:checked')?.value || '',
  }));
  try {
    const result = await api('/api/quiz/submit', jsonOptions({ quiz_id: activeQuizId, answers, user_id: USER_ID }));
    activeQuizId = null;
    $('#quiz-form').classList.add('hidden');
    renderQuizResults(result);
  } catch (error) {
    $('#quiz-status').textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

render();
if (!sources.some((source) => source.id === activeMaterialId)) {
  activeMaterialId = sources[0]?.id || '';
  saveMaterials();
}
