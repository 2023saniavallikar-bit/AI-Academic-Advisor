const chatWindow = document.getElementById('chatWindow');
const chatForm = document.getElementById('chatForm');
const studentIdInput = document.getElementById('studentId');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const newChatButton = document.getElementById('newChatButton');
const clearButton = document.getElementById('clearButton');

function addMessage(text, sender = 'bot') {
  let messageList = document.querySelector('.message-list');
  if (!messageList) {
    chatWindow.innerHTML = '';
    messageList = document.createElement('div');
    messageList.className = 'message-list';
    chatWindow.appendChild(messageList);
  }

  const wrapper = document.createElement('div');
  wrapper.className = `message ${sender}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  messageList.appendChild(wrapper);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  sendButton.textContent = isLoading ? '…' : '↑';
  messageInput.disabled = isLoading;
  studentIdInput.disabled = isLoading;
}

function resetConversation() {
  chatWindow.innerHTML = `
    <div class="welcome-block">
      <div class="welcome-icon">✦</div>
      <h2>How can I help you today?</h2>
      <p>Ask me about courses, prerequisites, degree requirements, or academic policy.</p>
    </div>
    <div class="quick-prompts">
      <button type="button" class="prompt-chip">Can I take COMP203 next semester?</button>
      <button type="button" class="prompt-chip">What courses should I take next?</button>
      <button type="button" class="prompt-chip">Show my degree requirements</button>
    </div>
  `;
  messageInput.value = '';
  studentIdInput.value = '';
  bindPromptButtons();
  messageInput.focus();
}

function bindPromptButtons() {
  document.querySelectorAll('.prompt-chip').forEach((button) => {
    button.addEventListener('click', () => {
      messageInput.value = button.textContent;
      messageInput.focus();
    });
  });
}

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
  setLoading(true);

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
    addMessage(error.message || 'Something went wrong.', 'bot');
  } finally {
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
bindPromptButtons();
