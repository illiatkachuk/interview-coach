'use strict';

/* ============ helpers ============ */

const $ = (sel) => document.querySelector(sel);

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function formatDate(iso) {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

let toastTimer;
function toast(msg, kind = 'info') {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast' + (kind === 'error' ? ' error' : '');
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4500);
}

function setBusy(btn, label) {
  btn.dataset.label = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>' + escapeHtml(label);
}

function clearBusy(btn) {
  btn.disabled = false;
  if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
}

/* ============ markdown (escape-first, XSS-safe) ============ */

function inlineMd(s) {
  let t = escapeHtml(s);
  const codes = [];
  t = t.replace(/`([^`]+)`/g, (_, c) => {
    codes.push('<code>' + c + '</code>');
    return '\u0001' + (codes.length - 1) + '\u0001';
  });
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
  t = t.replace(/\u0001(\d+)\u0001/g, (_, n) => codes[n]);
  return t;
}

function renderMarkdown(src) {
  const stash = [];
  const text = String(src).replace(/```[^\n]*\n([\s\S]*?)```/g, (_, code) => {
    stash.push('<pre class="codeblock"><code>' + escapeHtml(code.replace(/\n$/, '')) + '</code></pre>');
    return '\u0000' + (stash.length - 1) + '\u0000';
  });

  const lines = text.split('\n');
  const out = [];
  let i = 0;
  const isSpecial = (l) =>
    /^\s*$/.test(l) || /^#{1,6}\s/.test(l) || /^\s*[-*]\s+/.test(l) ||
    /^\s*\d+[.)]\s+/.test(l) || /^\s*>/.test(l) || /^\u0000\d+\u0000\s*$/.test(l.trim()) ||
    /^(-{3,}|\*{3,}|_{3,})\s*$/.test(l);

  while (i < lines.length) {
    const line = lines[i];
    let m;
    if (/^\s*$/.test(line)) { i++; continue; }
    if (/^\u0000\d+\u0000\s*$/.test(line.trim())) { out.push(line.trim()); i++; continue; }
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
      const level = Math.min(m[1].length + 1, 6);
      out.push(`<h${level}>` + inlineMd(m[2]) + `</h${level}>`);
      i++; continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { out.push('<hr>'); i++; continue; }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push('<li>' + inlineMd(lines[i].replace(/^\s*[-*]\s+/, '')) + '</li>');
        i++;
      }
      out.push('<ul>' + items.join('') + '</ul>');
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push('<li>' + inlineMd(lines[i].replace(/^\s*\d+[.)]\s+/, '')) + '</li>');
        i++;
      }
      out.push('<ol>' + items.join('') + '</ol>');
      continue;
    }
    if (/^\s*>/.test(line)) {
      const quote = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ''));
        i++;
      }
      out.push('<blockquote>' + inlineMd(quote.join(' ')) + '</blockquote>');
      continue;
    }
    const para = [];
    while (i < lines.length && !isSpecial(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    out.push('<p>' + inlineMd(para.join(' ')) + '</p>');
  }

  return out.join('\n').replace(/\u0000(\d+)\u0000/g, (_, n) => stash[n]);
}

/* ============ API ============ */

async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  } catch (err) {
    throw new Error('Cannot reach the server — is it still running?');
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') detail = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0] && data.detail[0].msg) {
        detail = data.detail[0].msg;
      }
    } catch (_) { /* keep generic message */ }
    throw new Error(detail);
  }
  return res.json();
}

/* ============ state ============ */

const state = {
  problem: null,
  difficulty: 'medium',
  lang: localStorage.getItem('ic:lang') || 'en',
};

const TOPICS = [
  'arrays', 'strings', 'dynamic-programming', 'graphs', 'trees',
  'binary-search', 'hash-maps', 'recursion', 'sorting', 'greedy',
];

const VERDICTS = {
  correct: { cls: 'ok', emoji: '✅', label: 'Correct' },
  partially_correct: { cls: 'warn', emoji: '🟡', label: 'Partially correct' },
  incorrect: { cls: 'bad', emoji: '❌', label: 'Incorrect' },
};

/* ============ views ============ */

function showView(name) {
  $('#view-practice').hidden = name !== 'practice';
  $('#view-history').hidden = name !== 'history';
  $('#nav-practice').classList.toggle('active', name === 'practice');
  $('#nav-history').classList.toggle('active', name === 'history');
  if (name === 'history') loadHistory();
  window.scrollTo({ top: 0 });
}

function showGenerator() {
  state.problem = null;
  $('#generator').hidden = false;
  $('#workspace').hidden = true;
}

function openProblem(problem) {
  state.problem = problem;
  $('#generator').hidden = true;
  $('#workspace').hidden = false;
  $('#problem-title').textContent = problem.title;
  $('#problem-badges').innerHTML =
    `<span class="badge">${escapeHtml(problem.topic)}</span>` +
    `<span class="badge diff-${escapeHtml(problem.difficulty)}">${escapeHtml(problem.difficulty)}</span>`;
  $('#problem-statement').innerHTML = renderMarkdown(problem.statement);
  $('#editor').value = '';
  $('#result').hidden = true;
  $('#result').innerHTML = '';
  showView('practice');
}

/* ============ generate ============ */

async function generateProblem(event) {
  event.preventDefault();
  const topic = $('#topic-input').value.trim();
  if (!topic) { toast('Enter a topic first.', 'error'); return; }
  const btn = $('#gen-btn');
  setBusy(btn, 'Generating…');
  $('#gen-note').hidden = false;
  try {
    const problem = await api('/api/problems', {
      method: 'POST',
      body: JSON.stringify({ topic, difficulty: state.difficulty, lang: state.lang }),
    });
    openProblem(problem);
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    clearBusy(btn);
    $('#gen-note').hidden = true;
  }
}

/* ============ submit ============ */

function runOutputHtml(a) {
  const bits = [];
  if (a.timed_out) bits.push('<p class="muted small">⏱ Interrupted by timeout.</p>');
  else if (a.exit_code !== 0) bits.push(`<p class="muted small">Exited with code ${a.exit_code}.</p>`);
  const block = (label, text) => text && text.trim()
    ? `<h4>${label}</h4><pre class="codeblock"><code>${escapeHtml(text.trim())}</code></pre>`
    : '';
  const body = bits.join('') + block('stdout', a.stdout) + block('stderr', a.stderr);
  return body || '<p class="muted small">(no output)</p>';
}

function renderResult(a) {
  const box = $('#result');
  const v = VERDICTS[a.verdict];
  let head;
  if (v) {
    head = `
      <div class="verdict ${v.cls}">
        <span>${v.emoji} ${v.label}</span>
        <span class="score-wrap">
          <span>${a.score}/10</span>
          <span class="score-bar"><div style="width:${a.score * 10}%"></div></span>
        </span>
      </div>`;
  } else {
    head = `
      <div class="verdict warn">
        <span>⚠️ Feedback unavailable — the attempt was saved without review.</span>
      </div>
      ${a.llm_error ? `<p class="muted small">${escapeHtml(a.llm_error)}</p>` : ''}`;
  }
  box.innerHTML = `
    <div class="card result-card">
      ${head}
      ${a.feedback ? `<div class="md">${renderMarkdown(a.feedback)}</div>` : ''}
      <details class="run-output">
        <summary>Run output</summary>
        ${runOutputHtml(a)}
      </details>
    </div>`;
  box.hidden = false;
  box.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function submitSolution() {
  if (!state.problem) return;
  const code = $('#editor').value;
  if (!code.trim()) { toast('Write or paste a solution first.', 'error'); return; }
  const btn = $('#submit-btn');
  setBusy(btn, 'Running & reviewing…');
  try {
    const attempt = await api(`/api/problems/${state.problem.id}/attempts`, {
      method: 'POST',
      body: JSON.stringify({ code, lang: state.lang }),
    });
    renderResult(attempt);
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    clearBusy(btn);
  }
}

/* ============ history ============ */

async function loadHistory() {
  const wrap = $('#history-content');
  wrap.innerHTML = '<div class="empty">Loading…</div>';
  let problems, attempts;
  try {
    [problems, attempts] = await Promise.all([api('/api/problems'), api('/api/attempts')]);
  } catch (err) {
    wrap.innerHTML = `<div class="empty">${escapeHtml(err.message)}</div>`;
    return;
  }

  if (!problems.length) {
    wrap.innerHTML = `
      <div class="empty">
        <p>Nothing here yet — generate your first problem to get started.</p>
        <button class="btn btn-primary" id="empty-cta" type="button">Generate a problem</button>
      </div>`;
    $('#empty-cta').addEventListener('click', () => { showGenerator(); showView('practice'); });
    return;
  }

  const counts = {};
  for (const a of attempts) counts[a.problem_id] = (counts[a.problem_id] || 0) + 1;

  const problemsHtml = [...problems].reverse().map((p) => `
    <div class="card problem-row">
      <div class="problem-row-info">
        <strong>${escapeHtml(p.title)}</strong>
        <span class="muted small">
          ${escapeHtml(p.topic)} · ${escapeHtml(p.difficulty)} · ${formatDate(p.created_at)}
          · ${counts[p.id] || 0} attempt${(counts[p.id] || 0) === 1 ? '' : 's'}
        </span>
      </div>
      <button class="btn btn-ghost" data-open-problem="${p.id}" type="button">Solve</button>
    </div>`).join('');

  const attemptsHtml = attempts.length
    ? [...attempts].reverse().map((a) => {
        const v = VERDICTS[a.verdict];
        const emoji = v ? v.emoji : '⚪';
        const chip = v
          ? `<span class="score-chip ${v.cls}">${a.score}/10</span>`
          : '<span class="score-chip none">no feedback</span>';
        return `
          <div class="card attempt" data-attempt="${a.id}">
            <button class="attempt-head" type="button">
              <span class="attempt-emoji">${emoji}</span>
              <span class="attempt-info">
                <strong>${escapeHtml(a.problem_title)}</strong>
                <span class="muted small">${formatDate(a.created_at)}</span>
              </span>
              ${chip}
              <span class="chev">▾</span>
            </button>
            <div class="attempt-body" hidden>
              ${a.feedback
                ? `<div class="md">${renderMarkdown(a.feedback)}</div>`
                : '<p class="muted small">No feedback was saved for this attempt.</p>'}
              <h4>Code</h4>
              <pre class="codeblock"><code>${escapeHtml(a.solution_code)}</code></pre>
              <details class="run-output">
                <summary>Run output</summary>
                ${runOutputHtml(a)}
              </details>
            </div>
          </div>`;
      }).join('')
    : '<p class="muted">No attempts yet.</p>';

  wrap.innerHTML = `
    <div class="history-section">
      <h2>Problems</h2>
      ${problemsHtml}
    </div>
    <div class="history-section">
      <h2>Attempts</h2>
      ${attemptsHtml}
    </div>`;

  wrap.querySelectorAll('[data-open-problem]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      setBusy(btn, 'Opening…');
      try {
        openProblem(await api(`/api/problems/${btn.dataset.openProblem}`));
      } catch (err) {
        toast(err.message, 'error');
        clearBusy(btn);
      }
    });
  });

  wrap.querySelectorAll('.attempt-head').forEach((head) => {
    head.addEventListener('click', () => {
      const card = head.closest('.attempt');
      const body = card.querySelector('.attempt-body');
      body.hidden = !body.hidden;
      card.classList.toggle('open', !body.hidden);
    });
  });
}

/* ============ wiring ============ */

function init() {
  const chipsWrap = $('#topic-chips');
  for (const topic of TOPICS) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip';
    chip.textContent = topic;
    chip.addEventListener('click', () => { $('#topic-input').value = topic; });
    chipsWrap.appendChild(chip);
  }

  $('#difficulty-seg').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-value]');
    if (!btn) return;
    state.difficulty = btn.dataset.value;
    $('#difficulty-seg').querySelectorAll('button').forEach((b) => {
      b.classList.toggle('active', b === btn);
    });
  });

  const langSelect = $('#lang-select');
  langSelect.value = state.lang;
  langSelect.addEventListener('change', () => {
    state.lang = langSelect.value;
    localStorage.setItem('ic:lang', state.lang);
  });

  $('#gen-form').addEventListener('submit', generateProblem);
  $('#submit-btn').addEventListener('click', submitSolution);
  $('#back-btn').addEventListener('click', showGenerator);
  $('#brand').addEventListener('click', (e) => { e.preventDefault(); showView('practice'); });
  $('#nav-practice').addEventListener('click', () => showView('practice'));
  $('#nav-history').addEventListener('click', () => showView('history'));

  const editor = $('#editor');
  editor.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = editor.selectionStart;
      const end = editor.selectionEnd;
      editor.value = editor.value.slice(0, start) + '    ' + editor.value.slice(end);
      editor.selectionStart = editor.selectionEnd = start + 4;
    } else if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      submitSolution();
    }
  });
}

init();
