/* Vidyashilp Guide — UI layer (v2). Loaded before app.js.
   app.js keeps the chat/conversation logic; this file owns everything the user
   sees around it. Exposes window.UI. No external libraries (works offline). */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };

  const DEMO = [
    ['STU_016', 'Ready for Machine Learning; Deep Learning is conditional'],
    ['STU_017', 'Failed MATH301, so blocked from Machine Learning'],
    ['STU_010', 'Economics minor with a prerequisite conflict'],
    ['STU_022', 'CGPA below 5.00: Year 3 progression risk'],
    ['STU_004', 'Registration hold (privacy demo)'],
    ['STU_043', 'Batch 2021: no curriculum data'],
    ['ADVISOR_01', 'Faculty advisor for STU_001–STU_012', '2468'],
  ];
  const SUGGEST = {
    guest: [
      'What is the minimum attendance to sit the end-term exam?',
      'What are the prerequisites for Machine Learning (DATA301) for the 2024 batch?',
      'Can I register late for a non-medical reason?',
      'How many credits can I take in the summer term?',
      'What CGPA do I need to graduate with distinction?',
    ],
    student: [
      'Can I take Deep Learning (DATA302) next semester?',
      'How many credits have I earned, and what is left?',
      'Will I be promoted to the next year?',
      'Which courses can I take next semester?',
      'Can I graduate on time?',
    ],
    advisor: [
      'Summarise this student\'s academic progress.',
      'Which courses is this student currently blocked from, and why?',
      'Does this student meet the progression criteria?',
    ],
  };
  const DECISIONS = {
    'ELIGIBLE': ['ok', '✓ Eligible'], 'NOT ELIGIBLE': ['bad', '✕ Not eligible'],
    'CONDITIONAL': ['warn', '◐ Conditional'], 'NEEDS REVIEW': ['warn', '⚠ Needs review'],
    'NOT IN CURRICULUM': ['info', 'ℹ Not in your curriculum'], 'ALREADY PASSED': ['info', '✓ Already passed'],
    'CURRENTLY REGISTERED': ['info', 'ℹ Already registered'], 'NO DATA FOR BATCH': ['warn', '⚠ No data for your batch'],
  };

  let me = null;  // signed-in user (from /api/me)

  // ------------------------------------------------------------------ toasts
  function toast(message, kind = '', ms = 4200) {
    const t = el('div', 'toast ' + kind, message);
    t.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    $('toasts').appendChild(t);
    setTimeout(() => t.remove(), ms);
  }

  // ------------------------------------------------------------------ markdown (escape first, then format)
  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function inline(s) {
    let h = esc(s);
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>');
    h = h.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>');
    h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    h = h.replace(/(https?:\/\/[^\s<]+[^\s<.,;:)])/g, (m, url, off, str) =>
      (str.slice(Math.max(0, off - 6), off).includes('href="') ? m : `<a href="${url}" target="_blank" rel="noopener">${url}</a>`));
    // evidence citations: [E1] or [E1, E2]
    h = h.replace(/\[((?:E\d+)(?:\s*,\s*E\d+)*)\]/g, (m, ids) => ids.split(/\s*,\s*/)
      .map((id) => `<button type="button" class="cite" data-cite="${id}" aria-label="Source ${id.slice(1)}">${id.slice(1)}</button>`).join(''));
    return h;
  }
  function renderMarkdown(text) {
    const lines = String(text || '').replace(/\r/g, '').split('\n');
    const out = [];
    let list = null;
    let para = [];
    const flushPara = () => { if (para.length) { out.push('<p>' + inline(para.join(' ')) + '</p>'); para = []; } };
    const flushList = () => { if (list) { out.push(`<${list.type}>` + list.items.map((i) => `<li>${inline(i)}</li>`).join('') + `</${list.type}>`); list = null; } };
    lines.forEach((raw) => {
      const line = raw.trim();
      let m;
      if (!line) { flushPara(); flushList(); return; }
      if ((m = line.match(/^#{1,4}\s+(.*)$/))) { flushPara(); flushList(); out.push('<h3>' + inline(m[1]) + '</h3>'); return; }
      if ((m = line.match(/^[-*•]\s+(.*)$/))) { flushPara(); if (!list || list.type !== 'ul') { flushList(); list = { type: 'ul', items: [] }; } list.items.push(m[1]); return; }
      if ((m = line.match(/^\d+[.)]\s+(.*)$/))) { flushPara(); if (!list || list.type !== 'ol') { flushList(); list = { type: 'ol', items: [] }; } list.items.push(m[1]); return; }
      if (list && /^\s{2,}/.test(raw)) { list.items[list.items.length - 1] += ' ' + line; return; }
      flushList(); para.push(line);
    });
    flushPara(); flushList();
    return out.join('');
  }
  function splitDecision(text) {
    const m = String(text || '').match(/^\s*\**\s*Decision:\s*([A-Z_ ]+?)\s*\**(?:\s+for\s+([A-Z]{4}\d{3}))?\s*(\n|$)/);
    if (!m) return { decision: null, rest: text };
    return { decision: m[1].replace(/_/g, ' ').trim(), course: m[2] || null, rest: text.slice(m[0].length) };
  }
  function renderAnswer(text) {
    const { decision, course, rest } = splitDecision(text);
    let html = '';
    if (decision) {
      const [kind, label] = DECISIONS[decision] || ['info', decision];
      const suffix = course ? ` · ${esc(course)}` : '';
      html += `<div class="decision ${kind}" role="note" aria-label="Decision: ${esc(decision.toLowerCase())}${course ? ' for ' + esc(course) : ''}">${label}${suffix}</div>`;
    }
    return html + renderMarkdown(rest);
  }
  function plain(text) {
    return String(text || '').replace(/\[E\d+(?:\s*,\s*E\d+)*\]/g, '').replace(/[*_#`>]/g, '')
      .replace(/Decision:\s*/i, 'Decision: ').replace(/\s+/g, ' ').trim();
  }

  // ------------------------------------------------------------------ welcome
  function renderWelcome(container) {
    const role = !me ? 'guest' : me.role;
    const who = !me ? '' : (me.role === 'advisor' ? `, ${me.username}` : `, ${me.student_id}`);
    const sub = !me
      ? 'Ask about courses, prerequisites, credits and university regulations. Answers cite the Student Handbook, SOP and curriculum.'
      : me.role === 'advisor'
        ? 'Choose an advisee in the menu, then ask about their record. You only see your own advisees.'
        : `Batch ${me.profile?.batch ?? '?'} · Semester ${me.profile?.current_semester ?? '?'}${me.profile?.minor ? ' · ' + me.profile.minor + ' minor' : ''}. I can check your eligibility, credits and progress.`;
    const wrap = el('div', 'welcome');
    wrap.innerHTML = `
      <div class="welcome-hero">
        <div class="welcome-copy">
          <span class="welcome-eyebrow">VIDYASHILP GUIDE</span>
          <h2>Hello${esc(who)}</h2>
          <p>${esc(sub)}</p>
        </div>
        <div class="hero-scene" id="heroScene" aria-hidden="true"></div>
      </div>
      <p class="suggest-title">A good place to start</p>
      <div class="suggestions"></div>
      <div class="capabilities">
        <div class="capability"><span class="cap-icon" aria-hidden="true">01</span><strong>Grounded answers</strong>
          <p>Attendance, grading, progression, registration. Every answer shows where it came from.</p></div>
        <div class="capability"><span class="cap-icon" aria-hidden="true">02</span><strong>Eligibility checks</strong>
          <p>Prerequisites, credits and CGPA are checked by rule-based tools, not guessed.</p></div>
        <div class="capability"><span class="cap-icon" aria-hidden="true">03</span><strong>Useful tools</strong>
          <p>Ask by voice, listen to answers, or upload a transcript photo.</p></div>
      </div>`;
    const sug = wrap.querySelector('.suggestions');
    SUGGEST[role].forEach((q) => {
      const b = el('button', 'prompt-chip', q);
      b.type = 'button';
      b.dataset.prompt = q;
      sug.appendChild(b);
    });
    if (!me) {
      const nudge = el('div', 'signin-nudge');
      nudge.innerHTML = '<p><strong>Want personal advice?</strong> Sign in with a demo student to see eligibility checks on a record.</p>';
      const b = el('button', 'btn btn-secondary btn-sm', 'Sign in');
      b.type = 'button';
      b.addEventListener('click', openSignIn);
      nudge.appendChild(b);
      wrap.appendChild(nudge);
    }
    container.replaceChildren(wrap);
    document.dispatchEvent(new Event('vg:welcome-rendered'));
  }

  // ------------------------------------------------------------------ thinking + errors
  function listEl() {
    const chat = $('chatWindow');
    let list = chat.querySelector('.message-list');
    if (!list) { chat.replaceChildren(); list = el('div', 'message-list'); chat.appendChild(list); }
    return list;
  }
  function botShell(extraClass) {
    const wrap = el('div', 'message bot' + (extraClass ? ' ' + extraClass : ''));
    const av = el('div', 'message-avatar', 'VG');
    av.setAttribute('aria-hidden', 'true');
    const body = el('div', 'message-body');
    wrap.append(av, body);
    listEl().appendChild(wrap);
    const chat = $('chatWindow');
    chat.scrollTop = chat.scrollHeight;
    return { wrap, body };
  }
  function showThinking(mode) {
    const steps = mode === 'rag'
      ? ['Searching the handbook and curriculum…', 'Writing the answer…']
      : ['Understanding your question…', 'Looking up the regulations…', 'Checking the record and prerequisites…',
        'Writing the answer…', 'Verifying against the sources…'];
    const { wrap, body } = botShell('thinking');
    wrap.setAttribute('role', 'status');
    const bubble = el('div', 'bubble');
    const label = el('span', 'thinking-step', steps[0]);
    bubble.append(el('span', 'spinner'), label);
    body.appendChild(bubble);
    let i = 0;
    const timer = setInterval(() => { if (i < steps.length - 1) { i += 1; label.textContent = steps[i]; } }, 1700);
    return { remove() { clearInterval(timer); wrap.remove(); } };
  }
  function showError(message, { status, retry } = {}) {
    const { wrap, body } = botShell('error');
    const bubble = el('div', 'bubble');
    const busy = status === 429 || status === 503;
    bubble.appendChild(el('p', '', busy
      ? 'The free AI service is busy or out of quota right now. Your question was not lost.'
      : message));
    if (busy) bubble.appendChild(el('p', 'muted', message));
    const actions = el('div', 'error-actions');
    if (retry) {
      const r = el('button', 'btn btn-secondary btn-sm', '↻ Try again');
      r.type = 'button';
      r.addEventListener('click', () => { wrap.remove(); retry(); });
      actions.appendChild(r);
    }
    if (busy && currentMode() === 'agentic' && retry) {
      const q = el('button', 'btn btn-ghost btn-sm', 'Use Quick mode (fewer AI calls)');
      q.type = 'button';
      q.addEventListener('click', () => { setMode('rag'); wrap.remove(); retry(); });
      actions.appendChild(q);
    }
    if (actions.childElementCount) bubble.appendChild(actions);
    body.appendChild(bubble);
    scrollToEnd();
    const first = actions.querySelector('button');
    if (first) first.focus({ preventScroll: true });
  }
  function scrollToEnd() {
    const chat = $('chatWindow');
    requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });
  }

  // ------------------------------------------------------------------ answer decoration
  function decorateAnswer(wrapper, text, meta) {
    const body = wrapper.querySelector('.message-body') || wrapper;
    meta = meta || {};
    if (meta.fallback_from) {
      body.appendChild(callout('fallback', 'ℹ', `${meta.fallback_from} was busy, so ${meta.model_label || 'another model'} answered.`));
    }
    if (meta.human_review && meta.human_review.length) {
      body.appendChild(callout('human', 'Needs a human decision:', meta.human_review.join(' ')));
    }
    const sec = (meta.security_events || []).filter((e) => e !== 'login_required_for_record');
    if (sec.length) {
      const human = {
        other_student_record: 'only your own record can be used',
        prompt_injection_blocked: 'the request tried to change the advisor\'s rules',
        not_an_advisee: 'this student is not one of your advisees',
        not_logged_in: 'sign in to use a student record',
        other_student_id_removed: 'another student\'s ID was removed',
        restricted_value_removed: 'restricted personal data was removed',
        system_prompt_leak_blocked: 'internal instructions are never shared',
      };
      body.appendChild(callout('privacy', '🔒 Privacy safeguard:', sec.map((e) => human[e] || e).join('; ') + '.'));
    }

    const footer = el('div', 'answer-footer');
    const metaLine = el('span', 'answer-meta');
    const parts = [];
    if (meta.status === 'blocked') {
      parts.push('🔒 Blocked by a privacy safeguard');
    } else if (meta.mode === 'agentic') {
      parts.push(meta.status === 'verified' ? '<span class="verified">✓ Verified against sources</span>'
        : meta.status === 'unverified' ? '<span class="unverified">⚠ Partly unverified</span>' : 'Verified mode');
    } else if (meta.mode === 'rag') parts.push('Quick mode');
    if (meta.model_label) parts.push(esc(meta.model_label));
    if (meta.elapsed_ms >= 100) parts.push((meta.elapsed_ms / 1000).toFixed(1) + ' s');
    parts.push('AI guidance, not an official decision');
    metaLine.innerHTML = parts.join(' · ');
    footer.appendChild(metaLine);

    if ('speechSynthesis' in window) {
      const b = chip('🔊 Listen', 'Read this answer aloud');
      b.addEventListener('click', () => speak(text, b));
      footer.appendChild(b);
    }
    const copy = chip('⧉ Copy', 'Copy answer text');
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(plain(text)); toast('Answer copied', 'ok', 1800); } catch (e) { toast('Could not copy', 'error'); }
    });
    footer.appendChild(copy);
    const intake = (meta.trace && meta.trace[0] && meta.trace[0].course_codes) || [];
    const codes = Array.from(new Set([...intake, ...(String(text).match(/\b[A-Z]{4}\d{3}\b/g) || [])])).slice(0, 2);
    codes.forEach((code) => {
      const b = chip(`🗺 ${code} map`, `Show the prerequisite chain for ${code}`);
      b.addEventListener('click', () => showPrereqMap(code));
      footer.appendChild(b);
    });
    let panel = null;
    if ((meta.evidence && meta.evidence.length) || (meta.trace && meta.trace.length)) {
      const n = (meta.evidence || []).length;
      const toggle = chip(`📑 Sources${n ? ' (' + n + ')' : ''} & steps`, 'Show sources and how this answer was made');
      toggle.setAttribute('aria-expanded', 'false');
      panel = detailsPanel(meta);
      panel.hidden = true;
      toggle.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        toggle.setAttribute('aria-expanded', String(!panel.hidden));
      });
      footer.appendChild(toggle);
      body.appendChild(footer);
      body.appendChild(panel);
      body.querySelectorAll('.cite').forEach((c) => c.addEventListener('click', () => {
        panel.hidden = false;
        toggle.setAttribute('aria-expanded', 'true');
        const item = panel.querySelector(`[data-source="${c.dataset.cite}"]`);
        if (item) { item.classList.remove('flash'); void item.offsetWidth; item.classList.add('flash'); item.scrollIntoView({ block: 'nearest' }); }
      }));
    } else {
      body.appendChild(footer);
      body.querySelectorAll('.cite').forEach((c) => { c.disabled = true; });
    }
    scrollToEnd();
  }
  function chip(label, aria) {
    const b = el('button', 'chip-btn', label);
    b.type = 'button';
    if (aria) b.setAttribute('aria-label', aria);
    return b;
  }
  function callout(kind, title, text) {
    const c = el('div', 'callout ' + kind);
    c.appendChild(el('strong', '', title));
    c.appendChild(el('span', '', text));
    return c;
  }
  function prettySource(src) {
    return String(src)
      .replace(/^cleaned\/courses\.csv row [^ ]+ \(sheet '([^']+)' row (\d+)\)$/, 'Curriculum sheet “$1”, row $2')
      .replace(/^cleaned\/minor_courses\.csv \(([^)]+)\)$/, 'Minor course list ($1)')
      .replace(/^check_eligibility\(([^,]+), ([^)]+)\)$/, 'Eligibility check: $2 for $1')
      .replace(/^course_info\(([^)]+)\)$/, 'Catalogue lookup: $1')
      .replace(/^credit_summary \+ compute_cgpa \+ progression_status$/, 'Credits, CGPA and progression (calculated)')
      .replace(/^graduation_check$/, 'Graduation requirements check (calculated)')
      .replace(/4\. Student Handbook Aug 2026\.pdf/, 'Student Handbook (Aug 2026)')
      .replace(/SOP STUDENT 17082026 - Final\.pdf/, 'Student SOP (Aug 2026)');
  }
  function detailsPanel(meta) {
    const p = el('div', 'details-panel');
    if (meta.evidence && meta.evidence.length) {
      p.appendChild(el('h4', '', 'Sources used'));
      const ul = el('ul', 'source-list');
      meta.evidence.forEach((e) => {
        const li = el('li');
        li.dataset.source = e.id;
        li.appendChild(el('span', 'cite', e.id.slice(1)));
        const d = el('div');
        d.appendChild(el('div', '', prettySource(e.source)));
        d.appendChild(el('div', 'source-type', e.type === 'tool' ? 'calculated from the record' : e.type === 'regulation' ? 'structured rule' : 'document passage'));
        li.appendChild(d);
        ul.appendChild(li);
      });
      p.appendChild(ul);
    }
    if (meta.trace && meta.trace.length) {
      p.appendChild(el('h4', '', 'How this answer was made'));
      const ol = el('ol', 'steps');
      meta.trace.forEach((t) => {
        const li = el('li');
        const failed = t.passed === false;
        li.appendChild(el('span', 'dot' + (failed ? ' fail' : '')));
        const info = [];
        if (t.intent) info.push('topic: ' + t.intent.replace(/_/g, ' '));
        if (t.course_codes && t.course_codes.length) info.push(t.course_codes.join(', '));
        if (t.decisions && Object.keys(t.decisions).length) info.push(Object.entries(t.decisions).map(([k, v]) => `${k}: ${v.replace(/_/g, ' ').toLowerCase()}`).join(', '));
        if (t.cgpa !== undefined && t.cgpa !== null) info.push('CGPA ' + t.cgpa);
        if (t.credits_earned !== undefined) info.push(t.credits_earned + ' credits');
        if (t.skipped) info.push(t.skipped);
        if (t.issues && t.issues.length) info.push('fixed: ' + t.issues.join('; '));
        if (t.passed === true) info.push('passed');
        const txt = el('span');
        txt.appendChild(document.createTextNode(t.agent + ' '));
        txt.appendChild(el('span', 'step-info', (info.length ? '— ' + info.join(' · ') : '') + ` (${t.ms} ms)`));
        li.appendChild(txt);
        ol.appendChild(li);
      });
      p.appendChild(ol);
    }
    return p;
  }

  // ------------------------------------------------------------------ speech
  function speak(text, button) {
    const synth = window.speechSynthesis;
    if (synth.speaking) { synth.cancel(); button.textContent = '🔊 Listen'; return; }
    const u = new SpeechSynthesisUtterance(plain(text));
    u.lang = 'en-IN';
    const voice = synth.getVoices().find((v) => v.lang === 'en-IN') || synth.getVoices().find((v) => v.lang.startsWith('en'));
    if (voice) u.voice = voice;
    u.onend = () => { button.textContent = '🔊 Listen'; };
    button.textContent = '⏹ Stop';
    synth.speak(u);
  }
  function setupMic() {
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    const mic = $('micButton');
    if (!Rec) return;
    mic.hidden = false;
    let rec = null;
    mic.addEventListener('click', () => {
      if (!window.isSecureContext) {
        toast(`The microphone only works on secure pages. Open http://localhost:${location.port || 5000} on this computer, or the https:// site.`, 'error', 8000);
        return;
      }
      if (rec) { rec.stop(); return; }
      rec = new Rec();
      rec.lang = 'en-IN';
      rec.interimResults = true;
      const input = $('messageInput');
      const before = input.value ? input.value.trim() + ' ' : '';
      mic.classList.add('listening');
      mic.setAttribute('aria-pressed', 'true');
      toast('Listening… speak your question', '', 2500);
      rec.onresult = (e) => {
        input.value = before + Array.from(e.results).map((r) => r[0].transcript).join(' ');
        input.dispatchEvent(new Event('input'));
      };
      rec.onerror = (e) => {
        const msg = {
          'not-allowed': 'Microphone access is blocked. Click the lock icon next to the address, allow Microphone, then reload.',
          'service-not-allowed': 'Microphone access is blocked for this site.',
          network: 'Speech recognition needs internet (Chrome sends the audio to Google to transcribe it).',
          'no-speech': 'I didn’t hear anything. Click 🎤 and start speaking.',
          'audio-capture': 'No microphone was found.',
        }[e.error];
        if (msg) toast(msg, 'error', 7000);
      };
      rec.onend = () => { mic.classList.remove('listening'); mic.setAttribute('aria-pressed', 'false'); rec = null; input.focus(); };
      rec.start();
    });
  }

  // ------------------------------------------------------------------ charts
  async function showSvg(url, caption) {
    const res = await fetch(url);
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      toast(d.error || 'Chart not available.', 'error');
      return;
    }
    const svg = await res.text();
    const { body } = botShell();
    const fig = el('figure', 'chart-card');
    const img = el('img');
    img.alt = caption;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    fig.append(img, el('figcaption', '', caption + ' · drawn by code from the curriculum data (not AI-generated)'));
    body.appendChild(fig);
    img.addEventListener('load', scrollToEnd);
    scrollToEnd();
  }
  function showPrereqMap(code) {
    const q = new URLSearchParams({ code });
    const batch = $('batchSelect').value || (me && me.profile && me.profile.batch) || '';
    if (batch) q.set('batch', batch);
    if ($('studentId').value) q.set('student_id', $('studentId').value);
    if (!batch) { toast('Choose a batch in ⚙ Settings (or sign in) to see the prerequisite map.', 'error', 5000); openSettings(); return; }
    showSvg('/api/chart/prerequisites?' + q, `Prerequisite chain for ${code}`);
  }

  // ------------------------------------------------------------------ uploads
  async function upload(file) {
    if (!file) return;
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { toast('Please upload a PNG, JPEG or WebP image.', 'error'); return; }
    const { wrap, body } = botShell();
    const bubble = el('div', 'bubble');
    bubble.append(el('span', 'spinner'), el('span', 'thinking-step', ` Reading “${file.name}”…`));
    bubble.style.display = 'flex'; bubble.style.gap = '10px'; bubble.style.alignItems = 'center';
    body.appendChild(bubble);
    const form = new FormData();
    form.append('image', file);
    if ($('studentId').value) form.append('student_id', $('studentId').value);
    try {
      const res = await fetch('/api/transcript', { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not read the image.');
      bubble.removeAttribute('style');
      bubble.replaceChildren();
      bubble.appendChild(el('p', '', ''));
      bubble.firstChild.innerHTML = `<strong>Read from your ${esc((data.document_type || 'document').replace(/_/g, ' '))}</strong> · legibility: ${esc(data.legibility || '?')}`;
      const scroll = el('div', 'table-scroll');
      const t = el('table', 'extract-table');
      t.innerHTML = '<caption class="sr-only">Courses read from the image</caption><thead><tr><th>Code</th><th>Title</th><th>Credits</th><th>Grade</th><th>Check</th></tr></thead>';
      const tb = el('tbody');
      data.courses.forEach((c) => {
        const tr = el('tr', c.status === 'ok' ? '' : 'row-warn');
        [c.course_code || '?', c.course_title || '', c.credits ?? '', c.grade ?? '', c.status === 'ok' ? '✓' : c.status.replace(/_/g, ' ') + (c.notes.length ? ': ' + c.notes.join('; ') : '')]
          .forEach((v) => tr.appendChild(el('td', '', String(v))));
        tb.appendChild(tr);
      });
      t.appendChild(tb);
      scroll.appendChild(t);
      bubble.appendChild(scroll);
      [...data.warnings, ...data.discrepancies].forEach((w) => body.appendChild(callout('human', '⚠', w)));
      (data.security_events || []).forEach((e) => body.appendChild(callout('privacy', '🔒', {
        pii_redacted: 'Personal details (phone, email, date of birth) were removed before use.',
        prompt_injection_in_document: 'Hidden instructions in the document were ignored.',
        document_of_another_student: 'This document belongs to another student.',
      }[e.type] || e.type)));
      body.appendChild(el('p', 'answer-meta', data.note));
      const actions = el('div', 'answer-footer');
      const ok = chip('✔ Looks right, ask about it');
      ok.addEventListener('click', () => {
        const codes = data.courses.filter((c) => c.course_code && c.grade).map((c) => `${c.course_code} (${c.grade})`).join(', ');
        const input = $('messageInput');
        input.value = `My uploaded document shows: ${codes || 'these courses'}. What should I check before registering next semester?`;
        input.dispatchEvent(new Event('input'));
        input.focus();
        actions.remove();
      });
      const no = chip('✖ Discard');
      no.addEventListener('click', () => wrap.remove());
      actions.append(ok, no);
      body.appendChild(actions);
    } catch (err) {
      wrap.classList.add('error');
      bubble.removeAttribute('style');
      bubble.textContent = err.message;
    }
  }
  function setupUpload() {
    $('transcriptInput').addEventListener('change', (e) => { const f = e.target.files[0]; e.target.value = ''; upload(f); });
    const composer = $('chatForm');
    let depth = 0;
    const show = (on) => { composer.classList.toggle('dragging', on); $('dropHint').hidden = !on; };
    ['dragenter', 'dragover'].forEach((t) => composer.addEventListener(t, (e) => {
      if (!e.dataTransfer || !Array.from(e.dataTransfer.types || []).includes('Files')) return;
      e.preventDefault(); if (t === 'dragenter') depth += 1; show(true);
    }));
    composer.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) show(false); });
    composer.addEventListener('drop', (e) => {
      e.preventDefault(); depth = 0; show(false);
      if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
    });
  }

  // ------------------------------------------------------------------ settings, mode, context
  function currentMode() { return $('modeSelect').value || 'agentic'; }
  function setMode(mode, silent) {
    $('modeSelect').value = mode;
    document.querySelectorAll('input[name="mode"]').forEach((r) => { r.checked = r.value === mode; });
    store.set('vidyashilp-mode', mode);
    const pill = $('modePill');
    pill.textContent = mode === 'rag' ? 'Quick mode' : 'Verified mode';
    pill.classList.toggle('quick', mode === 'rag');
    renderContext();
    if (!silent) toast(mode === 'rag' ? 'Quick mode: one AI call per answer' : 'Verified mode: rule checks + source verification', '', 2500);
  }
  function openSettings() { const d = $('settingsPanel'); if (!d.open) d.showModal(); }
  function applyTheme(theme, persist) {
    document.documentElement.dataset.theme = theme;
    if (persist) store.set('vidyashilp-theme', theme);
    const button = $('themeButton');
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    const label = `Switch to ${nextTheme} mode`;
    button.textContent = theme === 'dark' ? '☀' : '☾';
    button.setAttribute('aria-label', label);
    button.setAttribute('aria-pressed', String(theme === 'dark'));
    button.title = label;
    document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#11151d' : '#f4f6fa';
  }
  function setupTheme() {
    const preference = store.get('vidyashilp-theme');
    let manuallySet = preference === 'dark' || preference === 'light';
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    applyTheme(manuallySet ? preference : (media.matches ? 'dark' : 'light'), false);
    $('themeButton').addEventListener('click', () => {
      manuallySet = true;
      applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', true);
    });
    media.addEventListener('change', (event) => {
      if (!manuallySet) applyTheme(event.matches ? 'dark' : 'light', false);
    });
  }
  function renderContext() {
    const row = $('contextRow');
    row.replaceChildren();
    const add = (text, title, onClick) => {
      const c = el(onClick ? 'button' : 'span', 'context-chip', text);
      if (onClick) { c.type = 'button'; c.addEventListener('click', onClick); }
      if (title) c.title = title;
      row.appendChild(c);
    };
    if (me && me.role === 'student') add(`👤 ${me.student_id}`, 'Answers use your own record');
    if (me && me.role === 'advisor') add($('studentId').value ? `👤 Advising ${$('studentId').value}` : '👤 No advisee selected', 'Choose an advisee in the menu', () => openSidebar());
    const b = $('batchSelect').value;
    const s = $('semesterSelect').value;
    if (me && me.role === 'student' && me.profile && me.profile.batch) {
      add(`📅 Batch ${me.profile.batch} (yours)`, 'Your own batch is used for your questions', openSettings);
    } else {
      add(b ? `📅 Batch ${b}${s ? ', sem ' + s : ''}` : '📅 Any batch', 'Batch used for general course questions', openSettings);
    }
    add(currentMode() === 'rag' ? '⚡ Quick' : '✓ Verified', 'How answers are produced', openSettings);
  }
  function setupSettings() {
    $('settingsButton').addEventListener('click', openSettings);
    $('modePill').addEventListener('click', openSettings);
    document.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener('change', () => setMode(r.value)));
    ['batchSelect', 'semesterSelect', 'modelSelect'].forEach((id) => $(id).addEventListener('change', renderContext));
    $('settingsPanel').addEventListener('close', renderContext);
    const saved = store.get('vidyashilp-mode');
    setMode(saved === 'rag' ? 'rag' : 'agentic', true);
  }

  // ------------------------------------------------------------------ sidebar drawer
  function openSidebar() { $('sidebar').classList.add('open'); $('scrim').hidden = false; $('menuButton').setAttribute('aria-expanded', 'true'); }
  function closeSidebar() { $('sidebar').classList.remove('open'); $('scrim').hidden = true; $('menuButton').setAttribute('aria-expanded', 'false'); }
  function setupSidebar() {
    $('menuButton').addEventListener('click', openSidebar);
    $('sidebarClose').addEventListener('click', closeSidebar);
    $('scrim').addEventListener('click', closeSidebar);
    $('sidebar').addEventListener('click', (e) => { if (e.target.closest('.conversation-item, #newChatButton')) closeSidebar(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSidebar(); });
  }

  // ------------------------------------------------------------------ auth
  function openSignIn() {
    $('signInError').hidden = true;
    const d = $('signInDialog');
    if (!d.open) d.showModal();
    setTimeout(() => $('loginUser').focus(), 30);
  }
  async function refreshMe() {
    try {
      const d = await (await fetch('/api/me')).json();
      me = d.user;
    } catch (e) { me = null; }
    applyUser();
  }
  function applyUser() {
    const signedIn = !!me;
    $('accountSignedOut').hidden = signedIn;
    $('accountSignedIn').hidden = !signedIn;
    const sid = $('studentId');
    if (signedIn) {
      const isAdv = me.role === 'advisor';
      $('accountAvatar').textContent = isAdv ? 'FA' : me.student_id.slice(-2);
      $('accountName').textContent = isAdv ? `Faculty advisor ${me.username}` : me.student_id;
      $('accountSub').textContent = isAdv ? `${me.advisees.length} advisees`
        : `Batch ${me.profile?.batch ?? '?'} · Semester ${me.profile?.current_semester ?? '?'}${me.profile?.minor ? ' · ' + me.profile.minor : ''}`;
      $('adviseeField').hidden = !isAdv;
      $('progressButton').hidden = isAdv && !sid.value;
      if (isAdv) {
        const sel = $('adviseeSelect');
        const keep = sid.value;
        sel.innerHTML = '<option value="">Choose a student…</option>' + me.advisees.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
        sel.value = me.advisees.includes(keep) ? keep : '';
        sid.value = sel.value;
      } else {
        sid.value = me.student_id;
      }
    } else {
      sid.value = '';
    }
    renderContext();
    const chat = $('chatWindow');
    if (chat.querySelector('.welcome') || !chat.childElementCount) renderWelcome(chat);
  }
  function setupAuth() {
    $('openSignIn').addEventListener('click', openSignIn);
    $('signInClose').addEventListener('click', () => $('signInDialog').close());
    const list = $('demoList');
    DEMO.forEach(([id, desc, pin]) => {
      const b = el('button', 'demo-item');
      b.type = 'button';
      b.innerHTML = `<strong>${esc(id)}</strong><span>${esc(desc)}</span>`;
      b.addEventListener('click', () => {
        $('loginUser').value = id;
        $('loginPin').value = pin || id.slice(-3) + '9';
        $('signInForm').requestSubmit();
      });
      list.appendChild(b);
    });
    $('signInForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = $('loginUser').value.trim();
      const pin = $('loginPin').value.trim();
      const err = $('signInError');
      if (!username || !pin) { err.textContent = 'Enter your ID and PIN.'; err.hidden = false; return; }
      $('loginButton').disabled = true;
      try {
        const res = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, pin }) });
        const data = await res.json();
        if (!res.ok) { err.textContent = data.error || 'Sign in failed.'; err.hidden = false; return; }
        $('loginPin').value = '';
        $('signInDialog').close();
        me = data.user;
        toast(`Signed in as ${me.role === 'advisor' ? me.username : me.student_id}`, 'ok', 2200);
        document.dispatchEvent(new CustomEvent('vg:auth-changed'));
        applyUser();
      } finally { $('loginButton').disabled = false; }
    });
    $('logoutButton').addEventListener('click', async () => {
      await fetch('/api/logout', { method: 'POST' });
      me = null;
      toast('Signed out', '', 1800);
      document.dispatchEvent(new CustomEvent('vg:auth-changed'));
      applyUser();
    });
    $('adviseeSelect').addEventListener('change', () => {
      $('studentId').value = $('adviseeSelect').value;
      $('progressButton').hidden = !$('studentId').value;
      renderContext();
    });
    $('progressButton').addEventListener('click', () => {
      const sid = $('studentId').value;
      closeSidebar();
      showSvg('/api/chart/progress' + (sid ? `?student_id=${encodeURIComponent(sid)}` : ''), 'Degree progress by credit basket');
    });
  }

  // ------------------------------------------------------------------ init
  function fitPlaceholder() {
    $('messageInput').placeholder = window.matchMedia('(max-width: 640px)').matches
      ? 'Ask a question…' : 'Ask about a course, a rule, or your own progress…';
  }
  document.addEventListener('DOMContentLoaded', () => {
    fitPlaceholder();
    window.addEventListener('resize', fitPlaceholder);
    setupTheme();
    setupSettings();
    setupSidebar();
    setupAuth();
    setupMic();
    setupUpload();
    refreshMe();
  });

  window.UI = {
    toast, renderMarkdown, renderAnswer, renderWelcome, showThinking, showError, decorateAnswer,
    currentMode, isSignedIn: () => !!me,
  };
})();
