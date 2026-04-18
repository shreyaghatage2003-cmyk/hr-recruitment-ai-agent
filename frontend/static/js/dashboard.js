const API = '';
let roles = [];
let chatWs;
const sessionId = 'hr-' + Math.random().toString(36).slice(2);

// --- Init ---
async function init() {
  await loadSummary();
  await loadRoles();
  await loadCandidates();
  initChatbot();
}

async function loadSummary() {
  const res = await fetch(`${API}/api/dashboard/summary`);
  const data = await res.json();
  const grid = document.getElementById('stats-grid');
  const stages = data.stage_counts || {};
  const items = [
    { num: data.total_candidates, label: 'Total Candidates' },
    { num: stages.ats_passed || 0, label: 'ATS Passed' },
    { num: stages.interview || 0, label: 'In Interview' },
    { num: stages.scheduled || 0, label: 'Scheduled' },
    { num: stages.hired || 0, label: 'Hired' },
    { num: stages.ats_rejected || 0, label: 'Rejected' },
  ];
  grid.innerHTML = items.map(i => `
    <div class="stat-card">
      <div class="num">${i.num}</div>
      <div class="label">${i.label}</div>
    </div>`).join('');
}

async function loadRoles() {
  const res = await fetch(`${API}/api/dashboard/roles`);
  roles = await res.json();
  const sel = document.getElementById('filter-role');
  sel.innerHTML = '<option value="">All Roles</option>';
  roles.forEach(r => {
    sel.innerHTML += `<option value="${r.id}">${r.title}</option>`;
  });
}

async function loadCandidates() {
  const roleId = document.getElementById('filter-role').value;
  const stage = document.getElementById('filter-stage').value;
  let url = `${API}/api/candidates/?`;
  if (roleId) url += `role_id=${roleId}&`;
  if (stage) url += `stage=${stage}`;

  const res = await fetch(url);
  const candidates = await res.json();
  const tbody = document.getElementById('candidates-tbody');
  tbody.innerHTML = '';

  candidates.forEach(c => {
    const role = roles.find(r => r.id === c.job_role_id);
    tbody.innerHTML += `
      <tr>
        <td>${c.id}</td>
        <td>${c.name}</td>
        <td>${c.email}</td>
        <td>${role ? role.title : c.job_role_id}</td>
        <td><span class="badge badge-${c.pipeline_stage}">${c.pipeline_stage}</span></td>
        <td>${c.ats_score != null ? c.ats_score.toFixed(1) + '%' : '—'}</td>
        <td>${c.interview_score != null ? c.interview_score.toFixed(1) : '—'}</td>
        <td>
          <select id="stage-sel-${c.id}" style="width:auto;padding:0.2rem;">
            ${['applied','ats_passed','ats_rejected','interview','screening','scheduled','hired','rejected']
              .map(s => `<option value="${s}" ${s===c.pipeline_stage?'selected':''}>${s}</option>`).join('')}
          </select>
          <button class="btn btn-primary" style="padding:0.2rem 0.6rem;font-size:0.8rem;" onclick="updateStage(${c.id})">Update</button>
        </td>
      </tr>`;
  });
}

async function updateStage(candidateId) {
  const stage = document.getElementById(`stage-sel-${candidateId}`).value;
  await fetch(`${API}/api/candidates/${candidateId}/stage`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage }),
  });
  await loadCandidates();
  await loadSummary();
}

// --- Create Role ---
document.getElementById('role-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    title: document.getElementById('r-title').value,
    description: document.getElementById('r-desc').value,
    required_skills: document.getElementById('r-skills').value,
    experience_level: document.getElementById('r-level').value,
    headcount_target: parseInt(document.getElementById('r-headcount').value),
  };
  const res = await fetch(`${API}/api/dashboard/roles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  document.getElementById('role-result').innerHTML = `<span style="color:green;">Role "${data.title}" created (ID: ${data.id})</span>`;
  await loadRoles();
});

// --- Chatbot ---
function initChatbot() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  chatWs = new WebSocket(`${proto}://${location.host}/ws/chatbot/${sessionId}`);
  chatWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    appendMessage('bot', data.message || data.error || 'Error');
  };
  chatWs.onerror = () => appendMessage('bot', 'Connection error.');
}

function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  appendMessage('user', msg);
  chatWs.send(JSON.stringify({ message: msg }));
  input.value = '';
}

document.getElementById('chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendChat();
});

function appendMessage(role, text) {
  const box = document.getElementById('chat-box');
  box.innerHTML += `<div class="msg ${role}"><div class="bubble">${text}</div></div>`;
  box.scrollTop = box.scrollHeight;
}

init();
