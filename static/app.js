const chatWindow = document.getElementById('chatWindow');
const chatForm = document.getElementById('chatForm');
const studentIdInput = document.getElementById('studentId');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const newChatButton = document.getElementById('newChatButton');
const historyToggle = document.getElementById('historyToggle');
const clearButton = document.getElementById('clearButton');
const conversationList = document.getElementById('conversationList');

function storeValue(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.warn('Could not save chat state in this browser:', error);
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
const mathJaxReady = new Promise((resolve) => {
  if (typeof window.MathJax?.typesetPromise === 'function') {
    resolve();
    return;
  }

  const mathJaxScript = document.getElementById('mathJaxScript');
  if (!mathJaxScript) {
    resolve();
    return;
  }

  mathJaxScript.addEventListener('load', resolve, { once: true });
  mathJaxScript.addEventListener('error', resolve, { once: true });
});

const sendIcon = `
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
    <path d="M10 15.5v-11m0 0L5.5 9m4.5-4.5L14.5 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
`;

function addMessage(text, sender = 'bot', isError = false, renderRichText = false) {
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
    avatar.textContent = 'A';
    wrapper.appendChild(avatar);
  }

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (
    renderRichText
    && typeof window.marked?.parse === 'function'
    && typeof window.DOMPurify?.sanitize === 'function'
  ) {
    const markdown = window.marked.parse(text, { gfm: true, breaks: false });
    bubble.innerHTML = window.DOMPurify.sanitize(markdown);
  } else {
    bubble.textContent = text;
  }

  wrapper.appendChild(bubble);
  messageList.appendChild(wrapper);
  if (renderRichText) {
    mathJaxReady
      .then(() => window.MathJax?.typesetPromise?.([bubble]))
      .catch((error) => {
        console.error('Could not typeset advisor response math:', error);
      });
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
  chatWindow.setAttribute('aria-busy', String(isLoading));
}

function showWelcome() {
  chatWindow.innerHTML = `
    <div class="welcome-content">
      <div class="welcome-block">
        <span class="welcome-eyebrow">VIDYASHILP UNIVERSITY</span>
        <h2>Hello 👋<br />Welcome to Vidyashilp Guide.</h2>
        <p>Get clear, personalized guidance on your courses, prerequisites, degree requirements, semester planning, and university policies.</p>
      </div>
      <div class="quick-prompts" aria-label="Suggested questions">
        <button type="button" class="prompt-chip" data-prompt="What courses should I take next?">
          <span class="prompt-icon" aria-hidden="true">01</span>
          <span><strong>Plan my semester</strong><small>Explore courses for next term</small></span>
          <span class="prompt-arrow" aria-hidden="true">↗</span>
        </button>
        <button type="button" class="prompt-chip" data-prompt="Can I take COMP203 next semester?">
          <span class="prompt-icon" aria-hidden="true">02</span>
          <span><strong>Check prerequisites</strong><small>See what you need before a course</small></span>
          <span class="prompt-arrow" aria-hidden="true">↗</span>
        </button>
        <button type="button" class="prompt-chip" data-prompt="Show my degree requirements">
          <span class="prompt-icon" aria-hidden="true">03</span>
          <span><strong>Understand my degree</strong><small>Make sense of your requirements</small></span>
          <span class="prompt-arrow" aria-hidden="true">↗</span>
        </button>
      </div>
    </div>
  `;
  messageInput.value = '';
  studentIdInput.value = '';
  messageInput.style.height = 'auto';
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

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  const studentId = studentIdInput.value.trim();

  if (!message) {
    messageInput.focus();
    return;
  }

  addMessage(message, 'user');
  messageInput.value = '';
  messageInput.style.height = 'auto';
  setLoading(true);

  const typingMessage = document.createElement('div');
  typingMessage.className = 'message bot';
  typingMessage.setAttribute('role', 'status');
  typingMessage.setAttribute('aria-label', 'Finding guidance in university documents');

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = 'V';

  const bubble = document.createElement('div');
  bubble.className = 'bubble typing-indicator';
  const spinner = document.createElement('span');
  spinner.className = 'thinking-spinner';
  spinner.setAttribute('aria-hidden', 'true');
  const statusText = document.createElement('span');
  statusText.textContent = 'Finding guidance';
  const dots = document.createElement('span');
  dots.className = 'thinking-dots';
  dots.setAttribute('aria-hidden', 'true');
  for (let index = 0; index < 3; index += 1) {
    dots.appendChild(document.createElement('span'));
  }

  bubble.append(spinner, statusText, dots);
  typingMessage.append(avatar, bubble);
  document.querySelector('.message-list').appendChild(typingMessage);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        student_id: studentId,
        conversation_id: activeConversationId,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Unable to get an answer.');
    }

    addMessage(data.answer || 'No answer returned.', 'bot', false, true);
    const cachedMessages = readCachedMessages(activeConversationId) || [];
    cacheMessages(activeConversationId, [
      ...cachedMessages,
      { role: 'user', content: message },
      { role: 'assistant', content: data.answer || 'No answer returned.' },
    ]);

    if (data.student_id) {
      studentIdInput.value = data.student_id;
    }
    refreshConversations();
  } catch (error) {
    addMessage(error instanceof Error ? error.message : 'Something went wrong.', 'bot', true);
  } finally {
    typingMessage.remove();
    setLoading(false);
    messageInput.focus();
  }
});

messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 130)}px`;
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

refreshConversations();
loadConversation(activeConversationId);
