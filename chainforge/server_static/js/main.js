async function refresh() {
  try {
    const h=await fetch('/api/v1/health').then(r=>r.json());
    document.getElementById('agent-count').textContent=h.agents||0;
    document.getElementById('status').textContent=h.status==='ok'?'Online':'Offline';
    const agents=await fetch('/api/v1/agents').then(r=>r.json());
    const sec=document.getElementById('agents-section');
    if(agents.length===0){sec.innerHTML='<div class="empty-state"><h3>No agents registered</h3><p>Register via CLI or API.</p></div>';return;}
    let html='<table><thead><tr><th>ID</th><th>Type</th><th>Tools</th><th>Status</th></tr></thead><tbody>';
    for(const a of agents)html+='<tr><td>'+a.id+'</td><td>'+(a.agent_type||'-')+'</td><td>'+(a.tools?a.tools.length:0)+'</td><td><span class="status-dot online"></span>ready</td></tr>';
    html+='</tbody></table>';sec.innerHTML=html;
    document.getElementById('server-info').innerHTML='Version: '+(h.version||'-')+'<br>Agents: '+(h.agents||0);
    const ve=document.getElementById('version');if(ve)ve.textContent='v'+(h.version||'');
  }catch(e){document.getElementById('agent-count').textContent='!';document.getElementById('status').textContent='Offline';}
}
let sseClient=null,eventCount=0;
async function loadAgents(){
  try{const agents=await fetch('/api/v1/agents').then(r=>r.json());const sel=document.getElementById('agent-select');sel.innerHTML='<option value="">-- Select Agent --</option>';for(const a of agents){const o=document.createElement('option');o.value=a.id;o.textContent=a.id+' ('+(a.agent_type||'Agent')+')';sel.appendChild(o);}}catch(e){}
}
function updateStateMachine(s){
  document.querySelectorAll('.state-node').forEach(el=>{el.classList.remove('active','completed','error');const st=el.dataset.state;if(st===s)el.classList.add('active');else if(['initializing','thinking','executing_tool','observing','responding','done'].indexOf(st)>=0)el.classList.add('completed');});
  document.getElementById('m-state').textContent=s;
}
function runAgent(){
  const aid=document.getElementById('agent-select').value,pr=document.getElementById('prompt-input').value;
  if(!aid){alert('Select an agent');return;}
  document.getElementById('run-metrics').style.display='grid';document.getElementById('m-duration').textContent='0s';
  document.getElementById('m-tool-calls').textContent='0';document.getElementById('m-iterations').textContent='0';
  updateStateMachine('initializing');clearEvents();
  document.getElementById('event-log').innerHTML='<div class="log">Connecting...</div>';
  document.getElementById('run-btn').disabled=true;document.getElementById('stop-btn').disabled=false;eventCount=0;
  const st=Date.now();
  sseClient=new SSEClient('/api/v1/agents/'+encodeURIComponent(aid)+'/run/stream?prompt='+encodeURIComponent(pr));
  sseClient.onEvent=(type,data)=>{
    const log=document.getElementById('event-log');eventCount++;document.getElementById('event-count').textContent=eventCount+' events';
    const el=((Date.now()-st)/1000).toFixed(1);
    const entry=document.createElement('div');entry.className='event-entry '+type;
    entry.innerHTML='<span class="type">'+type+'</span><span class="time">+'+el+'s</span><br>'+(data.content||JSON.stringify(data.data||''));
    log.appendChild(entry);log.scrollTop=log.scrollHeight;
    if(type==='tool_call'){document.getElementById('m-tool-calls').textContent=parseInt(document.getElementById('m-tool-calls').textContent)+1;}
    if(type==='state'){const st=data.data?data.data.state:data.content;updateStateMachine(st);if(data.data&&data.data.iteration!==undefined)document.getElementById('m-iterations').textContent=data.data.iteration+1;}
    document.getElementById('m-duration').textContent=el+'s';
  };
  sseClient.onDone=()=>{document.getElementById('event-log').innerHTML+='<div class="info">--- Complete ---</div>';document.getElementById('run-btn').disabled=false;document.getElementById('stop-btn').disabled=true;updateStateMachine('done');};
  sseClient.onError=()=>{document.getElementById('run-btn').disabled=false;document.getElementById('stop-btn').disabled=true;};
  sseClient.connect();
}
function stopRun(){if(sseClient)sseClient.disconnect();document.getElementById('run-btn').disabled=false;document.getElementById('stop-btn').disabled=true;document.getElementById('event-log').innerHTML+='<div class="warn">--- Stopped ---</div>';}
function clearEvents(){const l=document.getElementById('event-log');if(l)l.innerHTML='';eventCount=0;document.getElementById('event-count').textContent='0 events';document.getElementById('m-tool-calls').textContent='0';document.getElementById('m-iterations').textContent='0';document.getElementById('m-duration').textContent='0s';}
document.addEventListener('DOMContentLoaded',()=>{if(document.getElementById('agent-count'))refresh();if(document.getElementById('agent-select'))loadAgents();});