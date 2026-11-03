/* Assignment 2 front-end features: login, voice in/out, transcript upload,
   charts, agent trace, human-review badges. Loaded after app.js. */
(function () {
  const $ = (id) => document.getElementById(id);
  const loginForm = $('loginForm');
  const loggedIn = $('loggedIn');
  const whoAmI = $('whoAmI');
  const adviseeSelect = $('adviseeSelect');
  const studentIdField = $('studentId');
  const messageField = $('messageInput');
  let currentUser = null;

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function listEl() {
    let list = document.querySelector('.message-list');
    if (!list) {
      const chat = $('chatWindow');
      chat.innerHTML = '';
      list = el('div', 'message-list');
      chat.appendChild(list);
    }
    return list;
  }

  function systemCard(node) {
    const wrap = el('div', 'message bot');
    const avatar = el('div', 'message-avatar', 'A');
    avatar.setAttribute('aria-hidden', 'true');
    const body = el('div', 'message-body');
    body.appendChild(node);
    wrap.append(avatar, body);
    listEl().appendChild(wrap);
    $('chatWindow').scrollTop = $('chatWindow').scrollHeight;
    return wrap;
  }

  // ------------------------------------------------------------------ auth
  function showUser(user) {
    currentUser = user;
    loginForm.hidden = !!user;
    loggedIn.hidden = !user;
    if (!user) { studentIdField.value = ''; return; }
    if (user.role === 'advisor') {
      whoAmI.textContent = `Faculty advisor ${user.username}`;
      adviseeSelect.hidden = false;
      adviseeSelect.innerHTML = '<option value="">Choose advisee…</option>' +
        user.advisees.map((s) => `<option value="${s}">${s}</option>`).join('');
      studentIdField.value = '';
    } else {
      whoAmI.textContent = `Logged in as ${user.student_id}`;
      adviseeSelect.hidden = true;
      studentIdField.value = user.student_id;
    }
  }

  async function doLogin() {
    const username = $('loginUser').value.trim();
    const pin = $('loginPin').value.trim();
    if (!username || !pin) return;
    const res = await fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, pin }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.error || 'Login failed'); return; }
    $('loginPin').value = '';
    showUser(data.user);
  }
  $('loginButton').addEventListener('click', doLogin);
  $('loginPin').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); doLogin(); } });
  $('logoutButton').addEventListener('click', async () => {
    await fetch('/api/logout', { method: 'POST' });
    showUser(null);
  });
  adviseeSelect.addEventListener('change', () => { studentIdField.value = adviseeSelect.value; });
  fetch('/api/me').then((r) => r.json()).then((d) => showUser(d.user)).catch(() => {});

  // ------------------------------------------------------------------ charts
  async function showSvg(url, caption) {
    const res = await fetch(url);
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      systemCard(el('div', 'bubble', d.error || 'Chart not available.'));
      return;
    }
    const svgText = await res.text();
    const fig = el('figure', 'chart-card');
    const img = el('img');
    img.alt = caption;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText);
    const cap = el('figcaption', '', caption + ' · drawn by code from the curriculum data');
    fig.append(img, cap);
    systemCard(fig);
  }
  $('progressButton').addEventListener('click', () => {
    const sid = studentIdField.value;
    showSvg('/api/chart/progress' + (sid ? `?student_id=${encodeURIComponent(sid)}` : ''), 'Degree progress');
  });

  // ------------------------------------------------------------------ voice
  const synth = window.speechSynthesis;
  function plainText(md) {
    return md.replace(/\[E\d+\]/g, '').replace(/[*_#`>]/g, '').replace(/\s+/g, ' ').trim();
  }
  function speak(text, button) {
    if (!synth) return;
    if (synth.speaking) { synth.cancel(); button.textContent = '🔊 Listen'; return; }
    const u = new SpeechSynthesisUtterance(plainText(text));
    u.lang = 'en-IN';
    u.rate = 1.0;
    const voice = synth.getVoices().find((v) => v.lang === 'en-IN') || synth.getVoices().find((v) => v.lang.startsWith('en'));
    if (voice) u.voice = voice;
    u.onend = () => { button.textContent = '🔊 Listen'; };
    button.textContent = '⏹ Stop';
    synth.speak(u);
  }

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mic = $('micButton');
  if (Recognition) {
    mic.hidden = false;
    let rec = null;
    mic.addEventListener('click', () => {
      if (rec) { rec.stop(); return; }
      rec = new Recognition();
      rec.lang = 'en-IN';
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      mic.classList.add('listening');
      rec.onresult = (e) => {
        messageField.value = Array.from(e.results).map((r) => r[0].transcript).join(' ');
        messageField.dispatchEvent(new Event('input'));
      };
      rec.onerror = (e) => { console.warn('speech error', e.error); };
      rec.onend = () => { mic.classList.remove('listening'); rec = null; messageField.focus(); };
      rec.start();
    });
  }

  // ------------------------------------------------------------------ answer decoration
  window.decorateAnswer = function (wrapper, text, meta) {
    const body = wrapper.querySelector('.message-body') || wrapper;
    const tools = el('div', 'answer-tools');
    const badge = el('span', 'ai-label', 'AI-generated · not an official decision');
    tools.appendChild(badge);
    if (synth) {
      const b = el('button', 'tiny-button', '🔊 Listen');
      b.type = 'button';
      b.addEventListener('click', () => speak(text, b));
      tools.appendChild(b);
    }
    const intakeCodes = (meta && meta.trace && meta.trace[0] && meta.trace[0].course_codes) || [];
    const codes = Array.from(new Set([...intakeCodes, ...(text.match(/\b[A-Z]{4}\d{3}\b/g) || [])])).slice(0, 3);
    codes.forEach((code) => {
      const b = el('button', 'tiny-button', `🗺 ${code} prerequisites`);
      b.type = 'button';
      b.addEventListener('click', () => {
        const batch = document.getElementById('batchSelect').value;
        const sid = studentIdField.value;
        const q = new URLSearchParams({ code });
        if (batch) q.set('batch', batch);
        if (sid) q.set('student_id', sid);
        showSvg('/api/chart/prerequisites?' + q.toString(), `Prerequisite chain for ${code}`);
      });
      tools.appendChild(b);
    });
    body.appendChild(tools);

    if (!meta) return;
    if (meta.human_review && meta.human_review.length) {
      const hr = el('div', 'human-review');
      hr.appendChild(el('strong', '', 'Needs a human decision: '));
      hr.appendChild(document.createTextNode(meta.human_review.join(' ')));
      body.appendChild(hr);
    }
    if (meta.security_events && meta.security_events.length) {
      body.appendChild(el('div', 'security-note', '🔒 Privacy safeguard applied: ' + meta.security_events.join(', ')));
    }
    if (meta.trace && meta.trace.length) {
      const det = el('details', 'agent-trace');
      det.appendChild(el('summary', '', `How this answer was made (${meta.trace.length} steps` +
        (meta.status ? ` · ${meta.status}` : '') + (meta.elapsed_ms ? ` · ${(meta.elapsed_ms / 1000).toFixed(1)}s` : '') + ')'));
      const ol = el('ol');
      meta.trace.forEach((t) => {
        const info = Object.entries(t).filter(([k]) => !['agent', 'ms', 'llm_verdict'].includes(k))
          .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ');
        ol.appendChild(el('li', '', `${t.agent} (${t.ms} ms) — ${info}`));
      });
      det.appendChild(ol);
      if (meta.evidence && meta.evidence.length) {
        det.appendChild(el('p', 'trace-heading', 'Evidence'));
        const ul = el('ul', 'evidence-list');
        meta.evidence.forEach((e) => ul.appendChild(el('li', '', `[${e.id}] ${e.type}: ${e.source}`)));
        det.appendChild(ul);
      }
      body.appendChild(det);
    }
  };

  // ------------------------------------------------------------------ transcript upload
  $('transcriptInput').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    event.target.value = '';
    if (!file) return;
    const preview = el('div', 'bubble');
    preview.textContent = `Reading ${file.name} with the vision model…`;
    const card = systemCard(preview);
    const form = new FormData();
    form.append('image', file);
    if (studentIdField.value) form.append('student_id', studentIdField.value);
    try {
      const res = await fetch('/api/transcript', { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not read the image.');
      preview.innerHTML = '';
      preview.appendChild(el('strong', '', `Extracted from ${data.document_type || 'document'} (legibility: ${data.legibility || '?'})`));
      const table = el('table', 'extract-table');
      table.innerHTML = '<thead><tr><th>Code</th><th>Title</th><th>Credits</th><th>Grade</th><th>Check</th></tr></thead>';
      const tb = el('tbody');
      data.courses.forEach((c) => {
        const tr = el('tr', c.status === 'ok' ? '' : 'row-warn');
        [c.course_code || '?', c.course_title || '', c.credits ?? '', c.grade ?? '', c.status + (c.notes.length ? ' – ' + c.notes.join('; ') : '')]
          .forEach((v) => tr.appendChild(el('td', '', String(v))));
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      preview.appendChild(table);
      [...data.warnings, ...data.discrepancies].forEach((w) => preview.appendChild(el('p', 'security-note', '⚠ ' + w)));
      preview.appendChild(el('p', 'ai-label', data.note));
      const actions = el('div', 'answer-tools');
      const ok = el('button', 'tiny-button', '✔ Looks right – ask about it');
      ok.type = 'button';
      ok.addEventListener('click', () => {
        const codes = data.courses.filter((c) => c.course_code && c.grade).map((c) => `${c.course_code} (${c.grade})`).join(', ');
        messageField.value = `My uploaded document shows: ${codes}. Based on this, what should I check before registering next semester?`;
        messageField.focus();
        actions.remove();
      });
      const no = el('button', 'tiny-button', '✖ Discard');
      no.type = 'button';
      no.addEventListener('click', () => card.remove());
      actions.append(ok, no);
      preview.appendChild(actions);
    } catch (error) {
      preview.textContent = error.message;
    }
  });
})();
