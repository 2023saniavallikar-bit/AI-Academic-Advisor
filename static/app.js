const chatWindow = document.getElementById('chatWindow');
const chatForm = document.getElementById('chatForm');
const studentIdInput = document.getElementById('studentId');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const newChatButton = document.getElementById('newChatButton');
const historyToggle = document.getElementById('historyToggle');
const clearButton = document.getElementById('clearButton');
const conversationList = document.getElementById('conversationList');
const modelSelect = document.getElementById('modelSelect');
const batchSelect = document.getElementById('batchSelect');
const semesterSelect = document.getElementById('semesterSelect');
let periodsByBatch = {};

function storeValue(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn('Could not save chat state in this browser:', error);
  }
}

function readValue(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function removeValue(key) {
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    console.warn('Could not remove cached chat data from this browser:', error);
  }
}

function getOrCreateId(storageKey) {
  try {
    const savedId = window.localStorage.getItem(storageKey);
    if (savedId) return savedId;
    const newId = window.crypto.randomUUID();
    storeValue(storageKey, newId);
    return newId;
  } catch (error) {
    console.error('Could not persist chat identity in this browser:', error);
    return window.crypto.randomUUID();
  }
}

let activeConversationId = getOrCreateId('vidyashilp-active-conversation-id');
const messageCachePrefix = 'vidyashilp-history:';
let conversationLoadSequence = 0;
const sendIcon = `
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
    <path d="M10 15.5v-11m0 0L5.5 9m4.5-4.5L14.5 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
`;

function formatCount(value) {
  return Number.isFinite(value) ? value.toLocaleString() : '?';
}

// The line under an answer: tokens and estimated cost, exactly as the server
// sent them. Older saved answers have no meta, so they show no line at all.
function buildUsageLine(meta) {
  if (!meta || typeof meta !== 'object') return null;
  const parts = [];
  const usage = meta.usage;
  if (usage) {
    parts.push(`Input ${formatCount(usage.input_tokens)} tokens`);
    let output = `Output ${formatCount(usage.output_tokens)} tokens`;
    if (usage.reasoning_tokens) {
      output += ` (incl. ${formatCount(usage.reasoning_tokens)} thinking)`;
    }
    parts.push(output);
    if (meta.cost && Number.isFinite(meta.cost.amount_usd)) {
      const amount = meta.cost.amount_usd;
      parts.push(`Est. cost $${amount.toFixed(amount < 0.01 ? 6 : 4)} (estimated)`);
    } else {
      parts.push('Cost unavailable (no price on file)');
    }
  } else {
    parts.push('Token usage was not reported for this response');
  }
  if (meta.mode) parts.push(meta.mode === 'agentic' ? 'Agentic (verified)' : 'RAG');
  if (meta.model_label) parts.push(meta.model_label);
  const period = meta.period;
  if (period && period.batch) {
    parts.push(period.semester
      ? `Batch ${period.batch}, semester ${period.semester}`
      : `Batch ${period.batch}`);
  }

  const line = document.createElement('div');
  line.className = 'usage-line';
  line.textContent = parts.join(' · ');
  if (meta.cost && meta.cost.basis) line.title = meta.cost.basis;
  return line;
}

function addMessage(text, sender = 'bot', isError = false, renderRichText = false, meta = null) {
  let messageList = document.querySelector('.message-list');
  if (!messageList) {
    chatWindow.innerHTML = '';
    messageList = document.createElement('div');
    messageList.className = 'message-list';
    chatWindow.appendChild(messageList);
  }

  const wrapper = document.createElement('div');
  wrapper.className = `message ${sender}${isError ? ' error' : ''}`;
  wrapper.setAttribute('role', 'group');
  wrapper.setAttribute('aria-label', sender === 'user' ? 'Your message' : 'Advisor response');

  if (sender === 'bot') {
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = 'VG';
    wrapper.appendChild(avatar);
  }

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (renderRichText && window.UI) {
    // UI.renderAnswer escapes all HTML first, then applies a small Markdown subset.
    bubble.innerHTML = window.UI.renderAnswer(text);
  } else {
    bubble.textContent = text;
  }

  const usageLine = sender === 'bot' && !isError && !window.UI ? buildUsageLine(meta) : null;
  const body = document.createElement('div');
  body.className = 'message-body';
  body.appendChild(bubble);
  if (usageLine) body.appendChild(usageLine);
  wrapper.appendChild(body);
  messageList.appendChild(wrapper);
  if (sender === 'bot' && !isError && window.UI) {
    window.UI.decorateAnswer(wrapper, text, meta);
  }
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  newChatButton.disabled = isLoading;
  clearButton.disabled = isLoading;
  historyToggle.disabled = isLoading;
  conversationList.querySelectorAll('button').forEach((button) => {
    button.disabled = isLoading;
  });
  sendButton.setAttribute('aria-label', isLoading ? 'Sending message' : 'Send message');
  sendButton.innerHTML = isLoading
    ? '<span class="send-spinner" aria-hidden="true"></span>'
    : sendIcon;
  messageInput.disabled = isLoading;
  studentIdInput.disabled = isLoading;
  modelSelect.disabled = isLoading;
  batchSelect.disabled = isLoading;
  semesterSelect.disabled = isLoading || !batchSelect.value;
  chatWindow.setAttribute('aria-busy', String(isLoading));
}

function showWelcome() {
  if (window.UI) {
    window.UI.renderWelcome(chatWindow);
  } else {
    chatWindow.innerHTML = '<p>Ask a question about courses, credits or regulations.</p>';
  }
  messageInput.value = '';
  messageInput.style.height = 'auto';
  // Note: the signed-in student / chosen advisee (studentIdInput) is kept.
}

function readCachedMessages(conversationId) {
  try {
    const cached = window.localStorage.getItem(messageCachePrefix + conversationId);
    if (!cached) return null;
    const messages = JSON.parse(cached);
    if (
      !Array.isArray(messages)
      || messages.some((message) => (
        !message
        || !['user', 'assistant'].includes(message.role)
        || typeof message.content !== 'string'
      ))
    ) {
      return null;
    }
    return messages;
  } catch (error) {
    console.error('Could not read cached conversation:', error);
    return null;
  }
}

function cacheMessages(conversationId, messages) {
  try {
    window.localStorage.setItem(
      messageCachePrefix + conversationId,
      JSON.stringify(messages.slice(-30)),
    );
  } catch (error) {
    console.warn('Could not cache conversation in this browser:', error);
  }
}

function renderConversationMessages(messages) {
  chatWindow.innerHTML = '<div class="message-list"></div>';
  messages.forEach((message) => {
    addMessage(
      message.content,
      message.role === 'user' ? 'user' : 'bot',
      false,
      message.role === 'assistant',
      message.role === 'assistant' ? message.meta : null,
    );
  });
  if (!messages.length) showWelcome();
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function refreshConversations() {
  try {
    const response = await fetch('/api/conversations');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load conversations.');

    conversationList.replaceChildren();
    if (!data.conversations.length) {
      const emptyState = document.createElement('span');
      emptyState.className = 'history-empty';
      emptyState.textContent = 'Your conversations will appear here.';
      conversationList.appendChild(emptyState);
      return;
    }

    data.conversations.forEach((conversation) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'history-item conversation-item';
      if (conversation.id === activeConversationId) button.classList.add('active');
      button.dataset.conversationId = conversation.id;
      button.title = conversation.title;

      const icon = document.createElement('span');
      icon.className = 'history-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = '◷';
      const title = document.createElement('span');
      title.className = 'conversation-title';
      title.textContent = conversation.title;
      button.append(icon, title);
      conversationList.appendChild(button);
    });
  } catch (error) {
    console.error('Could not load conversation history:', error);
    conversationList.textContent = 'Could not load conversation history.';
  }
}

async function loadConversation(conversationId) {
  const loadSequence = ++conversationLoadSequence;
  activeConversationId = conversationId;
  storeValue('vidyashilp-active-conversation-id', conversationId);
  const cachedMessages = readCachedMessages(conversationId);
  if (cachedMessages) renderConversationMessages(cachedMessages);
  try {
    const response = await fetch(
      `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    );
    if (loadSequence !== conversationLoadSequence) return;
    if (response.status === 404) {
      removeValue(messageCachePrefix + conversationId);
      await startNewConversation();
      return;
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load this conversation.');

    studentIdInput.value = data.conversation.student_id || '';
    renderConversationMessages(data.messages);
    cacheMessages(conversationId, data.messages);
    await refreshConversations();
  } catch (error) {
    if (loadSequence !== conversationLoadSequence) return;
    console.error('Could not load conversation:', error);
    addMessage('Could not load this saved conversation.', 'bot', true);
  }
}

async function startNewConversation() {
  conversationLoadSequence += 1;
  activeConversationId = window.crypto.randomUUID();
  storeValue('vidyashilp-active-conversation-id', activeConversationId);
  document.querySelector('.conversation-history').classList.remove('is-open');
  historyToggle.setAttribute('aria-expanded', 'false');
  showWelcome();
  await refreshConversations();
  messageInput.focus();
}

async function clearConversation() {
  const conversationId = activeConversationId;
  try {
    const response = await fetch(
      `/api/conversations/${encodeURIComponent(conversationId)}`,
      { method: 'DELETE' },
    );
    if (!response.ok && response.status !== 404) {
      const data = await response.json();
      throw new Error(data.error || 'Could not clear this conversation.');
    }
    removeValue(messageCachePrefix + conversationId);
    await startNewConversation();
  } catch (error) {
    console.error('Could not clear conversation:', error);
    addMessage(
      error instanceof Error ? error.message : 'Could not clear this conversation.',
      'bot',
      true,
    );
  }
}

document.addEventListener('click', (event) => {
  if (!(event.target instanceof Element)) return;
  const conversationButton = event.target.closest('.conversation-item[data-conversation-id]');
  if (conversationButton) {
    document.querySelector('.conversation-history').classList.remove('is-open');
    historyToggle.setAttribute('aria-expanded', 'false');
    loadConversation(conversationButton.dataset.conversationId);
    return;
  }

  const promptButton = event.target.closest('.prompt-chip, .history-item[data-prompt]');
  if (!promptButton) return;

  messageInput.value = promptButton.getAttribute('data-prompt') || '';
  messageInput.dispatchEvent(new Event('input'));
  messageInput.focus();
});

async function sendMessage(message) {
  const studentId = studentIdInput.value.trim();
  const mode = window.UI ? window.UI.currentMode() : 'agentic';
  addMessage(message, 'user');
  setLoading(true);
  const thinking = window.UI ? window.UI.showThinking(mode) : { remove() {} };
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        student_id: studentId,
        conversation_id: activeConversationId,
        model: modelSelect.value,
        batch: batchSelect.value,
        semester: semesterSelect.value,
        mode,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || 'Unable to get an answer.');
      error.status = response.status;
      throw error;
    }
    thinking.remove();
    addMessage(data.answer || 'No answer returned.', 'bot', false, true, data.meta);
    const cachedMessages = readCachedMessages(activeConversationId) || [];
    cacheMessages(activeConversationId, [
      ...cachedMessages,
      { role: 'user', content: message },
      { role: 'assistant', content: data.answer || 'No answer returned.', meta: data.meta || null },
    ]);
    refreshConversations();
  } catch (error) {
    thinking.remove();
    const text = error instanceof Error ? error.message : 'Something went wrong.';
    if (window.UI) {
      window.UI.showError(text, {
        status: error.status,
        retry: () => {
          // remove the failed question bubble, then send it again
          const bubbles = chatWindow.querySelectorAll('.message.user');
          const last = bubbles[bubbles.length - 1];
          if (last) last.remove();
          sendMessage(message);
        },
      });
    } else {
      addMessage(text, 'bot', true);
    }
  } finally {
    setLoading(false);
    messageInput.focus();
  }
}

chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    messageInput.focus();
    return;
  }
  messageInput.value = '';
  messageInput.style.height = 'auto';
  sendMessage(message);
});

// Signing in or out starts a fresh conversation, so one person's chat is never
// shown to the next person using the same browser.
document.addEventListener('vg:auth-changed', () => {
  startNewConversation();
});

messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 160)}px`;
});

messageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

newChatButton.addEventListener('click', startNewConversation);
clearButton.addEventListener('click', clearConversation);
historyToggle.addEventListener('click', () => {
  const isOpen = document.querySelector('.conversation-history').classList.toggle('is-open');
  historyToggle.setAttribute('aria-expanded', String(isOpen));
});

async function loadOptions() {
  try {
    const response = await fetch('/api/options');
    const data = await response.json();
    if (!response.ok) throw new Error('Could not load options.');
    modelSelect.replaceChildren();
    data.models.forEach((model) => {
      const option = document.createElement('option');
      option.value = model.id;
      option.textContent = model.label;
      if (model.note) option.title = model.note;
      modelSelect.appendChild(option);
    });
    const saved = readValue('vidyashilp-model');
    const ids = data.models.map((model) => model.id);
    modelSelect.value = ids.includes(saved) ? saved : data.default_model;
    loadPeriods(data.periods);
  } catch (error) {
    console.warn('Using the default model:', error);
  }
}

function fillSemesters(batch, wanted) {
  semesterSelect.replaceChildren();
  const none = document.createElement('option');
  none.value = '';
  none.textContent = 'Not specified';
  semesterSelect.appendChild(none);
  const semesters = periodsByBatch[batch] || [];
  semesters.forEach((number) => {
    const option = document.createElement('option');
    option.value = String(number);
    option.textContent = String(number);
    semesterSelect.appendChild(option);
  });
  semesterSelect.value = semesters.map(String).includes(wanted) ? wanted : '';
  semesterSelect.disabled = !batch || semesters.length === 0;
}

// Batches and semesters come from the server, which reads them from the data.
function loadPeriods(periods) {
  periodsByBatch = {};
  const batches = (periods && Array.isArray(periods.batches)) ? periods.batches : [];
  batches.forEach((entry) => { periodsByBatch[String(entry.batch)] = entry.semesters; });
  batchSelect.replaceChildren();
  const none = document.createElement('option');
  none.value = '';
  none.textContent = 'Not specified';
  batchSelect.appendChild(none);
  batches.forEach((entry) => {
    const option = document.createElement('option');
    option.value = String(entry.batch);
    option.textContent = String(entry.batch);
    batchSelect.appendChild(option);
  });
  const savedBatch = readValue('vidyashilp-batch') || '';
  batchSelect.value = periodsByBatch[savedBatch] ? savedBatch : '';
  fillSemesters(batchSelect.value, readValue('vidyashilp-semester') || '');
}

batchSelect.addEventListener('change', () => {
  storeValue('vidyashilp-batch', batchSelect.value);
  fillSemesters(batchSelect.value, '');
  storeValue('vidyashilp-semester', '');
});

semesterSelect.addEventListener('change', () => {
  storeValue('vidyashilp-semester', semesterSelect.value);
});

modelSelect.addEventListener('change', () => {
  storeValue('vidyashilp-model', modelSelect.value);
});

loadOptions();
refreshConversations();
loadConversation(activeConversationId);
