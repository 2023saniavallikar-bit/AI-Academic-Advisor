const chatWindow = document.getElementById('chatWindow');
const chatForm = document.getElementById('chatForm');
const studentIdInput = document.getElementById('studentId');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const newChatButton = document.getElementById('newChatButton');
const clearButton = document.getElementById('clearButton');

const sendIcon = `
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
    <path d="M10 15.5v-11m0 0L5.5 9m4.5-4.5L14.5 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
`;

function addMessage(text, sender = 'bot', isError = false) {
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
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  messageList.appendChild(wrapper);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  newChatButton.disabled = isLoading;
  clearButton.disabled = isLoading;
  sendButton.setAttribute('aria-label', isLoading ? 'Sending message' : 'Send message');
  sendButton.innerHTML = isLoading ? '…' : sendIcon;
  messageInput.disabled = isLoading;
  studentIdInput.disabled = isLoading;
  chatWindow.setAttribute('aria-busy', String(isLoading));
}

function resetConversation() {
  chatWindow.innerHTML = `
    <div class="welcome-content">
      <div class="welcome-block">
        <span class="welcome-eyebrow">YOUR CAMPUS, MADE CLEAR</span>
        <h2>A little guidance<br />goes a long way.</h2>
        <p>Get thoughtful answers about your studies, backed by your university’s academic documents.</p>
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
  messageInput.focus();
}

document.addEventListener('click', (event) => {
  if (!(event.target instanceof Element)) return;
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
  typingMessage.innerHTML = '<div class="message-avatar" aria-hidden="true">A</div><div class="bubble typing-indicator">Thinking</div>';
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
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Unable to get an answer.');
    }

    addMessage(data.answer || 'No answer returned.', 'bot');

    if (data.student_id) {
      studentIdInput.value = data.student_id;
    }
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

newChatButton.addEventListener('click', resetConversation);
clearButton.addEventListener('click', resetConversation);
