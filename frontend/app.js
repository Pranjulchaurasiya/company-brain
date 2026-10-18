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
let brain3D = null;
let isDarkMode = false;

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
}

// Initialize App
document.addEventListener('DOMContentLoaded', async () => {
  if (typeof CompanyBrain3D !== 'undefined') {
    brain3D = new CompanyBrain3D('brain3dContainer');
  }
  await checkHealth();
  await refreshAll();
  setupEventListeners();
});

function setupEventListeners() {
  if (resetBtn) resetBtn.addEventListener('click', handleReset);
  if (runStarterGoalBtn) runStarterGoalBtn.addEventListener('click', () => runWorkflow(goalInput.value));
  if (submitGoalBtn) submitGoalBtn.addEventListener('click', () => runWorkflow(goalInput.value));
  if (supersedeBtn) supersedeBtn.addEventListener('click', handleSupersede);
  if (recallMemoryBtn) recallMemoryBtn.addEventListener('click', handleRecallMemory);
  if (generalityBtn) generalityBtn.addEventListener('click', handleGenerality);

  // Quick query chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => handleQuickQuery(chip.dataset.query));
  });

  // FalkorDB Slide-out Drawer Controls
  const falkorDrawer = document.getElementById('falkorDrawer');
  const falkorDockBtn = document.getElementById('falkorDockBtn');
  const falkorDrawerClose = document.getElementById('falkorDrawerClose');
  const navOpenFalkorBtn = document.getElementById('navOpenFalkorBtn');
  const topGetStartedBtn = document.getElementById('topGetStartedBtn');
  const heroGetStartedBtn = document.getElementById('heroGetStartedBtn');
  const requestDemoBtn = document.getElementById('requestDemoBtn');

  window.openFalkorDrawer = function() {
    if (falkorDrawer) falkorDrawer.classList.add('open');
  };
  window.closeFalkorDrawer = function() {
    if (falkorDrawer) falkorDrawer.classList.remove('open');
  };

  if (falkorDockBtn) falkorDockBtn.addEventListener('click', openFalkorDrawer);
  if (navOpenFalkorBtn) navOpenFalkorBtn.addEventListener('click', openFalkorDrawer);
  if (topGetStartedBtn) topGetStartedBtn.addEventListener('click', openFalkorDrawer);
  if (heroGetStartedBtn) heroGetStartedBtn.addEventListener('click', openFalkorDrawer);
  if (falkorDrawerClose) falkorDrawerClose.addEventListener('click', closeFalkorDrawer);
  if (requestDemoBtn) requestDemoBtn.addEventListener('click', () => {
    openTopologyModal();
  });

  // Sensitive tools Popover in Guardrails Frame
  const sensitiveSelectBtn = document.getElementById('sensitiveSelectBtn');
  const guardrailPopover = document.getElementById('guardrailPopover');
  if (sensitiveSelectBtn && guardrailPopover) {
    sensitiveSelectBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      guardrailPopover.style.display = (guardrailPopover.style.display === 'none' || guardrailPopover.style.display === '') ? 'block' : 'none';
    });
    document.querySelectorAll('.q-popover-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        document.querySelectorAll('.q-popover-item').forEach(i => i.classList.remove('checked'));
        item.classList.add('checked');
        const text = item.textContent.trim();
        const span = sensitiveSelectBtn.querySelector('span');
        if (span) span.textContent = text;
        guardrailPopover.style.display = 'none';
      });
    });
    document.addEventListener('click', (e) => {
      if (guardrailPopover && !guardrailPopover.contains(e.target) && e.target !== sensitiveSelectBtn) {
        guardrailPopover.style.display = 'none';
      }
    });
  }

  // Gantt Timeline Tracks click handlers
  document.querySelectorAll('.q-track-row').forEach(row => {
    row.addEventListener('click', () => {
      const agentId = row.dataset.agent;
      openModal(`Employee Agent Track: ${agentId}`, `
        <div style="font-size:14px; line-height:1.6; color:#f8fafc;">
          <div style="margin-bottom:12px;"><strong>Canonical Agent ID:</strong> <code>${agentId}</code></div>
          <div style="margin-bottom:12px;"><strong>Execution State:</strong> <span class="badge badge-success">ACTIVE &bull; FALKORDB GROUNDED</span></div>
          <p style="color:#94a3b8; margin-bottom:16px;">This employee agent maintains stateful execution in FalkorDB graph memory. Re-invocations resume from the exact canonical graph state without duplicated API calls or runaway loops.</p>
          <button class="btn btn-primary btn-sm" onclick="closeModal(); openFalkorDrawer();">Inspect in FalkorDB Swarm Console</button>
        </div>
      `);
    });
  });

  // 3D Viewport Controls
  const rotateToggleBtn = document.getElementById('rotateToggleBtn');
  if (rotateToggleBtn) {
    rotateToggleBtn.addEventListener('click', () => {
      if (brain3D) {
        const active = brain3D.toggleAutoRotate();
        rotateToggleBtn.style.color = active ? 'var(--accent-primary)' : 'var(--text-muted)';
      }
    });
  }

  const resetCamBtn = document.getElementById('resetCamBtn');
  if (resetCamBtn) {
    resetCamBtn.addEventListener('click', () => {
      if (brain3D) brain3D.resetCamera();
    });
  }

  const zoomInBtn = document.getElementById('zoomInBtn');
  if (zoomInBtn) {
    zoomInBtn.addEventListener('click', () => {
      if (brain3D) brain3D.zoomIn();
    });
  }

  const zoomOutBtn = document.getElementById('zoomOutBtn');
  if (zoomOutBtn) {
    zoomOutBtn.addEventListener('click', () => {
      if (brain3D) brain3D.zoomOut();
    });
  }

  const fitCamBtn = document.getElementById('fitCamBtn');
  if (fitCamBtn) {
    fitCamBtn.addEventListener('click', () => {
      if (brain3D) brain3D.fitToBounds();
    });
  }

  const expand3dBtn = document.getElementById('expand3dBtn');
  if (expand3dBtn) {
    expand3dBtn.addEventListener('click', () => {
      openTopologyModal();
    });
  }

  // Ingestion Tabs
  const tabGithubBtn = document.getElementById('tabGithubBtn');
  const tabDocBtn = document.getElementById('tabDocBtn');
  const tabInvestigatorBtn = document.getElementById('tabInvestigatorBtn');
  const githubIngestSection = document.getElementById('githubIngestSection');
  const docIngestSection = document.getElementById('docIngestSection');
  const investigatorSection = document.getElementById('investigatorSection');

  function setActiveIngestTab(activeTab, activeSection) {
    [tabGithubBtn, tabDocBtn, tabInvestigatorBtn].forEach(btn => {
      if (btn) btn.classList.toggle('active', btn === activeTab);
    });
    [githubIngestSection, docIngestSection, investigatorSection].forEach(sec => {
      if (sec) sec.style.display = (sec === activeSection) ? 'block' : 'none';
    });
  }

  if (tabGithubBtn) tabGithubBtn.addEventListener('click', () => setActiveIngestTab(tabGithubBtn, githubIngestSection));
  if (tabDocBtn) tabDocBtn.addEventListener('click', () => setActiveIngestTab(tabDocBtn, docIngestSection));
  if (tabInvestigatorBtn) tabInvestigatorBtn.addEventListener('click', () => setActiveIngestTab(tabInvestigatorBtn, investigatorSection));

  // GitHub Ingestion Action
  const importGithubBtn = document.getElementById('importGithubBtn');
  const githubRepoInput = document.getElementById('githubRepoInput');
  const ingestStatusMsg = document.getElementById('ingestStatusMsg');

  if (importGithubBtn) {
    importGithubBtn.addEventListener('click', async () => {
      const url = githubRepoInput ? githubRepoInput.value.trim() : '';
      if (!url) return;
      importGithubBtn.disabled = true;
      const spinner = document.getElementById('importGithubSpinner');
      if (spinner) spinner.classList.remove('hidden');
      if (ingestStatusMsg) {
        ingestStatusMsg.style.display = 'block';
        ingestStatusMsg.className = 'ingest-status-msg';
        ingestStatusMsg.textContent = 'Connecting to public GitHub API and ingesting documentation...';
      }

      try {
        const res = await fetch(`${API_BASE}/ingest/github`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repo_url: url })
        });
        const data = await res.json();
        if (res.ok && data.status === 'INGESTED_SUCCESS') {
          if (ingestStatusMsg) {
            ingestStatusMsg.className = 'ingest-status-msg success';
            let extra = '';
            if (data.skipped_files && data.skipped_files.length > 0) {
              extra = ` (${data.skipped_files.length} non-text/oversized file(s) skipped)`;
            }
            ingestStatusMsg.textContent = `✓ Ingested ${data.sources_created} file(s) and ${data.evidence_created} grounded evidence records from ${data.project_name}.${extra}`;
          }
          await refreshAll();
        } else if (res.ok && data.status === 'INGESTION_PARTIAL') {
          if (ingestStatusMsg) {
            ingestStatusMsg.className = 'ingest-status-msg warning';
            const failCount = data.files_failed ? data.files_failed.length : 0;
            ingestStatusMsg.textContent = `⚠ Partial Import: ${data.sources_created} file(s) imported, but ${failCount} file(s) failed to download.`;
          }
          await refreshAll();
        } else {
          if (ingestStatusMsg) {
            ingestStatusMsg.className = 'ingest-status-msg error';
            ingestStatusMsg.textContent = `Error: ${data.detail?.error || data.error || 'Failed to import repository.'}`;
          }
        }
      } catch (err) {
        if (ingestStatusMsg) {
          ingestStatusMsg.className = 'ingest-status-msg error';
          ingestStatusMsg.textContent = `Network error: ${err.message}`;
        }
      } finally {
        importGithubBtn.disabled = false;
        if (spinner) spinner.classList.add('hidden');
      }
    });
  }

  // Document Ingestion Action
  const importDocBtn = document.getElementById('importDocBtn');
  const docTitleInput = document.getElementById('docTitleInput');
  const docContentInput = document.getElementById('docContentInput');

  if (importDocBtn) {
    importDocBtn.addEventListener('click', async () => {
      const title = docTitleInput ? docTitleInput.value.trim() : '';
      const content = docContentInput ? docContentInput.value.trim() : '';
      if (!title || !content) {
        alert('Please provide both document title and content.');
        return;
      }
      importDocBtn.disabled = true;
      const spinner = document.getElementById('importDocSpinner');
      if (spinner) spinner.classList.remove('hidden');

      try {
        const res = await fetch(`${API_BASE}/ingest/document`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, content })
        });
        const data = await res.json();
        if (res.ok && data.status === 'INGESTED_SUCCESS') {
          if (ingestStatusMsg) {
            ingestStatusMsg.style.display = 'block';
            ingestStatusMsg.className = 'ingest-status-msg success';
            ingestStatusMsg.textContent = `✓ Ingested '${title}' with ${data.evidence_created} evidence excerpt(s) into FalkorDB.`;
          }
          if (docContentInput) docContentInput.value = '';
          await refreshAll();
        } else {
          if (ingestStatusMsg) {
            ingestStatusMsg.style.display = 'block';
            ingestStatusMsg.className = 'ingest-status-msg error';
            ingestStatusMsg.textContent = `Error: ${data.detail?.error || data.error || 'Failed to import document.'}`;
          }
        }
      } catch (err) {
        if (ingestStatusMsg) {
          ingestStatusMsg.style.display = 'block';
          ingestStatusMsg.className = 'ingest-status-msg error';
          ingestStatusMsg.textContent = `Network error: ${err.message}`;
        }
      } finally {
        importDocBtn.disabled = false;
        if (spinner) spinner.classList.add('hidden');
      }
    });
  }

  // Engineering Contribution Investigator Action
  const importHistoryBtn = document.getElementById('importHistoryBtn');
  const investigatorRepoInput = document.getElementById('investigatorRepoInput');
  const investigatorStatusMsg = document.getElementById('investigatorStatusMsg');
  const importHistorySpinner = document.getElementById('importHistorySpinner');

  if (importHistoryBtn) {
    importHistoryBtn.addEventListener('click', async () => {
      const url = investigatorRepoInput ? investigatorRepoInput.value.trim() : '';
      if (!url) return;
      importHistoryBtn.disabled = true;
      if (importHistorySpinner) importHistorySpinner.classList.remove('hidden');
      if (investigatorStatusMsg) {
        investigatorStatusMsg.style.display = 'block';
        investigatorStatusMsg.className = 'ingest-status-msg';
        investigatorStatusMsg.textContent = 'Importing bounded GitHub repository history (commits, PRs, issues, files, reviews)...';
      }

      try {
        const res = await fetch(`${API_BASE}/investigator/import`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repo_url: url })
        });
        const data = await res.json();
        if (res.ok && data.status === 'IMPORTED_SUCCESS') {
          if (investigatorStatusMsg) {
            investigatorStatusMsg.className = 'ingest-status-msg success';
            investigatorStatusMsg.innerHTML = `
              <strong>✓ Imported ${escapeHtml(data.repository.full_name)}</strong><br>
              <div style="font-size:11px; margin-top:4px; color:#cbd5e1;">
                Commits: ${data.commits_imported} | PRs: ${data.pull_requests_imported} | 
                Issues: ${data.issues_imported} | Contributors: ${data.contributors_imported} | 
                Files: ${data.files_imported} | Explicit Resolutions: ${data.explicit_resolutions_linked}
              </div>
            `;
          }
          await refreshAll();
        } else {
          if (investigatorStatusMsg) {
            investigatorStatusMsg.className = 'ingest-status-msg error';
            investigatorStatusMsg.textContent = `Error: ${data.detail?.error || data.error || 'Failed to import repository history.'}`;
          }
        }
      } catch (err) {
        if (investigatorStatusMsg) {
          investigatorStatusMsg.className = 'ingest-status-msg error';
          investigatorStatusMsg.textContent = `Network error: ${err.message}`;
        }
      } finally {
        importHistoryBtn.disabled = false;
        if (importHistorySpinner) importHistorySpinner.classList.add('hidden');
      }
    });
  }

  // Person Contribution Read-Only Query Handler
  const lookupPersonBtn = document.getElementById('lookupPersonBtn');
  const investigatorUsernameInput = document.getElementById('investigatorUsernameInput');
  const personContribResultBox = document.getElementById('personContribResultBox');

  if (lookupPersonBtn) {
    lookupPersonBtn.addEventListener('click', async () => {
      const username = investigatorUsernameInput ? investigatorUsernameInput.value.trim() : '';
      if (!username) return;
      lookupPersonBtn.disabled = true;
      if (personContribResultBox) {
        personContribResultBox.style.display = 'block';
        personContribResultBox.innerHTML = '<span style="color:#94a3b8;">Querying FalkorDB graph for person contributions...</span>';
      }

      try {
        const res = await fetch(`${API_BASE}/investigator/contributions?username=${encodeURIComponent(username)}`);
        const data = await res.json();
        if (res.ok && data.status === 'SUCCESS') {
          const person = data.person;
          const stats = data.stats;
          let html = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:6px;">
              <div>
                <strong style="color:#f8fafc; font-size:13px;">${escapeHtml(person.name || person.login)}</strong>
                <span style="color:#94a3b8; font-size:11px;">(@${escapeHtml(person.login)})</span>
              </div>
              <a href="${escapeHtml(person.url || '#')}" target="_blank" rel="noopener" style="color:#60a5fa; font-size:11px; text-decoration:none;">View Profile &rarr;</a>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; font-size:11px;">
              <span class="badge badge-accent">Commits: ${stats.commits}</span>
              <span class="badge badge-info">PRs: ${stats.pull_requests}</span>
              <span class="badge badge-warning">Reviews: ${stats.reviews}</span>
              <span class="badge badge-success">Issues Resolved: ${stats.explicit_issues_resolved}</span>
            </div>
          `;

          if (data.authored_commits && data.authored_commits.length > 0) {
            html += `<div style="font-weight:600; color:#cbd5e1; margin-top:8px; margin-bottom:4px; font-size:11px;">Authored Commits:</div><ul style="margin:0; padding-left:16px; color:#94a3b8; font-size:11px;">`;
            data.authored_commits.slice(0, 5).forEach(c => {
              const url = c.url ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener" style="color:#60a5fa; margin-left:4px;">${c.commit_id ? c.commit_id.substring(0, 7) : 'link'}</a>` : '';
              html += `<li>${escapeHtml((c.message || '').split('\n')[0])} ${url}</li>`;
            });
            if (data.authored_commits.length > 5) html += `<li>...and ${data.authored_commits.length - 5} more</li>`;
            html += `</ul>`;
          }

          if (data.opened_pull_requests && data.opened_pull_requests.length > 0) {
            html += `<div style="font-weight:600; color:#cbd5e1; margin-top:8px; margin-bottom:4px; font-size:11px;">Opened Pull Requests:</div><ul style="margin:0; padding-left:16px; color:#94a3b8; font-size:11px;">`;
            data.opened_pull_requests.slice(0, 5).forEach(pr => {
              const url = pr.url ? `<a href="${escapeHtml(pr.url)}" target="_blank" rel="noopener" style="color:#60a5fa; margin-left:4px;">#${pr.number}</a>` : `#${pr.number}`;
              html += `<li>${url}: ${escapeHtml(pr.title)} <span class="badge badge-sm">${escapeHtml(pr.state || '')}</span></li>`;
            });
            if (data.opened_pull_requests.length > 5) html += `<li>...and ${data.opened_pull_requests.length - 5} more</li>`;
            html += `</ul>`;
          }

          if (data.explicitly_resolved_issues && data.explicitly_resolved_issues.length > 0) {
            html += `<div style="font-weight:600; color:#10b981; margin-top:8px; margin-bottom:4px; font-size:11px;">Explicitly Linked Resolved Issues:</div><ul style="margin:0; padding-left:16px; color:#a7f3d0; font-size:11px;">`;
            data.explicitly_resolved_issues.forEach(iss => {
              const url = iss.url ? `<a href="${escapeHtml(iss.url)}" target="_blank" rel="noopener" style="color:#34d399; margin-left:4px;">#${iss.number}</a>` : `#${iss.number}`;
              html += `<li>${url}: ${escapeHtml(iss.title)} <span style="color:#94a3b8;">(via PR #${iss.resolved_by_pr_number})</span></li>`;
            });
            html += `</ul>`;
          }

          personContribResultBox.innerHTML = html;
        } else {
          personContribResultBox.innerHTML = `<span style="color:#ef4444;">${data.detail?.error || data.error || 'Person not found in graph.'}</span>`;
        }
      } catch (err) {
        personContribResultBox.innerHTML = `<span style="color:#ef4444;">Query error: ${err.message}</span>`;
      } finally {
        lookupPersonBtn.disabled = false;
      }
    });
  }

  // =========================================================================
  // Company Brain: Engineering Change Room Handlers
  // =========================================================================
  const changeProposalInput = document.getElementById('changeProposalInput');
  const analyzeChangeBtn = document.getElementById('analyzeChangeBtn');
  const analyzeChangeSpinner = document.getElementById('analyzeChangeSpinner');
  const changeOwnerBtn = document.getElementById('changeOwnerBtn');
  const currentOwnerBadge = document.getElementById('currentOwnerBadge');
  const changeOwnerNotice = document.getElementById('changeOwnerNotice');
  const changeRoomResultBox = document.getElementById('changeRoomResultBox');
  const impactPathBreadcrumbs = document.getElementById('impactPathBreadcrumbs');
  const followupTaskTitle = document.getElementById('followupTaskTitle');
  const followupTaskMeta = document.getElementById('followupTaskMeta');
  const affectedEntitiesList = document.getElementById('affectedEntitiesList');
  const requiredReviewersList = document.getElementById('requiredReviewersList');
  const agentMessagesFeed = document.getElementById('agentMessagesFeed');
  const messageCountBadge = document.getElementById('messageCountBadge');

  // Change chip quick clicks
  document.querySelectorAll('.change-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      if (changeProposalInput) {
        changeProposalInput.value = chip.dataset.change || chip.textContent.trim();
      }
    });
  });

  // Toggle Owner Demo Action
  if (changeOwnerBtn) {
    changeOwnerBtn.addEventListener('click', async () => {
      changeOwnerBtn.disabled = true;
      try {
        const res = await fetch(`${API_BASE}/change-room/toggle-owner`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (res.ok && data.status === 'SUPERSEDED_SUCCESS') {
          const newName = data.updated_owner?.name || (data.new_owner_id === 'emp_eng_manager' ? 'Marcus Chen' : 'Asha Patel');
          if (currentOwnerBadge) currentOwnerBadge.textContent = `Owner: ${newName}`;
          if (changeOwnerNotice) {
            changeOwnerNotice.style.display = 'block';
            changeOwnerNotice.textContent = `✓ Operational State Changed: Technical owner superseded to ${newName} in FalkorDB graph.`;
            setTimeout(() => { changeOwnerNotice.style.display = 'none'; }, 6000);
          }
          await refreshAll();
        }
      } catch (err) {
        alert(`Failed to change owner: ${err.message}`);
      } finally {
        changeOwnerBtn.disabled = false;
      }
    });
  }

  // Analyze Change Impact Action
  if (analyzeChangeBtn) {
    analyzeChangeBtn.addEventListener('click', async () => {
      const proposal = changeProposalInput ? changeProposalInput.value.trim() : '';
      if (!proposal) return;

      analyzeChangeBtn.disabled = true;
      if (analyzeChangeSpinner) analyzeChangeSpinner.classList.remove('hidden');

      try {
        const res = await fetch(`${API_BASE}/change-room/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ proposed_change: proposal })
        });
        const data = await res.json();
        if (res.ok && data.change_id) {
          if (changeRoomResultBox) changeRoomResultBox.style.display = 'block';

          // 0. Render Final Grounded Answer Banner
          const finalAnswerBox = document.getElementById('finalAnswerBox');
          const finalAnswerText = document.getElementById('finalAnswerText');
          const questionIntentBadge = document.getElementById('questionIntentBadge');
          if (finalAnswerBox && data.final_answer) {
            finalAnswerBox.style.display = 'block';
            if (finalAnswerText) finalAnswerText.textContent = data.final_answer;
            if (questionIntentBadge) questionIntentBadge.textContent = data.question_intent || 'GENERAL_CHANGE_IMPACT';
          }

          // 1. Render 6-Agent Collaboration Activity Timeline
          const timelineContainer = document.getElementById('agentTimelineSteps');
          const workflowStateBadge = document.getElementById('workflowStateBadge');
          if (timelineContainer && data.timeline) {
            let timelineHtml = '';
            data.timeline.forEach(step => {
              const badgeColor = step.status === 'COMPLETED' ? '#10b981' :
                                 step.status === 'APPROVED' ? '#10b981' :
                                 step.status === 'REVIEW' ? '#f59e0b' :
                                 step.status === 'IN_PROGRESS' ? '#38bdf8' :
                                 step.status === 'ASSIGNED' ? '#818cf8' : '#c084fc';
              timelineHtml += `
                <div style="display:flex; align-items:flex-start; gap:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:6px; padding:6px 10px; font-size:11px;">
                  <span style="background:${badgeColor}22; color:${badgeColor}; border:1px solid ${badgeColor}66; border-radius:3px; padding:1px 5px; font-weight:700; font-size:10px;">Turn ${step.step}</span>
                  <div style="flex:1;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                      <strong style="color:#f8fafc;">${escapeHtml(step.agent)} <span style="font-weight:normal; color:#94a3b8;">(${escapeHtml(step.agent_id)})</span></strong>
                      <span style="color:${badgeColor}; font-weight:600; font-size:10px;">${escapeHtml(step.status)}</span>
                    </div>
                    <div style="color:#cbd5e1; margin-top:2px;">${escapeHtml(step.summary)}</div>
                    <div style="font-size:10px; color:#64748b; margin-top:1px;">Action: ${escapeHtml(step.action)} &bull; Msg ID: <code>${escapeHtml(step.message_id)}</code></div>
                  </div>
                </div>
              `;
            });
            timelineContainer.innerHTML = timelineHtml;
            if (workflowStateBadge && data.task_status_progression) {
              const lastStatus = data.task_status_progression[data.task_status_progression.length - 1];
              workflowStateBadge.textContent = lastStatus;
              workflowStateBadge.className = `badge badge-${lastStatus === 'COMPLETED' ? 'success' : 'warning'}`;
            }
          }

          // 2. Render Canonical Sequential Impact Path
          if (impactPathBreadcrumbs && data.impact_path) {
            let breadcrumbsHtml = '';
            data.impact_path.forEach((node, idx) => {
              const isUnproven = node.label && node.label.includes('Not documented');
              const badgeClass = isUnproven ? 'background:rgba(239,68,68,0.2); color:#fca5a5; border:1px solid #ef4444;' :
                                 node.type === 'PROPOSED_CHANGE' ? 'background:rgba(192,132,252,0.25); color:#e9d5ff; border:1px solid #c084fc;' :
                                 node.type === 'TASK' ? 'background:rgba(16,185,129,0.25); color:#6ee7b7; border:1px solid #10b981;' :
                                 node.type === 'OWNER' ? 'background:rgba(59,130,246,0.25); color:#93c5fd; border:1px solid #3b82f6;' :
                                 'background:rgba(255,255,255,0.08); color:#cbd5e1; border:1px solid rgba(255,255,255,0.15);';

              breadcrumbsHtml += `
                <div style="display:inline-flex; align-items:center; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:600; ${badgeClass}">
                  <span style="font-size:9px; text-transform:uppercase; color:#94a3b8; margin-right:4px;">${node.type}:</span>
                  <span>${escapeHtml(node.label)}</span>
                </div>
              `;
              if (idx < data.impact_path.length - 1) {
                breadcrumbsHtml += `<span style="color:#a855f7; font-weight:bold; font-size:12px;">&rarr;</span>`;
              }
            });
            impactPathBreadcrumbs.innerHTML = breadcrumbsHtml;
          }

          // 3. Render Generated GitHub Follow-Up Issue Artifact
          if (data.generated_github_issue) {
            const gh = data.generated_github_issue;
            const titleEl = document.getElementById('githubIssueTitle');
            const metaEl = document.getElementById('githubIssueMeta');
            const bodyEl = document.getElementById('githubIssueBody');
            if (titleEl) titleEl.textContent = gh.title;
            if (metaEl) {
              metaEl.innerHTML = `
                <span><strong>Repo:</strong> <code style="color:#38bdf8;">${escapeHtml(gh.repository)}</code></span>
                <span><strong>Assignees:</strong> ${gh.assignees.map(a => `@${escapeHtml(a)}`).join(', ')}</span>
                <span><strong>Labels:</strong> ${gh.labels.map(l => `<span class="badge badge-sm badge-accent" style="font-size:9px;">${escapeHtml(l)}</span>`).join(' ')}</span>
                <span><strong>State:</strong> <span class="badge badge-sm badge-success" style="font-size:9px;">${escapeHtml(gh.state)}</span></span>
              `;
            }
            if (bodyEl) bodyEl.textContent = gh.body;

            const copyBtn = document.getElementById('copyIssueMdBtn');
            if (copyBtn) {
              copyBtn.onclick = () => {
                navigator.clipboard.writeText(gh.body).then(() => {
                  copyBtn.textContent = 'Copied!';
                  setTimeout(() => { copyBtn.textContent = 'Copy Markdown'; }, 2000);
                });
              };
            }
          }

          // 4. Render Created Follow-up Work Task
          if (data.followup_task) {
            const ft = data.followup_task;
            if (followupTaskTitle) followupTaskTitle.textContent = ft.title;
            if (followupTaskMeta) {
              followupTaskMeta.innerHTML = `
                <span><strong>Assignee:</strong> <span style="color:#60a5fa;">${escapeHtml(ft.assigned_to_name)}</span></span>
                <span><strong>Priority:</strong> <span class="badge badge-accent" style="font-size:9px;">${ft.priority}</span></span>
                <span><strong>Task ID:</strong> <code>${ft.id}</code></span>
                ${ft.linked_service ? `<span><strong>Service:</strong> ${escapeHtml(ft.linked_service)}</span>` : ''}
              `;
            }
            if (currentOwnerBadge && data.current_owner) {
              currentOwnerBadge.textContent = `Owner: ${data.current_owner.name}`;
            }
          }

          // 5. Render Affected Entities
          if (affectedEntitiesList) {
            let html = '<ul style="margin:0; padding-left:14px; line-height:1.6;">';
            if (data.affected_services && data.affected_services.length > 0) {
              data.affected_services.forEach(s => {
                html += `<li><strong>Service:</strong> ${escapeHtml(s.name)} <span class="badge badge-sm" style="font-size:9px;">${s.status}</span></li>`;
              });
            }
            if (data.affected_files && data.affected_files.length > 0) {
              data.affected_files.forEach(f => {
                const url = f.url ? `<a href="${escapeHtml(f.url)}" target="_blank" rel="noopener" style="color:#60a5fa;">${escapeHtml(f.filename)}</a>` : escapeHtml(f.filename);
                html += `<li><strong>File:</strong> ${url}</li>`;
              });
            }
            if (data.related_pull_requests && data.related_pull_requests.length > 0) {
              data.related_pull_requests.forEach(pr => {
                html += `<li><strong>PR #${pr.number}:</strong> ${escapeHtml(pr.title)}</li>`;
              });
            }
            if (data.related_issues && data.related_issues.length > 0) {
              data.related_issues.forEach(iss => {
                html += `<li><strong>Issue #${iss.number}:</strong> ${escapeHtml(iss.title)}</li>`;
              });
            }
            html += '</ul>';
            affectedEntitiesList.innerHTML = html;
          }

          // 6. Render Reviewers & Decision
          if (requiredReviewersList) {
            let html = '<ul style="margin:0; padding-left:14px; line-height:1.6;">';
            if (data.architecture_decisions && data.architecture_decisions.length > 0) {
              data.architecture_decisions.forEach(d => {
                html += `<li><strong>Decision:</strong> ${escapeHtml(d.outcome || d.id)}</li>`;
              });
            }
            if (data.deliverable && data.deliverable.required_reviewers) {
              html += `<li><strong>Required Reviewers:</strong> ${data.deliverable.required_reviewers.join(', ')}</li>`;
            }
            if (data.deliverable && data.deliverable.risks && data.deliverable.risks.length > 0) {
              html += `<li><strong>Key Risk:</strong> ${escapeHtml(data.deliverable.risks[0])}</li>`;
            }
            html += '</ul>';
            requiredReviewersList.innerHTML = html;
          }

          // 7. Render FalkorDB Agent Message Bus Feed
          if (agentMessagesFeed && data.agent_messages) {
            if (messageCountBadge) messageCountBadge.textContent = `${data.agent_messages.length} Messages`;
            let feedHtml = '';
            data.agent_messages.forEach(m => {
              const typeColor = m.message_type === 'TASK_ASSIGNED' ? '#c084fc' :
                                m.message_type === 'REVIEW_REQUEST' ? '#f59e0b' :
                                m.message_type === 'REVIEW_RESULT' ? '#10b981' : '#60a5fa';
              feedHtml += `
                <div style="background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.06); border-left:3px solid ${typeColor}; border-radius:4px; padding:6px 10px; font-size:11px;">
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                    <div>
                      <strong style="color:#f8fafc;">${escapeHtml(m.sender_id)}</strong>
                      <span style="color:#94a3b8;">&rarr;</span>
                      <strong style="color:#f8fafc;">${escapeHtml(m.receiver_id)}</strong>
                    </div>
                    <span class="badge" style="background:${typeColor}22; color:${typeColor}; border:1px solid ${typeColor}66; font-size:9px; padding:1px 5px;">${m.message_type}</span>
                  </div>
                  <div style="color:#cbd5e1; margin-top:2px;">${escapeHtml(m.content)}</div>
                  ${m.evidence_ids && m.evidence_ids.length > 0 ? `
                    <div style="font-size:10px; color:#94a3b8; margin-top:3px;">
                      <strong>Evidence Cited:</strong> ${m.evidence_ids.map(e => `<code>${escapeHtml(e)}</code>`).join(', ')}
                    </div>
                  ` : ''}
                </div>
              `;
            });
            agentMessagesFeed.innerHTML = feedHtml;
          }

          await refreshAll();
        } else {
          alert(`Analysis error: ${data.detail?.error || data.error || 'Failed to analyze change.'}`);
        }
      } catch (err) {
        alert(`Request error: ${err.message}`);
      } finally {
        analyzeChangeBtn.disabled = false;
        if (analyzeChangeSpinner) analyzeChangeSpinner.classList.add('hidden');
      }
    });
  }

  // Ask Question / Evidence Retrieval Handler
  const askBtn = document.getElementById('askBtn');
  const askInput = document.getElementById('askInput');
  const askResultBox = document.getElementById('askResultBox');
  const askVerdictBadge = document.getElementById('askVerdictBadge');
  const askReasoningMode = document.getElementById('askReasoningMode');
  const askAnswerText = document.getElementById('askAnswerText');
  const askCheckedSources = document.getElementById('askCheckedSources');

  async function handleAskQuestion(query) {
    if (!query) return;
    if (askBtn) askBtn.disabled = true;
    const spinner = document.getElementById('askSpinner');
    if (spinner) spinner.classList.remove('hidden');

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      const data = await res.json();
      if (askResultBox) {
        askResultBox.style.display = 'block';
        if (askVerdictBadge) {
          askVerdictBadge.textContent = data.verdict;
          askVerdictBadge.className = `badge ${data.has_evidence ? 'badge-success' : 'badge-warning'}`;
        }
        if (askReasoningMode) {
          askReasoningMode.textContent = `Mode: ${data.reasoning_mode || 'Graph Retrieval'}`;
        }
        if (askAnswerText) {
          askAnswerText.textContent = data.answer;
        }
        if (askCheckedSources) {
          askCheckedSources.textContent = `Checked in FalkorDB: ${(data.checked_sources || []).join(' • ')}`;
        }
        if (data.citations && data.citations.length > 0) {
          renderCitations(data.citations);
        }
      }
    } catch (err) {
      if (askAnswerText) askAnswerText.textContent = `Error asking graph: ${err.message}`;
    } finally {
      if (askBtn) askBtn.disabled = false;
      if (spinner) spinner.classList.add('hidden');
    }
  }

  if (askBtn && askInput) {
    askBtn.addEventListener('click', () => handleAskQuestion(askInput.value.trim()));
    askInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleAskQuestion(askInput.value.trim());
    });
  }

  document.querySelectorAll('.ask-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-q');
      if (askInput) askInput.value = q;
      handleAskQuestion(q);
    });
  });

  window.onNode3DClick = function(node) {
    const props = node.properties || {};
    let contentSnippet = '';
    if (props.excerpt) {
      contentSnippet = `<h4 style="margin:12px 0 6px 0; color:#34d399;">Evidence Excerpt:</h4><div class="code-block" style="white-space:pre-wrap;">${props.excerpt}</div>`;
    } else if (props.content) {
      contentSnippet = `<h4 style="margin:12px 0 6px 0; color:#818cf8;">Source Content:</h4><div class="code-block" style="white-space:pre-wrap; max-height:220px; overflow-y:auto;">${props.content.substring(0, 800)}...</div>`;
    }

    openModal(`Node: ${node.label || node.id} [${node.type}]`, `
      <div style="margin-bottom:12px; font-size:1rem;">
        Type: <span class="badge badge-accent">${node.type}</span> &bull; ID: <code>${node.id}</code>
      </div>
      ${props.source_uri ? `<div style="font-size:12px; margin-bottom:8px; color:#38bdf8;">URI: <a href="${props.source_uri}" target="_blank" style="color:#38bdf8;">${props.source_uri}</a></div>` : ''}
      ${contentSnippet}
      <h4 style="margin:12px 0 6px 0; color:var(--accent-primary);">Canonical Properties in FalkorDB:</h4>
      <div class="code-block">${JSON.stringify(props, null, 2)}</div>
    `);
  };

  // Modal
  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
  if (modalBackdrop) {
    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop) closeModal();
    });
  }

  // Initialize Particle Vortex
  initParticleVortex();
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    if (data.status === 'HEALTHY') {
      dbStatusBadge.innerHTML = `<span class="status-dot healthy"></span> FalkorDB: Live (Port ${data.port || 6380})`;
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
    if (wsLabel) wsLabel.textContent = data.workspace_id;
    if (nodeCountEl) nodeCountEl.textContent = data.node_count;
    if (edgeCountEl) edgeCountEl.textContent = data.edge_count;
    
    // Update Qronos Telemetry Strip KPIs
    const kpiNodes = document.getElementById('kpiNodes');
    const kpiEdges = document.getElementById('kpiEdges');
    if (kpiNodes) kpiNodes.textContent = `${data.node_count} Objects`;
    if (kpiEdges) kpiEdges.textContent = `${data.edge_count} Edges`;
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
    timelineContainer.innerHTML = `
      <div class="timeline-empty-state">
        <div class="empty-icon-wrap"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></div>
        <h3>No Turns Recorded</h3>
        <p>Trigger a workflow to begin autonomous agent coordination.</p>
      </div>`;
    return;
  }

  // Update Qronos Agent Roster state pills
  const agentMap = {
    'emp_chief_of_staff': { key: 'chief', name: 'Chief of Staff' },
    'emp_eng_manager': { key: 'eng-mgr', name: 'Engineering Manager' },
    'emp_engineer': { key: 'engineer', name: 'Staff Engineer' },
    'emp_knowledge_mgr': { key: 'km', name: 'Knowledge Manager' }
  };

  // Reset states
  Object.values(agentMap).forEach(a => {
    const st = document.getElementById(`state-${a.key}`);
    const cd = document.getElementById(`agentCard-${a.key}`);
    if (st) { st.textContent = 'IDLE'; st.className = 'agent-state-pill state-idle'; }
    if (cd) cd.classList.remove('agent-active');
  });

  const avatars = {
    'emp_chief_of_staff': '<span class="agent-tag tag-cs">CS</span>',
    'emp_eng_manager': '<span class="agent-tag tag-em">EM</span>',
    'emp_engineer': '<span class="agent-tag tag-se">SE</span>',
    'emp_knowledge_mgr': '<span class="agent-tag tag-km">KM</span>'
  };

  turns.forEach(turn => {
    // Mark agent active & completed in top deck
    const agentMeta = agentMap[turn.employee_id];
    if (agentMeta) {
      const st = document.getElementById(`state-${agentMeta.key}`);
      const cd = document.getElementById(`agentCard-${agentMeta.key}`);
      if (st) { st.textContent = 'DONE'; st.className = 'agent-state-pill state-done'; }
      if (cd) cd.classList.add('agent-active');
    }

    const card = document.createElement('div');
    card.className = 'employee-turn-card';
    const avatar = avatars[turn.employee_id] || '<span class="agent-tag tag-ai">AI</span>';

    let claimsHtml = '';
    if (turn.claims && turn.claims.length > 0) {
      claimsHtml = `
        <div class="turn-claims">
          <div class="claims-title">GROUNDED CLAIMS (FALKORDB VERIFIED)</div>
          ${turn.claims.map(c => `
            <div class="claim-item">
              <span class="claim-badge ${c.kind === 'FACT' ? 'badge-success' : 'badge-accent'}">${c.kind}</span>
              <span>${c.text}</span>
              ${(c.evidence_ids || []).map(eid => `<span class="ev-tag" onclick="showEvidence('${eid}')">#${eid}</span>`).join(' ')}
            </div>
          `).join('')}
        </div>`;
    }

    card.innerHTML = `
      <div class="turn-header">
        <div class="turn-agent-info">
          <div class="turn-agent-avatar">${avatar}</div>
          <div>
            <div class="turn-agent-title">${turn.employee_role}</div>
            <div class="turn-agent-meta">${turn.employee_id} &bull; Turn ${turn.turn}</div>
          </div>
        </div>
        <span class="badge badge-success">${turn.status}</span>
      </div>
      <div class="turn-summary">${turn.summary}</div>
      ${claimsHtml}
      <div class="turn-footer">
        <div>Next Owner: <strong>${turn.next_owner_id || 'Coordinator (Close)'}</strong></div>
        <div>FalkorDB Persisted: <strong>Yes (Canonical)</strong></div>
      </div>
    `;
    timelineContainer.appendChild(card);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderCitations(citations) {
  citationsContainer.innerHTML = '';
  citationCountBadge.textContent = `${citations.length} Citations`;

  if (!citations || citations.length === 0) {
    citationsContainer.innerHTML = '<p style="color:#64748b; font-size:12px; padding:12px; text-align:center;">No citations available.</p>';
    return;
  }

  citations.forEach(cit => {
    const card = document.createElement('div');
    card.className = 'citation-card';

    // Parse clean display filename and line range
    let fileDisplay = cit.source_title || 'Source';
    let lineRange = '';
    const locator = cit.locator || '';

    if (locator.includes('#')) {
      const parts = locator.split('#');
      fileDisplay = parts[0] || fileDisplay;
      lineRange = parts[1] || '';
    } else if (locator.includes(':')) {
      const parts = locator.split(':');
      fileDisplay = parts[0] || fileDisplay;
      lineRange = parts[1] ? `L${parts[1]}` : '';
    }

    // Format clean short evidence ID (e.g. #ev_12db...f539)
    const rawId = cit.evidence_id || '';
    const shortId = rawId.length > 20 ? `${rawId.slice(0, 9)}...${rawId.slice(-6)}` : rawId;

    // Clean excerpt text: strip markdown header hashes and excessive backticks
    let excerptText = (cit.excerpt || '').trim();
    if (excerptText.startsWith('#### ') || excerptText.startsWith('### ') || excerptText.startsWith('## ')) {
      excerptText = excerptText.replace(/^#{1,6}\s+/, '');
    }

    const sourceLinkHtml = cit.source_uri ? `
      <a href="${cit.source_uri}" target="_blank" rel="noopener noreferrer" class="citation-source-link" title="Open source file on external repository">
        <span>View File</span>
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
      </a>
    ` : '';

    card.innerHTML = `
      <div class="citation-header">
        <div class="citation-file-badge" title="${escapeHtml(locator)}">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#a855f7" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          <span class="citation-filename">${escapeHtml(fileDisplay)}</span>
          ${lineRange ? `<span class="citation-locator-tag">${escapeHtml(lineRange)}</span>` : ''}
        </div>
        <div class="citation-meta-group">
          <span class="citation-id-tag" title="FalkorDB Evidence ID: ${escapeHtml(rawId)}">#${escapeHtml(shortId)}</span>
          ${sourceLinkHtml}
        </div>
      </div>
      <div class="citation-excerpt">${escapeHtml(excerptText)}</div>
    `;

    citationsContainer.appendChild(card);
  });
}

function renderDeliverable(deliv) {
  deliverableCard.style.display = 'block';
  const badgeEl = document.getElementById('deliverableBadge');
  const verdict = deliv.readiness_verdict || 'COMPLETED';
  const isBlocked = verdict.toUpperCase().includes('BLOCK');
  const badgeStatus = deliv.badge_status || (isBlocked ? 'Completed with conditions' : 'Completed');

  if (badgeEl) {
    badgeEl.textContent = badgeStatus;
    badgeEl.className = `badge ${isBlocked ? 'badge-warning' : 'badge-success'}`;
  }

  deliverableContent.innerHTML = `
    <div class="deliverable-title">${deliv.title}</div>
    <div class="deliverable-meta">Author: ${deliv.author_name} (${deliv.author_id}) &bull; Status: ${deliv.status}</div>
    <div class="verdict-box ${isBlocked ? 'verdict-blocked' : 'verdict-approved'}">
      VERDICT: ${verdict} ${isBlocked ? '— (Release blocked pending remediation)' : '— (Approved for release)'}
    </div>
    
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
    if (brain3D) {
      brain3D.setData(graphData);
    }
    if (fullBrain3D) {
      fullBrain3D.setData(graphData);
    }
    const nodePill = document.getElementById('topoNodeCountPill');
    const edgePill = document.getElementById('topoEdgeCountPill');
    if (nodePill && graphData.nodes) nodePill.textContent = `${graphData.nodes.length} Nodes`;
    if (edgePill && graphData.edges) edgePill.textContent = `${graphData.edges.length} Edges`;
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
  if (btnSpinner) btnSpinner.style.display = isLoading ? 'inline-block' : 'none';
  if (btnText) btnText.textContent = isLoading ? 'Swarm Executing...' : 'Coordinate Employees';
  if (submitGoalBtn) submitGoalBtn.disabled = isLoading;
  if (runStarterGoalBtn) runStarterGoalBtn.disabled = isLoading;

  if (isLoading) {
    const chiefState = document.getElementById('state-chief');
    const chiefCard = document.getElementById('agentCard-chief');
    if (chiefState) {
      chiefState.textContent = 'RUNNING';
      chiefState.className = 'agent-state-pill state-running';
    }
    if (chiefCard) chiefCard.classList.add('agent-active');
  }
}

function openModal(title, htmlContent) {
  modalTitle.innerHTML = title;
  modalBody.innerHTML = htmlContent;
  modalBackdrop.classList.add('open');
}

function closeModal() {
  modalBackdrop.classList.remove('open');
  const modalWindow = document.querySelector('.modal-window');
  if (modalWindow) modalWindow.classList.remove('modal-lg');
}

// Dedicated 3D Knowledge Topology Studio
let fullBrain3D = null;
let fullTopologyInitialized = false;

window.openTopologyModal = function() {
  const backdrop = document.getElementById('topologyModalBackdrop');
  if (!backdrop) return;
  backdrop.classList.add('open');

  const nodeCount = graphData.nodes ? graphData.nodes.length : 0;
  const edgeCount = graphData.edges ? graphData.edges.length : 0;
  const nodePill = document.getElementById('topoNodeCountPill');
  const edgePill = document.getElementById('topoEdgeCountPill');
  if (nodePill) nodePill.textContent = `${nodeCount} Nodes`;
  if (edgePill) edgePill.textContent = `${edgeCount} Edges`;

  setTimeout(() => {
    if (!fullBrain3D && typeof CompanyBrain3D !== 'undefined') {
      fullBrain3D = new CompanyBrain3D('fullBrain3dContainer');
      setupFullTopologyListeners();
      fullTopologyInitialized = true;
    }
    if (fullBrain3D) {
      fullBrain3D.setData(graphData);
      fullBrain3D.handleResize();
      fullBrain3D.fitToBounds();
    }
  }, 50);
};

window.closeTopologyModal = function() {
  const backdrop = document.getElementById('topologyModalBackdrop');
  if (backdrop) backdrop.classList.remove('open');
  const panel = document.getElementById('topologyNodeDetailPanel');
  if (panel) panel.style.display = 'none';
};

function setupFullTopologyListeners() {
  const closeBtn = document.getElementById('topologyModalCloseBtn');
  const closeFooterBtn = document.getElementById('topoCloseFooterBtn');
  const launchSwarmBtn = document.getElementById('topoLaunchSwarmBtn');
  const panelCloseBtn = document.getElementById('panelCloseBtn');

  if (closeBtn) closeBtn.onclick = closeTopologyModal;
  if (closeFooterBtn) closeFooterBtn.onclick = closeTopologyModal;
  if (launchSwarmBtn) launchSwarmBtn.onclick = () => {
    closeTopologyModal();
    openFalkorDrawer();
  };

  if (panelCloseBtn) {
    panelCloseBtn.onclick = () => {
      const panel = document.getElementById('topologyNodeDetailPanel');
      if (panel) panel.style.display = 'none';
    };
  }

  // Node Inspector click in 3D
  window.onNode3DClick = function(node) {
    showNodeDetailInTopologyModal(node);
  };

  // Filter Buttons
  document.querySelectorAll('.topo-filter-btn').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.topo-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;
      if (fullBrain3D) {
        fullBrain3D.filterByType(filter);
      }
    };
  });

  // Tools
  const zIn = document.getElementById('topoZoomInBtn');
  const zOut = document.getElementById('topoZoomOutBtn');
  const fitBtn = document.getElementById('topoFitBtn');
  const rotBtn = document.getElementById('topoRotateBtn');
  const rstBtn = document.getElementById('topoResetBtn');

  if (zIn) zIn.onclick = () => { if (fullBrain3D) fullBrain3D.zoomIn(); };
  if (zOut) zOut.onclick = () => { if (fullBrain3D) fullBrain3D.zoomOut(); };
  if (fitBtn) fitBtn.onclick = () => { if (fullBrain3D) fullBrain3D.fitToBounds(); };
  if (rotBtn) rotBtn.onclick = () => {
    if (fullBrain3D) {
      const active = fullBrain3D.toggleAutoRotate();
      rotBtn.style.color = active ? 'var(--accent-primary)' : 'var(--text-muted)';
    }
  };
  if (rstBtn) rstBtn.onclick = () => { if (fullBrain3D) fullBrain3D.resetCamera(); };
}

function showNodeDetailInTopologyModal(node) {
  const panel = document.getElementById('topologyNodeDetailPanel');
  if (!panel || !node) return;

  const badge = document.getElementById('panelNodeBadge');
  const title = document.getElementById('panelNodeTitle');
  const idEl = document.getElementById('panelNodeId');
  const desc = document.getElementById('panelNodeDesc');
  const propsEl = document.getElementById('panelNodeProps');
  const focusBtn = document.getElementById('panelFocusBtn');
  const inspectBtn = document.getElementById('panelInspectFalkorBtn');

  if (badge) badge.textContent = node.type || 'Entity';
  if (title) title.textContent = node.label || node.id;
  if (idEl) idEl.textContent = `ID: ${node.id}`;

  const props = node.properties || {};
  const descriptionText = props.description || props.summary || props.text || props.content || props.purpose || '';
  if (desc) {
    desc.textContent = descriptionText ? (descriptionText.length > 200 ? descriptionText.slice(0, 200) + '...' : descriptionText) : 'FalkorDB persistent company entity';
  }

  if (propsEl) {
    const keys = Object.keys(props).filter(k => !['description', 'summary', 'text', 'content', 'label'].includes(k));
    if (keys.length > 0) {
      propsEl.innerHTML = keys.slice(0, 6).map(k => `
        <div class="panel-prop-row">
          <span class="panel-prop-k">${k}:</span>
          <span class="panel-prop-v">${String(props[k]).slice(0, 36)}</span>
        </div>
      `).join('');
      propsEl.style.display = 'flex';
    } else {
      propsEl.style.display = 'none';
    }
  }

  if (focusBtn) {
    focusBtn.onclick = () => {
      const mesh = fullBrain3D && fullBrain3D.nodeMap ? fullBrain3D.nodeMap.get(node.id) : null;
      if (mesh && fullBrain3D) fullBrain3D.focusNode(mesh);
    };
  }

  if (inspectBtn) {
    inspectBtn.onclick = () => {
      closeTopologyModal();
      openFalkorDrawer();
      if (node.id) handleInspectNode(node.id);
    };
  }

  panel.style.display = 'block';
}

window.showEvidence = function(eid) {
  openModal(`Evidence: #${eid}`, `
    <p>Loading evidence details for <strong>#${eid}</strong>...</p>
  `);
};

// =========================================================================
// 3D WOVEN PARTICLE VORTEX ENGINE FOR QRONOS HERO FRAME
// =========================================================================
function initParticleVortex() {
  const canvas = document.getElementById('particleCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const STRAND_COUNT = 48;
  const PARTICLES_PER_STRAND = 28;
  const strands = [];

  for (let s = 0; s < STRAND_COUNT; s++) {
    const baseTheta = (s / STRAND_COUNT) * Math.PI * 2;
    const strandParticles = [];
    for (let p = 0; p < PARTICLES_PER_STRAND; p++) {
      const t = (p / (PARTICLES_PER_STRAND - 1)) * 2 - 1; // -1 (top) to +1 (bottom)
      strandParticles.push({
        normY: t,
        thetaOffset: t * 1.8, // twist
        size: Math.random() * 1.2 + 0.6,
        isViolet: (s % 4 === 0) || Math.random() > 0.8
      });
    }
    strands.push({
      baseTheta,
      speed: 0.0035,
      particles: strandParticles
    });
  }

  // Floating ambient field
  const AMBIENT_COUNT = 300;
  const ambient = [];
  for (let i = 0; i < AMBIENT_COUNT; i++) {
    ambient.push({
      x: (Math.random() - 0.5) * width * 1.4,
      y: (Math.random() - 0.5) * height * 1.2,
      z: Math.random() * 600 - 300,
      size: Math.random() * 1.2 + 0.4,
      alpha: Math.random() * 0.5 + 0.1,
      speedY: (Math.random() - 0.5) * 0.3
    });
  }

  const focalLength = 380;
  let globalAngle = 0;

  function renderVortex() {
    ctx.clearRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height * 0.42;
    globalAngle += 0.004;

    // Render woven strands
    for (let s = 0; s < STRAND_COUNT; s++) {
      const strand = strands[s];
      const theta = strand.baseTheta + globalAngle;

      let prevPoint = null;

      for (let p = 0; p < strand.particles.length; p++) {
        const pt = strand.particles[p];
        const y = pt.normY * (height * 0.52);

        // Hyperbolic hourglass formula: narrow waist at center
        const neck = 55;
        const flare = Math.pow(Math.abs(pt.normY), 2.2) * (width * 0.45);
        const radius = neck + flare;

        const particleTheta = theta + pt.thetaOffset;
        const x = radius * Math.cos(particleTheta);
        const z = radius * Math.sin(particleTheta);

        const zDist = focalLength + z + 180;
        if (zDist > 0) {
          const scale = focalLength / zDist;
          const projX = centerX + x * scale;
          const projY = centerY + y * scale;

          const depthAlpha = Math.min(Math.max((z + 280) / 560, 0.08), 0.9);

          // Draw strand curve connection
          if (prevPoint && Math.abs(projX - prevPoint.x) < 180) {
            ctx.beginPath();
            ctx.moveTo(prevPoint.x, prevPoint.y);
            ctx.lineTo(projX, projY);
            ctx.strokeStyle = pt.isViolet ? `rgba(192, 132, 252, ${depthAlpha * 0.35})` : `rgba(255, 255, 255, ${depthAlpha * 0.22})`;
            ctx.lineWidth = Math.max(0.6 * scale, 0.4);
            ctx.stroke();
          }

          // Draw point node
          ctx.beginPath();
          ctx.arc(projX, projY, Math.max(pt.size * scale, 0.6), 0, Math.PI * 2);
          if (pt.isViolet) {
            ctx.fillStyle = `rgba(216, 180, 254, ${depthAlpha * 0.95})`;
          } else {
            ctx.fillStyle = `rgba(255, 255, 255, ${depthAlpha * 0.75})`;
          }
          ctx.fill();

          prevPoint = { x: projX, y: projY };
        } else {
          prevPoint = null;
        }
      }
    }

    // Render ambient field
    for (let i = 0; i < AMBIENT_COUNT; i++) {
      const a = ambient[i];
      a.y += a.speedY;
      if (a.y > height * 0.6) a.y = -height * 0.6;
      if (a.y < -height * 0.6) a.y = height * 0.6;

      const zDist = focalLength + a.z + 180;
      if (zDist > 0) {
        const scale = focalLength / zDist;
        const projX = centerX + a.x * scale;
        const projY = centerY + a.y * scale;

        ctx.beginPath();
        ctx.arc(projX, projY, a.size * scale, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${a.alpha * 0.4})`;
        ctx.fill();
      }
    }

    requestAnimationFrame(renderVortex);
  }

  requestAnimationFrame(renderVortex);
}

