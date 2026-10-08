const $ = (selector) => document.querySelector(selector);
const input = $('#file-input');
const zone = $('#drop-zone');
const status = $('#upload-status');
const libraryPage = $('.main-content > .page:not(#tutor-page)');
const tutorPage = $('#tutor-page');
const quizPage = $('#quiz-page');
const dashboardPage = $('#dashboard-page');
let sources = [];
let activeQuizId = null;

function prettyDate(value) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

function render() {
  const query = $('#search-input').value.trim().toLowerCase();
  const visible = sources.filter((source) => source.name.toLowerCase().includes(query));
  const topics = new Set(sources.flatMap((source) => source.units.map((unit) => unit.topic)));
  $('#source-count').textContent = sources.length;
  $('#unit-count').textContent = sources.reduce((sum, source) => sum + source.unit_count, 0);
  $('#topic-count').textContent = topics.size;
  $('#empty-state').classList.toggle('hidden', visible.length > 0);
  $('#empty-state').innerHTML = query
    ? '<div class="empty-icon">⌕</div><b>No matching sources</b><span>Try another search term.</span>'
    : '<div class="empty-icon">▤</div><b>Your library is ready for its first source</b><span>Upload slides, a reading, or a lecture transcript to get started.</span>';
  $('#source-list').innerHTML = visible.map((source) => {
    const topicsForSource = [...new Set(source.units.map((unit) => unit.topic))].slice(0, 3);
    const suffix = source.unit_count === 1 ? 'unit' : 'units';
    return `<article class="source-card">
      <div class="file-icon ${escapeHtml(source.type)}">${escapeHtml(source.type.toUpperCase())}</div>
      <div class="source-meta"><b title="${escapeHtml(source.name)}">${escapeHtml(source.name)}</b><small>Added ${prettyDate(source.uploaded_at)} · ${source.unit_count} linked ${suffix}</small></div>
      <div class="source-topics">${topicsForSource.map((topic) => `<span class="topic-pill">${escapeHtml(topic)}</span>`).join('')}</div>
      <div class="source-actions"><span class="unit-count">${source.unit_count} ${suffix}</span><button class="delete-button" data-delete="${source.id}" aria-label="Remove ${escapeHtml(source.name)}" title="Remove source">×</button></div>
    </article>`;
  }).join('');
  renderTutorSources();
}

function renderTutorSources() {
  const count = $('#tutor-source-count');
  if (!count) return;
  count.textContent = sources.length;
  $('#tutor-sources').innerHTML = sources.length
    ? sources.map((source) => `<div class="tutor-source"><span class="tiny-file ${escapeHtml(source.type)}">${escapeHtml(source.type.toUpperCase())}</span><span title="${escapeHtml(source.name)}">${escapeHtml(source.name)}</span></div>`).join('')
    : '<p class="no-sources">Upload course material in the library to ask grounded questions.</p>';
}

async function loadQuizTopics() {
  try {
    const response = await fetch('/api/quiz/topics');
    const data = await response.json();
    $('#quiz-topic').innerHTML = '<option value="">All topics</option>' + (data.topics || []).map((topic) => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`).join('');
  } catch (_) {
    // The quiz view explains connection problems through its status area.
  }
}

async function loadDashboard() {
  try {
    const response = await fetch('/api/dashboard');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load progress.');
    $('#dashboard-summary').innerHTML = `<article class="dashboard-stat"><b>${data.attempt_count}</b><span>Quizzes completed</span></article><article class="dashboard-stat recommendation"><span>RECOMMENDED NEXT</span><b>${escapeHtml(data.next_topic || 'Upload course material')}</b></article>`;
    $('#mastery-list').innerHTML = data.topics.length ? data.topics.map((item) => {
      const percent = Math.round(item.mastery * 100);
      return `<article class="mastery-row"><div class="mastery-label"><b>${escapeHtml(item.topic)}</b><span>${percent}%</span></div><div class="mastery-track"><i style="width:${percent}%"></i></div></article>`;
    }).join('') : '<div class="dashboard-empty">Upload course material to see topic mastery.</div>';
    $('#attempt-list').innerHTML = data.attempts.length ? data.attempts.map((attempt) => {
      const date = new Date(attempt.submitted_at);
      return `<article class="attempt-row"><span class="attempt-icon">◷</span><span class="attempt-meta"><b>${escapeHtml(attempt.topic || 'All topics')} quiz</b><small>${date.toLocaleDateString()} · ${escapeHtml(attempt.difficulty)}</small></span><span class="attempt-score">${attempt.score}/${attempt.total}</span></article>`;
    }).join('') : '<div class="dashboard-empty">Quiz results will appear here after your first attempt.</div>';
  } catch (error) {
    $('#dashboard-summary').innerHTML = `<div class="dashboard-empty">${escapeHtml(error.message)}</div>`;
  }
}

async function refresh() {
  const response = await fetch('/api/sources');
  const data = await response.json();
  sources = data.sources || [];
  render();
}

async function upload(file) {
  if (!file) return;
  status.classList.remove('error');
  status.textContent = `Reading ${file.name}…`;
  const form = new FormData();
  form.append('file', file);
  try {
    const response = await fetch('/api/sources', { method: 'POST', body: form });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Upload failed.');
    await refresh();
    status.textContent = `Added ${file.name} — ${result.source.unit_count} linked content units.`;
  } catch (error) {
    status.classList.add('error');
    status.textContent = error.message;
  } finally {
    input.value = '';
  }
}

function showView(view) {
  if (!['library', 'tutor', 'quiz', 'dashboard'].includes(view)) view = 'library';
  libraryPage.classList.toggle('hidden', view !== 'library');
  tutorPage.classList.toggle('hidden', view !== 'tutor');
  quizPage.classList.toggle('hidden', view !== 'quiz');
  dashboardPage.classList.toggle('hidden', view !== 'dashboard');
  document.querySelectorAll('.nav-item[data-view]').forEach((button) => button.classList.toggle('selected', button.dataset.view === view));
  $('.breadcrumb b').textContent = view === 'tutor' ? 'Ask your tutor' : view === 'quiz' ? 'Practice quiz' : view === 'dashboard' ? 'My progress' : 'Course library';
  if (view === 'tutor') $('#question-input').focus();
  if (view === 'quiz') loadQuizTopics();
  if (view === 'dashboard') loadDashboard();
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
  const wrapper = document.createElement('div');
  wrapper.className = `message tutor-message ${result.supported ? '' : 'unsupported-message'}`;
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = result.supported ? '✳' : '!';
  const body = document.createElement('div');
  body.className = 'message-body';
  const answer = document.createElement('p');
  answer.textContent = result.answer;
  body.append(answer);
  for (const citation of result.citations || []) {
    const card = document.createElement('article');
    card.className = 'citation-card';
    const link = document.createElement('a');
    const anchor = citation.location.startsWith('page ') ? `#page=${citation.location.slice(5)}` : '';
    link.href = `/api/sources/${encodeURIComponent(citation.source_id)}/file${anchor}`;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = `${citation.source} · ${citation.location}`;
    const excerpt = document.createElement('blockquote');
    excerpt.textContent = citation.excerpt;
    const topic = document.createElement('span');
    topic.className = 'citation-topic';
    topic.textContent = citation.topic;
    card.append(link, excerpt, topic);
    body.append(card);
  }
  const label = document.createElement('small');
  label.textContent = result.supported ? 'Based on uploaded sources' : 'No matching source found';
  body.append(label);
  wrapper.append(avatar, body);
  $('#chat-messages').append(wrapper);
  wrapper.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

$('#choose-file').addEventListener('click', () => input.click());
input.addEventListener('change', () => upload(input.files[0]));
$('#search-input').addEventListener('input', render);
document.querySelectorAll('.nav-item[data-view]').forEach((button) => button.addEventListener('click', () => showView(button.dataset.view)));
$('#source-list').addEventListener('click', async (event) => {
  const button = event.target.closest('[data-delete]');
  if (!button) return;
  const response = await fetch(`/api/sources/${button.dataset.delete}`, { method: 'DELETE' });
  if (response.ok) {
    await refresh();
    status.textContent = 'Source removed.';
  }
});
for (const eventName of ['dragenter', 'dragover']) zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.add('drag-over'); });
for (const eventName of ['dragleave', 'drop']) zone.addEventListener(eventName, (event) => { event.preventDefault(); zone.classList.remove('drag-over'); });
zone.addEventListener('drop', (event) => upload(event.dataTransfer.files[0]));

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
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Tutor request failed.');
    addTutorAnswer(result);
  } catch (error) {
    addTutorAnswer({ supported: false, answer: `I couldn't reach the tutor: ${error.message}`, citations: [] });
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
  $('#quiz-status').textContent = 'Building a quiz from your course material…';
  $('#quiz-form').classList.add('hidden');
  $('#quiz-results').classList.add('hidden');
  try {
    const response = await fetch('/api/quizzes', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: $('#quiz-topic').value, difficulty: $('#quiz-difficulty').value, count: Number($('#quiz-count').value) }),
    });
    const quiz = await response.json();
    if (!response.ok) throw new Error(quiz.error || 'Could not create a quiz.');
    activeQuizId = quiz.quiz_id;
    $('#quiz-questions').innerHTML = quiz.questions.map((question, index) => {
      const inputControl = question.type === 'mcq'
        ? `<div class="quiz-options">${question.choices.map((choice) => `<label class="quiz-option"><input type="radio" name="${question.id}" value="${escapeHtml(choice)}" required><span>${escapeHtml(choice)}</span></label>`).join('')}</div>`
        : `<textarea name="${question.id}" rows="3" class="short-answer" placeholder="Write your answer…" required></textarea>`;
      return `<article class="quiz-question" data-question-id="${question.id}"><div class="question-top"><span>QUESTION ${index + 1}</span><span class="question-type">${question.type === 'mcq' ? 'MULTIPLE CHOICE' : 'SHORT ANSWER'}</span></div><h2>${escapeHtml(question.prompt)}</h2>${inputControl}<div class="question-source">${escapeHtml(question.topic)} · ${escapeHtml(question.source)} · ${escapeHtml(question.location)}</div></article>`;
    }).join('');
    $('#quiz-status').textContent = `${quiz.questions.length} questions · ${quiz.difficulty} difficulty`;
    $('#quiz-form').classList.remove('hidden');
  } catch (error) {
    $('#quiz-status').textContent = error.message;
  }
});

$('#quiz-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!activeQuizId) return;
  const answers = {};
  document.querySelectorAll('.quiz-question').forEach((card) => {
    const questionId = card.dataset.questionId;
    const selected = card.querySelector(`input[name="${questionId}"]:checked`);
    const shortAnswer = card.querySelector(`textarea[name="${questionId}"]`);
    answers[questionId] = { answer: selected ? selected.value : shortAnswer ? shortAnswer.value.trim() : '' };
  });
  try {
    const response = await fetch(`/api/quizzes/${encodeURIComponent(activeQuizId)}/submit`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not submit this quiz.');
    activeQuizId = null;
    $('#quiz-form').classList.add('hidden');
    const cards = result.results.map((item, index) => `<article class="result-question ${item.correct ? 'correct' : 'incorrect'}"><div class="question-top"><span>QUESTION ${index + 1}</span><b>${item.correct ? 'Correct' : 'Review this'}</b></div><h2>${escapeHtml(item.prompt)}</h2><p><strong>Your answer:</strong> ${escapeHtml(item.user_answer || 'No answer')}</p><p><strong>${item.correct ? 'Answer' : 'Suggested answer'}:</strong> ${escapeHtml(item.correct_answer)}</p><blockquote>${escapeHtml(item.explanation)}</blockquote><a href="/api/sources/${encodeURIComponent(item.source_id)}/file" target="_blank" rel="noopener">${escapeHtml(item.source)} · ${escapeHtml(item.location)}</a></article>`).join('');
    $('#quiz-results').innerHTML = `<div class="score-card"><div class="score-number">${result.score}<span>/${result.total}</span></div><div><b>Quiz complete</b><small>Topic mastery has been updated from this attempt.</small></div></div><div class="weak-topic-note"><b>Topics to revisit:</b> ${result.weak_topics.map(escapeHtml).join(', ') || 'Keep practicing to build a topic history.'}</div>${cards}<button type="button" class="secondary-button" id="new-quiz">Try another quiz</button>`;
    $('#quiz-results').classList.remove('hidden');
    $('#quiz-results').scrollIntoView({ block: 'start', behavior: 'smooth' });
    $('#new-quiz').addEventListener('click', () => { $('#quiz-results').classList.add('hidden'); $('#quiz-status').textContent = 'Choose your settings to build another quiz.'; });
  } catch (error) {
    $('#quiz-status').textContent = error.message;
  }
});

refresh().catch(() => { status.classList.add('error'); status.textContent = 'Could not reach the local app. Please restart the server.'; });
