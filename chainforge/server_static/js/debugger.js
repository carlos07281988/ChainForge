/**
 * ChainForge Agent Visual Debugger - Frontend Logic
 *
 * Connects to the Debugger API via REST + WebSocket.
 * Provides real-time timeline, state inspection, and execution control.
 */

class DebuggerUI {
  constructor() {
    this.apiBase = '/api/v1/debug';
    this.currentSessionId = null;
    this.ws = null;
    this.events = [];
    this.sessions = [];
    this.selectedEventIndex = -1;
    this.breakpoints = [];

    // DOM refs
    this.elements = {
      sessionList: document.getElementById('session-list'),
      timeline: document.getElementById('timeline'),
      inspectorBody: document.getElementById('inspector-body'),
      controlRun: document.getElementById('control-run'),
      controlPause: document.getElementById('control-pause'),
      controlResume: document.getElementById('control-resume'),
      controlStep: document.getElementById('control-step'),
      promptInput: document.getElementById('prompt-input'),
      breakpointBar: document.getElementById('breakpoint-bar'),
      statusIndicator: document.getElementById('status-indicator'),
      emptyState: document.getElementById('empty-state'),
    };

    this._bindEvents();
    this._loadSessions();
  }

  // ── API calls ─────────────────────────────────────────

  async _fetch(path, options = {}) {
    const resp = await fetch(`${this.apiBase}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
  }

  async _loadSessions() {
    try {
      const data = await this._fetch('/sessions');
      this.sessions = data.sessions || [];
      this._renderSessionList();
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  }

  async _createSession(name, agentId, prompt, breakpoints) {
    const data = await this._fetch('/sessions', {
      method: 'POST',
      body: JSON.stringify({ name, agent_id: agentId, prompt, breakpoints }),
    });
    this.sessions.unshift(data);
    this._renderSessionList();
    this._selectSession(data.id);
    return data;
  }

  async _runSession() {
    if (!this.currentSessionId) return;
    await this._fetch(`/sessions/${this.currentSessionId}/run`, { method: 'POST' });
  }

  async _pauseSession() {
    if (!this.currentSessionId) return;
    await this._fetch(`/sessions/${this.currentSessionId}/pause`, { method: 'POST' });
  }

  async _resumeSession() {
    if (!this.currentSessionId) return;
    await this._fetch(`/sessions/${this.currentSessionId}/resume`, { method: 'POST' });
  }

  async _stepSession() {
    if (!this.currentSessionId) return;
    await this._fetch(`/sessions/${this.currentSessionId}/step`, { method: 'POST' });
  }

  async _loadEvents() {
    if (!this.currentSessionId) return;
    try {
      const data = await this._fetch(`/sessions/${this.currentSessionId}/events?limit=500`);
      this.events = data.events || [];
      this._renderTimeline();
      this.updateStatusBar();
    } catch (e) {
      console.error('Failed to load events:', e);
    }
  }

  async _loadCheckpoints() {
    if (!this.currentSessionId) return;
    try {
      const data = await this._fetch(`/sessions/${this.currentSessionId}/checkpoints`);
      return data.checkpoints || [];
    } catch (e) {
      return [];
    }
  }

  async _loadCheckpointState(checkpointId) {
    if (!this.currentSessionId) return null;
    try {
      return await this._fetch(`/sessions/${this.currentSessionId}/checkpoints/${checkpointId}`);
    } catch (e) {
      return null;
    }
  }

  // ── WebSocket ─────────────────────────────────────────

  _connectWebSocket() {
    if (this.ws) {
      this.ws.close();
    }
    if (!this.currentSessionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${this.apiBase}/sessions/${this.currentSessionId}/ws`;

    this.ws = new WebSocket(wsUrl);
    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this._handleWsMessage(msg);
      } catch (e) {
        console.error('WS message error:', e);
      }
    };
    this.ws.onclose = () => {
      // Reconnect after delay
      setTimeout(() => this._connectWebSocket(), 3000);
    };
    this.ws.onerror = () => {
      this.ws.close();
    };
  }

  _handleWsMessage(msg) {
    if (msg.type === 'connected') {
      console.log('WS connected:', msg.session_id);
      return;
    }
    if (msg.type === 'done') {
      this.updateStatusBar();
      return;
    }
    if (msg.type === 'paused' || msg.type === 'resumed' || msg.type === 'stepping') {
      this.updateStatusBar();
      return;
    }

    // Regular event
    if (msg.type) {
      this.events.push(msg);
      this._appendEventToTimeline(msg);
      this.updateStatusBar();
    }
  }

  // ── UI Rendering ───────────────────────────────────────

  _renderSessionList() {
    const el = this.elements.sessionList;
    el.innerHTML = '';
    for (const session of this.sessions) {
      const card = document.createElement('div');
      card.className = `session-card${session.id === this.currentSessionId ? ' active' : ''}`;
      card.innerHTML = `
        <div class="name">${this._escapeHtml(session.name)}</div>
        <div class="meta">
          <span class="status-badge ${session.status}">${session.status}</span>
          ${session.event_count || 0} events · ${session.checkpoint_count || 0} ckps
        </div>
      `;
      card.onclick = () => this._selectSession(session.id);
      el.appendChild(card);
    }
  }

  _renderTimeline() {
    const el = this.elements.timeline;
    el.innerHTML = '';
    if (this.events.length === 0) {
      el.appendChild(this.elements.emptyState.cloneNode(true));
      return;
    }
    for (let i = 0; i < this.events.length; i++) {
      const eventEl = this._createEventElement(this.events[i], i);
      el.appendChild(eventEl);
    }
    el.scrollTop = el.scrollHeight;
  }

  _appendEventToTimeline(event) {
    const el = this.elements.timeline;
    // Remove empty state if present
    const empty = el.querySelector('.timeline-empty');
    if (empty) empty.remove();

    const index = this.events.length - 1;
    const eventEl = this._createEventElement(event, index);
    el.appendChild(eventEl);
    el.scrollTop = el.scrollHeight;
  }

  _createEventElement(event, index) {
    const div = document.createElement('div');
    div.className = `event-item ${event.type || 'status'}${index === this.selectedEventIndex ? ' selected' : ''}`;
    div.dataset.index = index;

    const iconMap = {
      tool_call: '🔧',
      tool_result: '✅',
      text: '💬',
      state: '⚡',
      error: '❌',
      status: 'ℹ️',
    };

    const titleMap = {
      tool_call: `Tool: ${event.data?.name || 'unknown'}`,
      tool_result: `Result: ${event.data?.name || 'tool'}`,
      text: 'LLM Response',
      state: `State: ${event.data?.state || event.content || ''}`,
      error: `Error: ${event.content || ''}`,
      status: event.content || 'Status',
    };

    const previewMap = {
      tool_call: `args: ${JSON.stringify(event.data?.args || {}).slice(0, 80)}`,
      tool_result: `result: ${(event.data?.content || '').slice(0, 80)}`,
      text: (event.content || '').slice(0, 100),
      state: event.content || event.data?.state || '',
      error: event.content || '',
      status: '',
    };

    div.innerHTML = `
      <div class="event-icon ${event.type}">${iconMap[event.type] || 'ℹ️'}</div>
      <div class="event-content">
        <div class="event-title">${this._escapeHtml(titleMap[event.type] || event.type)}</div>
        <div class="event-preview">${this._escapeHtml(previewMap[event.type] || '')}</div>
      </div>
      <div class="event-time">${new Date((event.timestamp || 0) * 1000).toLocaleTimeString()}</div>
    `;

    div.onclick = () => this._selectEvent(index);
    return div;
  }

  _renderInspector(event) {
    const el = this.elements.inspectorBody;
    if (!event) {
      el.innerHTML = '<div class="inspector-empty">Select an event to inspect</div>';
      return;
    }

    let html = '';

    // Type badge
    html += `<div class="inspector-section">
      <div class="inspector-section-title">Event Type</div>
      <div><span class="status-badge ${event.type}">${event.type}</span></div>
    </div>`;

    // Content
    if (event.content) {
      html += `<div class="inspector-section">
        <div class="inspector-section-title">Content</div>
        <div class="inspector-text">${this._escapeHtml(event.content)}</div>
      </div>`;
    }

    // Data
    if (event.data && Object.keys(event.data).length > 0) {
      html += `<div class="inspector-section">
        <div class="inspector-section-title">Data</div>
        <div class="inspector-json">${this._escapeHtml(JSON.stringify(event.data, null, 2))}</div>
      </div>`;
    }

    // Full event
    html += `<div class="inspector-section">
      <div class="inspector-section-title">Full Event</div>
      <div class="inspector-json">${this._escapeHtml(JSON.stringify(event, null, 2))}</div>
    </div>`;

    // Checkpoint link (if available)
    if (event.data?.checkpoint_id) {
      html += `<div class="inspector-section">
        <div class="inspector-section-title">Checkpoint</div>
        <div><button class="btn btn-sm" onclick="debuggerUI._viewCheckpoint('${event.data.checkpoint_id}')">
          View Checkpoint State
        </button></div>
      </div>`;
    }

    el.innerHTML = html;
  }

  // ── Session selection ─────────────────────────────────

  async _selectSession(sessionId) {
    this.currentSessionId = sessionId;
    this.events = [];
    this.selectedEventIndex = -1;
    this._renderSessionList();
    this.elements.timeline.innerHTML = '';
    this._renderInspector(null);
    this._connectWebSocket();
    await this._loadEvents();
    this.updateStatusBar();
  }

  _selectEvent(index) {
    this.selectedEventIndex = index;
    const event = this.events[index];
    this._renderInspector(event);

    // Update visual selection
    this.elements.timeline.querySelectorAll('.event-item').forEach((el, i) => {
      el.classList.toggle('selected', i === index);
    });
  }

  async _viewCheckpoint(checkpointId) {
    const data = await this._loadCheckpointState(checkpointId);
    if (data?.state) {
      const el = this.elements.inspectorBody;
      el.innerHTML += `<div class="inspector-section">
        <div class="inspector-section-title">Checkpoint: ${checkpointId}</div>
        <div class="inspector-json">${this._escapeHtml(JSON.stringify(data.state, null, 2))}</div>
      </div>`;
    }
  }

  // ── Actions ───────────────────────────────────────────

  async onRun() {
    const prompt = this.elements.promptInput.value.trim();
    if (!prompt) return;

    // Create session if none selected
    if (!this.currentSessionId) {
      const agentId = document.getElementById('agent-id-input')?.value || 'default';
      await this._createSession('debug-run', agentId, prompt, this.breakpoints);
    }

    await this._runSession();
  }

  async onPause() { await this._pauseSession(); }
  async onResume() { await this._resumeSession(); }
  async onStep() { await this._stepSession(); }

  async onNewSession() {
    const prompt = this.elements.promptInput.value.trim() || 'New debug session';
    const agentId = document.getElementById('agent-id-input')?.value || 'default';
    await this._createSession('debug-session', agentId, prompt, this.breakpoints);
  }

  addBreakpoint(eventType) {
    this.breakpoints.push({ event_type: eventType });
    this._renderBreakpoints();
  }

  removeBreakpoint(index) {
    this.breakpoints.splice(index, 1);
    this._renderBreakpoints();
  }

  _renderBreakpoints() {
    const el = this.elements.breakpointBar;
    if (!el) return;
    let html = '<span style="color:var(--text-muted)">Breakpoints:</span>';
    this.breakpoints.forEach((bp, i) => {
      html += `<span class="breakpoint-chip">
        ${bp.event_type}
        <span class="remove" onclick="debuggerUI.removeBreakpoint(${i})">×</span>
      </span>`;
    });
    html += `<button class="btn btn-sm" onclick="debuggerUI.addBreakpoint('tool_call')">+ Tool</button>
             <button class="btn btn-sm" onclick="debuggerUI.addBreakpoint('error')">+ Error</button>`;
    el.innerHTML = html;
  }

  updateStatusBar() {
    const indicator = this.elements.statusIndicator;
    if (!indicator) return;
    const session = this.sessions.find(s => s.id === this.currentSessionId);
    if (session) {
      indicator.textContent = `${session.status} · ${this.events.length} events`;
      indicator.className = `status-badge ${session.status}`;
    }
  }

  // ── Event binding ─────────────────────────────────────

  _bindEvents() {
    if (this.elements.controlRun) {
      this.elements.controlRun.onclick = () => this.onRun();
    }
    if (this.elements.controlPause) {
      this.elements.controlPause.onclick = () => this.onPause();
    }
    if (this.elements.controlResume) {
      this.elements.controlResume.onclick = () => this.onResume();
    }
    if (this.elements.controlStep) {
      this.elements.controlStep.onclick = () => this.onStep();
    }

    // Enter key to run
    if (this.elements.promptInput) {
      this.elements.promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.onRun();
        }
      });
    }
  }

  // ── Utilities ─────────────────────────────────────────

  _escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}

// ── Initialize ───────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  window.debuggerUI = new DebuggerUI();
});
