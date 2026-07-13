class SSEClient {
  constructor(url) { this.url = url; this.eventSource = null; this.onEvent = null; this.onDone = null; this.onError = null; this._running = false; }
  connect() {
    if (this._running) this.disconnect();
    this._running = true;
    this.eventSource = new EventSource(this.url);
    const handlers = {
      text: (d) => { if (this.onEvent) this.onEvent('text', d); },
      tool_call: (d) => { if (this.onEvent) this.onEvent('tool_call', d); },
      tool_result: (d) => { if (this.onEvent) this.onEvent('tool_result', d); },
      status: (d) => { if (this.onEvent) this.onEvent('status', d); },
      state: (d) => { if (this.onEvent) this.onEvent('state', d); },
      error: (d) => { if (this.onEvent) this.onEvent('error', d); if (this.onError) this.onError(d); },
      done: (d) => { if (this.onEvent) this.onEvent('done', d); if (this.onDone) this.onDone(d); this.disconnect(); },
    };
    for (const [et, h] of Object.entries(handlers)) {
      this.eventSource.addEventListener(et, (e) => { try { h(JSON.parse(e.data)); } catch (err) {} });
    }
    this.eventSource.onerror = (err) => { if (this.onError) this.onError(err); this.disconnect(); };
  }
  disconnect() { if (this.eventSource) { this.eventSource.close(); this.eventSource = null; } this._running = false; }
  get running() { return this._running; }
}