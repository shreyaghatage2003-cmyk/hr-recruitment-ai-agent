const params = new URLSearchParams(location.search);
const candidateId = params.get('id');
const API = '';
let ws, questions = [], currentIdx = 0, timerInterval;

if (!candidateId) {
  document.getElementById('status-msg').textContent = 'No candidate ID provided.';
} else {
  startInterview();
}

function startInterview() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/interview/${candidateId}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'questions') {
      questions = data.questions;
      document.getElementById('status-msg').textContent = `Interview starting — ${questions.length} questions, 30 seconds each.`;
    } else if (data.type === 'question') {
      showQuestion(data.index, data.question);
    } else if (data.type === 'timeout') {
      clearInterval(timerInterval);
      document.getElementById('status-msg').textContent = `Time's up for question ${data.index + 1}.`;
    } else if (data.type === 'answer_received') {
      clearInterval(timerInterval);
    } else if (data.type === 'complete') {
      showInterviewResult(data.result);
    } else if (data.type === 'error') {
      document.getElementById('status-msg').textContent = 'Error: ' + data.message;
    }
  };

  ws.onerror = () => {
    document.getElementById('status-msg').textContent = 'Connection error. Please refresh.';
  };
}

function showQuestion(idx, question) {
  currentIdx = idx;
  document.getElementById('status-msg').textContent = `Question ${idx + 1} of ${questions.length}`;
  document.getElementById('question-text').textContent = question;
  document.getElementById('question-text').style.display = 'block';

  const input = document.getElementById('answer-input');
  input.value = '';
  input.style.display = 'block';
  input.focus();

  // Disable copy-paste
  input.onpaste = (e) => e.preventDefault();
  input.oncopy = (e) => e.preventDefault();
  input.oncut = (e) => e.preventDefault();

  document.getElementById('submit-btn').style.display = 'inline-block';
  document.getElementById('result-panel').style.display = 'none';

  startTimer(30);
}

function startTimer(seconds) {
  const timerEl = document.getElementById('timer');
  timerEl.style.display = 'block';
  let remaining = seconds;
  timerEl.textContent = remaining;

  timerInterval = setInterval(() => {
    remaining--;
    timerEl.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(timerInterval);
      // Auto-submit with whatever is typed
      submitAnswer();
    }
  }, 1000);
}

function submitAnswer() {
  clearInterval(timerInterval);
  const answer = document.getElementById('answer-input').value;
  ws.send(JSON.stringify({ answer }));
  document.getElementById('submit-btn').style.display = 'none';
  document.getElementById('answer-input').style.display = 'none';
  document.getElementById('timer').style.display = 'none';
  document.getElementById('status-msg').textContent = 'Answer submitted, loading next question...';
}

document.getElementById('submit-btn').addEventListener('click', submitAnswer);

function showInterviewResult(result) {
  document.getElementById('question-text').style.display = 'none';
  document.getElementById('timer').style.display = 'none';
  document.getElementById('submit-btn').style.display = 'none';
  document.getElementById('answer-input').style.display = 'none';

  const panel = document.getElementById('result-panel');
  panel.style.display = 'block';
  panel.innerHTML = `<strong>Interview Complete!</strong><br/>Score: <strong>${result.interview_score}/100</strong><br/><em>Proceeding to HR Screening...</em>`;

  // Load screening after short delay
  setTimeout(() => loadScreening(), 1500);
}

// --- Screening ---
async function loadScreening() {
  document.getElementById('screening-panel').style.display = 'block';
  const res = await fetch(`${API}/api/screening/${candidateId}/questions`);
  const data = await res.json();
  const container = document.getElementById('screening-questions');
  container.innerHTML = '';
  data.questions.forEach((q, i) => {
    container.innerHTML += `
      <div style="margin-bottom:1rem;">
        <label>${i + 1}. ${q}</label>
        <input type="text" id="sq-${i}" placeholder="Your answer"/>
      </div>`;
  });
  window._screeningQuestions = data.questions;
}

document.getElementById('screening-submit').addEventListener('click', async () => {
  const qs = window._screeningQuestions || [];
  const answers = qs.map((q, i) => ({
    question: q,
    answer: document.getElementById(`sq-${i}`)?.value || '',
  }));
  await fetch(`${API}/api/screening/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_id: parseInt(candidateId), answers }),
  });
  document.getElementById('screening-panel').style.display = 'none';
  document.getElementById('scheduling-panel').style.display = 'block';
});

// --- Scheduling ---
document.getElementById('schedule-btn').addEventListener('click', async () => {
  const date = document.getElementById('pref-date').value;
  const time = document.getElementById('pref-time').value;
  if (!date || !time) { alert('Please select date and time.'); return; }

  const res = await fetch(`${API}/api/scheduling/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_id: parseInt(candidateId),
      availability: [{ date, time, timezone: 'UTC' }],
    }),
  });
  const data = await res.json();
  document.getElementById('schedule-result').innerHTML = `
    <div class="card" style="background:#d1fae5;">
      <strong>Interview Scheduled!</strong><br/>
      Date/Time: ${data.interview_datetime}<br/>
      Meeting Link: <a href="${data.meeting_link}" target="_blank">${data.meeting_link}</a><br/>
      Confirmation emails have been sent.
    </div>`;
  document.getElementById('schedule-btn').style.display = 'none';
});
