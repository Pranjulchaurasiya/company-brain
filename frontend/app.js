// Company Brain Frontend Client

const API_BASE = '/api';

// DOM Elements
const dbStatusBadge = document.getElementById('dbStatusBadge');
const dbStatusText = document.getElementById('dbStatusText');
const wsLabel = document.getElementById('wsLabel');
const nodeCountEl = document.getElementById('nodeCount');
const edgeCountEl = document.getElementById('edgeCount');
const resetBtn = document.getElementById('resetBtn');
const runStarterGoalBtn = document.getElementById('runStarterGoalBtn');
const submitGoalBtn = document.getElementById('submitGoalBtn');
const goalInput = document.getElementById('goalInput');
const btnSpinner = document.getElementById('btnSpinner');
const btnText = document.getElementById('btnText');
const supersedeBtn = document.getElementById('supersedeBtn');
const recallMemoryBtn = document.getElementById('recallMemoryBtn');
const generalityBtn = document.getElementById('generalityBtn');

const timelineContainer = document.getElementById('timelineContainer');
const deliverableCard = document.getElementById('deliverableCard');
const deliverableContent = document.getElementById('deliverableContent');
const citationsContainer = document.getElementById('citationsContainer');
const citationCountBadge = document.getElementById('citationCountBadge');
const historyContainer = document.getElementById('historyContainer');
const graphSvg = document.getElementById('graphSvg');
const graphOverlayInfo = document.getElementById('graphOverlayInfo');

// Modal Elements
const modalBackdrop = document.getElementById('modalBackdrop');
const modalTitle = document.getElementById('modalTitle');
const modalBody = document.getElementById('modalBody');
const modalCloseBtn = document.getElementById('modalCloseBtn');

// State
let graphData = { nodes: [], edges: [] };

// Initialize App
document.addEventListener('DOMContentLoaded', async () => {
  await checkHealth();
  await refreshAll();
  setupEventListeners();
});

function setupEventListeners() {
  resetBtn.addEventListener('click', handleReset);
  runStarterGoalBtn.addEventListener('click', () => runWorkflow(goalInput.value));
  submitGoalBtn.addEventListener('click', () => runWorkflow(goalInput.value));
  supersedeBtn.addEventListener('click', handleSupersede);
  recallMemoryBtn.addEventListener('click', handleRecallMemory);
  generalityBtn.addEventListener('click', handleGenerality);

  // Quick query chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => handleQuickQuery(chip.dataset.query));
  });

  // Modal
  modalCloseBtn.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', (e) => {
    if (e.target === modalBackdrop) closeModal();
  });
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    if (data.status === 'HEALTHY') {
      dbStatusBadge.innerHTML = '<span class="status-dot healthy"></span> FalkorDB: Live (Port 6379)';
      dbStatusBadge.style.color = '#10b981';
    } else {
      dbStatusBadge.innerHTML = '<span class="status-dot" style="background:#f43f5e"></span> FalkorDB: Offline';
      dbStatusBadge.style.color = '#f43f5e';
    }
  } catch (e) {
    dbStatusBadge.innerHTML = '<span class="status-dot" style="background:#f43f5e"></span> FalkorDB: Error';
  }
}

async function refreshAll() {
  await loadWorkspace();
  await loadGraph();
  await loadOwnershipHistory();
}

async function loadWorkspace() {
  try {
    const res = await fetch(`${API_BASE}/workspace`);
    const data = await res.json();
    wsLabel.textContent = data.workspace_id;
    nodeCountEl.textContent = data.node_count;
    edgeCountEl.textContent = data.edge_count;
  } catch (e) {
    console.error('Failed to load workspace:', e);
  }
}

async function loadOwnershipHistory() {
  try {
    const res = await fetch(`${API_BASE}/queries/owner`);
    const data = await res.json();
    renderHistory(data.history || []);
  } catch (e) {
    console.error('Failed to load history:', e);
  }
}

function renderHistory(history) {
  historyContainer.innerHTML = '';
  if (!history || history.length === 0) {
    historyContainer.innerHTML = '<div style="color:#64748b; font-size:0.8rem;">No historical records found.</div>';
    return;
  }

  history.forEach(item => {
    const el = document.createElement('div');
    el.className = `history-item ${item.status === 'ACTIVE' ? 'active' : 'superseded'}`;
    el.innerHTML = `
      <div>
        <div class="fact-title">${item.employee_name} <span style="font-size:0.75rem; color:#94a3b8">(${item.employee_title})</span></div>
        <div class="fact-dates">Valid: ${item.valid_from ? item.valid_from.substring(0, 10) : 'N/A'} ${item.valid_until ? '&rarr; ' + item.valid_until.substring(0, 10) : '&rarr; Present'}</div>
      </div>
      <div>
        <span class="badge ${item.status === 'ACTIVE' ? 'badge-success' : 'badge-warning'}">${item.status}</span>
      </div>
    `;
    historyContainer.appendChild(el);
  });
}

// Run Workflow
async function runWorkflow(goalText) {
  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/workflow/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal: goalText })
    });
    const data = await res.json();
    renderTimeline(data.agent_turns || []);
    renderCitations(data.citations || []);
    if (data.deliverable) {
      renderDeliverable(data.deliverable);
    }
    await refreshAll();
  } catch (e) {
    alert('Workflow execution error: ' + e.message);
  } finally {
    setLoading(false);
  }
}

function renderTimeline(turns) {
  timelineContainer.innerHTML = '';
  if (!turns || turns.length === 0) {
    timelineContainer.innerHTML = '<div class="timeline-empty-state"><p>No turns recorded.</p></div>';
    return;
  }

  const avatars = {
    'emp_chief_of_staff': '👔',
    'emp_eng_manager': '📐',
    'emp_engineer': '⚡',
    'emp_knowledge_mgr': '📚'
  };

  turns.forEach(turn => {
    const card = document.createElement('div');
    card.className = 'employee-turn-card';
    const avatar = avatars[turn.employee_id] || '👤';

    let claimsHtml = '';
    if (turn.claims && turn.claims.length > 0) {
      claimsHtml = `<div class="turn-claims">
        <div style="font-size:0.75rem; font-weight:600; color:#818cf8; margin-bottom:6px;">GROUNDED CLAIMS:</div>
        ${turn.claims.map(c => `
          <div class="claim-item">
            <span class="claim-badge ${c.kind === 'FACT' ? 'badge-success' : 'badge-accent'}">${c.kind}</span>
            <span>${c.text}</span>
            ${c.evidence_ids.map(eid => `<span class="ev-tag" onclick="showEvidence('${eid}')">#${eid}</span>`).join(' ')}
          </div>
        `).join('')}
      </div>`;
    }

    card.innerHTML = `
      <div class="turn-header">
        <div class="turn-agent-info">
          <div class="agent-avatar">${avatar}</div>
          <div>
            <div class="agent-name">${turn.employee_role}</div>
            <div class="agent-role">${turn.employee_id} &bull; Turn ${turn.turn}</div>
          </div>
        </div>
        <span class="badge badge-success">${turn.status}</span>
      </div>
      <div class="turn-summary">${turn.summary}</div>
      ${claimsHtml}
      <div class="turn-footer">
        <div>Next Owner: <strong>${turn.next_owner_id || 'Coordinator (Close)'}</strong></div>
        <div>FalkorDB Persisted: <strong>Yes</strong></div>
      </div>
    `;
    timelineContainer.appendChild(card);
  });
}

function renderCitations(citations) {
  citationsContainer.innerHTML = '';
  citationCountBadge.textContent = `${citations.length} Citations`;

  if (!citations || citations.length === 0) {
    citationsContainer.innerHTML = '<p style="color:#64748b; font-size:0.8rem;">No citations available.</p>';
    return;
  }

  citations.forEach(cit => {
    const card = document.createElement('div');
    card.className = 'citation-card';
    card.innerHTML = `
      <div class="citation-header">
        <span class="citation-id">#${cit.evidence_id}</span>
        <span class="citation-locator">${cit.locator || ''}</span>
      </div>
      <div class="citation-excerpt">"${cit.excerpt}"</div>
    `;
    citationsContainer.appendChild(card);
  });
}

function renderDeliverable(deliv) {
  deliverableCard.style.display = 'block';
  deliverableContent.innerHTML = `
    <div class="deliverable-title">${deliv.title}</div>
    <div class="deliverable-meta">Author: ${deliv.author_name} (${deliv.author_id}) &bull; Status: ${deliv.status}</div>
    <div class="verdict-box">VERDICT: ${deliv.readiness_verdict}</div>
    
    <div class="deliv-section-title">Key Findings:</div>
    <ul class="deliv-list">
      ${(deliv.key_findings || []).map(f => `<li>${f}</li>`).join('')}
    </ul>

    <div class="deliv-section-title">Required Actions Before Release:</div>
    <ul class="deliv-list">
      ${(deliv.required_actions_before_signoff || []).map(a => `<li>${a}</li>`).join('')}
    </ul>

    <div class="deliv-section-title">Grounding Citations:</div>
    <div style="font-size:0.8rem; color:#94a3b8;">
      ${(deliv.sources_cited || []).map(s => `<div>&bull; <strong>${s.title}</strong> [${s.type}] (${s.id})</div>`).join('')}
    </div>
  `;
}

// Quick Queries
async function handleQuickQuery(type) {
  if (type === 'owner') {
    const res = await fetch(`${API_BASE}/queries/owner`);
    const data = await res.json();
    const curr = data.current_owner;
    openModal('Current Owner & Evidence', `
      <div style="font-size:1rem; margin-bottom:12px;">Current Accountable Owner: <strong style="color:#34d399">${curr.name}</strong> (${curr.title})</div>
      <div>Department: <strong>${curr.department}</strong></div>
      <div>Status: <span class="badge badge-success">${curr.status}</span> (Effective: ${curr.valid_from})</div>
      <div class="code-block">FalkorDB Fact ID: ${curr.fact_id}</div>
      <h4 style="margin:12px 0 6px 0; color:#818cf8;">Supporting Evidence:</h4>
      <div class="code-block">${curr.evidence ? curr.evidence.excerpt : 'No excerpt'} (${curr.evidence ? curr.evidence.locator : ''})</div>
      <h4 style="margin:12px 0 6px 0; color:#818cf8;">Originating Source:</h4>
      <div>${curr.source ? curr.source.title : 'N/A'} [${curr.source ? curr.source.type : ''}] &bull; <a href="#" style="color:#38bdf8">${curr.source ? curr.source.uri : ''}</a></div>
    `);
  } else if (type === 'risks') {
    const res = await fetch(`${API_BASE}/queries/risks`);
    const risks = await res.json();
    openModal('Unresolved Release Risks & Blockers', `
      <p style="margin-bottom:14px; color:#cbd5e1;">Retrieved from FalkorDB Ticket & Service graph records:</p>
      ${risks.map(r => `
        <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; margin-bottom:10px; border-left:3px solid #f43f5e;">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong style="color:#f87171">${r.ticket_key}: ${r.title}</strong>
            <span class="badge badge-danger">${r.status}</span>
          </div>
          <div style="font-size:0.85rem; color:#e2e8f0; margin-bottom:6px;">${r.description}</div>
          <div style="font-size:0.75rem; color:#94a3b8;">Affects Service: <strong>${r.service_name}</strong> &bull; Assignee: <strong>${r.assignee_name}</strong></div>
        </div>
      `).join('')}
    `);
  } else if (type === 'decisions') {
    const res = await fetch(`${API_BASE}/queries/decisions`);
    const decs = await res.json();
    openModal('Architectural Decisions & Provenance', `
      ${decs.map(d => `
        <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; margin-bottom:10px; border-left:3px solid #6366f1;">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong style="color:#a5b4fc">${d.decision_id}: ${d.question}</strong>
            <span class="badge badge-accent">${d.status}</span>
          </div>
          <div style="font-size:0.85rem; color:#e2e8f0; margin-bottom:6px;">${d.outcome}</div>
          <div style="font-size:0.75rem; color:#94a3b8;">Decided By: <strong>${d.decided_by}</strong> &bull; Date: <strong>${d.decided_at.substring(0, 10)}</strong> &bull; Doc: <strong>${d.source_title}</strong></div>
        </div>
      `).join('')}
    `);
  } else if (type === 'multi-hop') {
    const res = await fetch(`${API_BASE}/queries/multi-hop`);
    const path = await res.json();
    openModal('Multi-Hop Relationship Path in FalkorDB', `
      <p style="margin-bottom:12px; color:#cbd5e1;">Evaluates <code>Project &rarr; Service &rarr; Ticket/Risk &rarr; Decision &rarr; Active Owner</code>:</p>
      <div class="code-block" style="white-space: pre-wrap; font-size:0.85rem; color:#38bdf8;">${path.relationship_path}</div>
      <div style="margin-top:14px; font-size:0.85rem; line-height:1.6;">
        <div>&bull; <strong>Project:</strong> ${path.project}</div>
        <div>&bull; <strong>Service:</strong> ${path.service}</div>
        <div>&bull; <strong>Unresolved Blocker:</strong> ${path.unresolved_risk_ticket}</div>
        <div>&bull; <strong>Architectural Decision:</strong> ${path.decision}</div>
        <div>&bull; <strong>Current Owner:</strong> ${path.current_owner} (Effective: ${path.owner_effective_date ? path.owner_effective_date.substring(0, 10) : 'N/A'})</div>
      </div>
    `);
  }
}

// Reset Demo
async function handleReset() {
  if (!confirm('Reset workspace to clean initial seeded state?')) return;
  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/reset`, { method: 'POST' });
    const data = await res.json();
    alert(data.message);
    timelineContainer.innerHTML = '<div class="timeline-empty-state"><p>Demo reset complete. Workspace restored to clean initial seed.</p></div>';
    deliverableCard.style.display = 'none';
    citationsContainer.innerHTML = '<p style="color:#64748b; font-size:0.8rem;">Citations cleared.</p>';
    await refreshAll();
  } catch (e) {
    alert('Reset failed: ' + e.message);
  } finally {
    setLoading(false);
  }
}

// Supersede Fact
async function handleSupersede() {
  const note = prompt('Enter ownership transfer note for Payments API v2:', 'Marcus Chen (@marcus) has temporarily assumed operational ownership of Payments API v2 during release audit.');
  if (!note) return;
  try {
    const res = await fetch(`${API_BASE}/freshness/supersede`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: 'proj_payments_v2',
        new_owner_id: 'emp_eng_manager',
        announcement_text: note
      })
    });
    const data = await res.json();
    alert(`Success: Fact superseded! New active owner is ${data.updated_owner.name}. Prior fact marked SUPERSEDED.`);
    await refreshAll();
    openModal('Fact Supersession Audit Trail', `
      <div style="margin-bottom:12px;">Prior fact <code>${data.prior_fact_id}</code> is now <span class="badge badge-warning">SUPERSEDED</span>.</div>
      <div style="margin-bottom:12px;">New fact <code>${data.new_fact_id}</code> is now <span class="badge badge-success">ACTIVE</span> with owner <strong>${data.updated_owner.name}</strong>.</div>
      <div class="code-block">Relationship: (${data.new_fact_id})-[:SUPERSEDES]->(${data.prior_fact_id})</div>
    `);
  } catch (e) {
    alert('Supersede failed: ' + e.message);
  }
}

// Recall Memory
async function handleRecallMemory() {
  try {
    const res = await fetch(`${API_BASE}/memory/recall?query=Payments`);
    const memories = await res.json();
    openModal('Cross-Session FalkorDB Memory Recall (Zero Chat Context)', `
      <p style="margin-bottom:12px; color:#cbd5e1;">Simulating a brand new session with zero conversational context. Retrieved directly from FalkorDB persistent Memory nodes:</p>
      ${memories.map(m => `
        <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; margin-bottom:10px; border-left:3px solid #10b981;">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong style="color:#34d399">${m.memory_id}</strong>
            <span class="badge badge-info">${m.type}</span>
          </div>
          <div style="font-size:0.85rem; color:#e2e8f0; margin-bottom:6px;">${m.content}</div>
          <div style="font-size:0.75rem; color:#94a3b8;">
            Learned from Task: <strong>${m.originating_task ? m.originating_task.title : 'N/A'}</strong> &bull; Created: <strong>${m.created_at.substring(0, 10)}</strong>
          </div>
        </div>
      `).join('')}
    `);
  } catch (e) {
    alert('Memory recall error: ' + e.message);
  }
}

// Generality Check
async function handleGenerality() {
  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/generality/run`, { method: 'POST' });
    const data = await res.json();
    renderTimeline(data.result.agent_turns || []);
    renderCitations(data.result.citations || []);
    alert('Generality check complete: Evaluated Core Platform Infrastructure & Auth Gateway using identical company graph primitives.');
    await refreshAll();
  } catch (e) {
    alert('Generality check error: ' + e.message);
  } finally {
    setLoading(false);
  }
}

// Graph Visualization
async function loadGraph() {
  try {
    const res = await fetch(`${API_BASE}/graph`);
    graphData = await res.json();
    drawGraph(graphData);
  } catch (e) {
    console.error('Failed to load graph:', e);
  }
}

function drawGraph(data) {
  graphSvg.innerHTML = '';
  const width = graphSvg.clientWidth || 500;
  const height = graphSvg.clientHeight || 380;

  if (!data.nodes || data.nodes.length === 0) return;

  // Simple clean circular layout grouped by type
  const typeColors = {
    'Employee': '#6366f1',
    'Project': '#06b6d4',
    'Service': '#3b82f6',
    'Task': '#a855f7',
    'Decision': '#ec4899',
    'Fact': '#10b981',
    'Source': '#f59e0b',
    'Evidence': '#f97316',
    'Deliverable': '#14b8a6'
  };

  const nodePositions = {};
  const total = data.nodes.length;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(centerX, centerY) - 45;

  data.nodes.forEach((n, idx) => {
    const angle = (idx / total) * 2 * Math.PI;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);
    nodePositions[n.id] = { x, y };
  });

  // Render edges
  data.edges.forEach(e => {
    const p1 = nodePositions[e.source];
    const p2 = nodePositions[e.target];
    if (p1 && p2) {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', p1.x);
      line.setAttribute('y1', p1.y);
      line.setAttribute('x2', p2.x);
      line.setAttribute('y2', p2.y);
      line.setAttribute('stroke', 'rgba(255, 255, 255, 0.12)');
      line.setAttribute('stroke-width', '1');
      graphSvg.appendChild(line);
    }
  });

  // Render nodes
  data.nodes.forEach(n => {
    const pos = nodePositions[n.id];
    if (!pos) return;

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.style.cursor = 'pointer';

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', pos.x);
    circle.setAttribute('cy', pos.y);
    circle.setAttribute('r', '7');
    circle.setAttribute('fill', typeColors[n.type] || '#94a3b8');
    circle.setAttribute('stroke', '#fff');
    circle.setAttribute('stroke-width', '1.5');

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', pos.x + 10);
    text.setAttribute('y', pos.y + 4);
    text.setAttribute('fill', '#cbd5e1');
    text.setAttribute('font-size', '9px');
    text.setAttribute('font-family', 'sans-serif');
    text.textContent = n.label ? (n.label.length > 16 ? n.label.substring(0, 14) + '..' : n.label) : n.id;

    g.appendChild(circle);
    g.appendChild(text);

    g.addEventListener('click', () => {
      openModal(`Node: ${n.label || n.id} [${n.type}]`, `
        <div class="code-block">${JSON.stringify(n.properties, null, 2)}</div>
      `);
    });

    graphSvg.appendChild(g);
  });
}

function setLoading(isLoading) {
  btnSpinner.style.display = isLoading ? 'inline-block' : 'none';
  btnText.textContent = isLoading ? 'Coordinating...' : 'Coordinate Employees';
  submitGoalBtn.disabled = isLoading;
  runStarterGoalBtn.disabled = isLoading;
}

function openModal(title, htmlContent) {
  modalTitle.textContent = title;
  modalBody.innerHTML = htmlContent;
  modalBackdrop.classList.add('open');
}

function closeModal() {
  modalBackdrop.classList.remove('open');
}

window.showEvidence = function(eid) {
  openModal(`Evidence: #${eid}`, `
    <p>Loading evidence details for <strong>#${eid}</strong>...</p>
  `);
};
