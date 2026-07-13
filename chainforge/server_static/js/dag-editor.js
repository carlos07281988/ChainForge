class DagEditor {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId); this.ctx = this.canvas.getContext('2d');
    this.nodes = []; this.edges = []; this.selectedNode = null; this.draggingNode = null;
    this.dragOffset = { x: 0, y: 0 }; this.connectingFrom = null;
    this.mousePos = { x: 0, y: 0 }; this.nodeCounter = 0;
    this.setupCanvas(); this.setupEvents(); this.render();
  }
  setupCanvas() {
    const resize = () => { const rect = this.canvas.parentElement.getBoundingClientRect(); this.canvas.width = rect.width; this.canvas.height = this.canvas.clientHeight || 500; this.render(); };
    window.addEventListener('resize', resize); setTimeout(resize, 50);
  }
  setupEvents() {
    ['mousedown','mousemove','mouseup','dblclick'].forEach(evt => this.canvas.addEventListener(evt, (e) => this['on'+evt.charAt(0).toUpperCase()+evt.slice(1)](e)));
    document.addEventListener('keydown', (e) => { if (e.key === 'Delete' || e.key === 'Backspace') this.deleteSelected(); });
  }
  getPos(e) { const r = this.canvas.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; }
  addNode(type, x, y) {
    if (!x||!y) { x=100+Math.random()*(this.canvas.width-200); y=100+Math.random()*(this.canvas.height-200); }
    this.nodeCounter++; const colors={step:'#6366f1',input:'#22c55e',output:'#ef4444',router:'#eab308',merge:'#06b6d4'};
    const n={id:'n'+this.nodeCounter,type:type,label:type.charAt(0).toUpperCase()+type.slice(1)+' '+this.nodeCounter,x:x,y:y,width:120,height:48,color:colors[type]||'#6366f1',description:''};
    this.nodes.push(n); this.render(); this.updateJSON(); return n;
  }
  findNodeAt(x,y) { for(let i=this.nodes.length-1;i>=0;i--){const n=this.nodes[i];if(x>=n.x&&x<=n.x+n.width&&y>=n.y&&y<=n.y+n.height)return n;}return null;}
  findPortAt(x,y) {
    for(const n of this.nodes){
      const ip={x:n.x,y:n.y+n.height/2,r:6,node:n,type:'input'};if(Math.hypot(x-ip.x,y-ip.y)<ip.r+4)return ip;
      const op={x:n.x+n.width,y:n.y+n.height/2,r:6,node:n,type:'output'};if(Math.hypot(x-op.x,y-op.y)<op.r+4)return op;
    }return null;
  }
  onMouseDown(e) {
    const p=this.getPos(e); const port=this.findPortAt(p.x,p.y);
    if(port&&port.type==='output'){this.connectingFrom=port;return;}
    const n=this.findNodeAt(p.x,p.y);
    if(n){this.selectedNode=n;this.draggingNode=n;this.dragOffset={x:p.x-n.x,y:p.y-n.y};this.updateProperties();}
    else{this.selectedNode=null;this.updateProperties();}
    this.render();
  }
  onMouseMove(e) {
    this.mousePos=this.getPos(e);
    if(this.connectingFrom){this.render();return;}
    if(this.draggingNode){this.draggingNode.x=this.mousePos.x-this.dragOffset.x;this.draggingNode.y=this.mousePos.y-this.dragOffset.y;this.render();this.updateJSON();}
  }
  onMouseUp(e) {
    if(this.connectingFrom){const p=this.getPos(e);const port=this.findPortAt(p.x,p.y);if(port&&port.type==='input'&&port.node!==this.connectingFrom.node){this.edges.push({source:this.connectingFrom.node.id,target:port.node.id});this.updateJSON();}this.connectingFrom=null;this.render();}
    this.draggingNode=null;
  }
  onDoubleClick(e) {
    const p=this.getPos(e);const n=this.findNodeAt(p.x,p.y);
    if(n){const l=prompt('Node label:',n.label);if(l){n.label=l;this.updateJSON();this.render();}}
    else{const t=prompt('Node type (step/input/output/router/merge):','step');if(t)this.addNode(t,p.x-60,p.y-24);}
  }
  deleteSelected(){
    if(!this.selectedNode)return;
    this.nodes=this.nodes.filter(n=>n.id!==this.selectedNode.id);
    this.edges=this.edges.filter(e=>e.source!==this.selectedNode.id&&e.target!==this.selectedNode.id);
    this.selectedNode=null;this.updateJSON();this.render();
  }
  render() {
    const ctx=this.ctx,w=this.canvas.width,h=this.canvas.height;
    ctx.clearRect(0,0,w,h);
    for(const e of this.edges){
      const src=this.nodes.find(n=>n.id===e.source),tgt=this.nodes.find(n=>n.id===e.target);
      if(!src||!tgt)continue;
      const x1=src.x+src.width,y1=src.y+src.height/2,x2=tgt.x,y2=tgt.y+tgt.height/2;
      ctx.beginPath();ctx.moveTo(x1,y1);ctx.bezierCurveTo(x1+Math.abs(x2-x1)*0.4,y1,x2-Math.abs(x2-x1)*0.4,y2,x2,y2);
      ctx.strokeStyle='#4a4d6a';ctx.lineWidth=2;ctx.stroke();
    }
    if(this.connectingFrom){
      ctx.beginPath();ctx.moveTo(this.connectingFrom.x,this.connectingFrom.y);ctx.lineTo(this.mousePos.x,this.mousePos.y);
      ctx.strokeStyle='#6366f1';ctx.lineWidth=2;ctx.setLineDash([4,4]);ctx.stroke();ctx.setLineDash([]);
    }
    for(const n of this.nodes){
      const sel=this.selectedNode&&this.selectedNode.id===n.id;
      ctx.shadowColor='rgba(0,0,0,0.3)';ctx.shadowBlur=8;ctx.shadowOffsetY=2;
      ctx.fillStyle='#1a1d27';ctx.beginPath();ctx.roundRect?ctx.roundRect(n.x,n.y,n.width,n.height,6):ctx.rect(n.x,n.y,n.width,n.height);ctx.fill();
      ctx.shadowColor='transparent';ctx.strokeStyle=sel?n.color:'#2a2d3e';ctx.lineWidth=sel?2:1;
      ctx.beginPath();ctx.roundRect?ctx.roundRect(n.x,n.y,n.width,n.height,6):ctx.rect(n.x,n.y,n.width,n.height);ctx.stroke();
      ctx.fillStyle=n.color;ctx.beginPath();ctx.roundRect?ctx.roundRect(n.x+2,n.y+2,n.width-4,4,2):ctx.rect(n.x+2,n.y+2,n.width-4,4);ctx.fill();
      ctx.fillStyle='#e1e4ed';ctx.font='12px -apple-system, system-ui, sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(n.label,n.x+n.width/2,n.y+n.height/2);
      ctx.fillStyle='rgba(255,255,255,0.1)';ctx.font='9px monospace';ctx.fillText(n.type,n.x+n.width-4,n.y+10);
      ctx.fillStyle='#2a2d3e';ctx.beginPath();ctx.arc(n.x,n.y+n.height/2,4,0,Math.PI*2);ctx.fill();
      ctx.fillStyle=sel?n.color:'#4a4d6a';ctx.beginPath();ctx.arc(n.x,n.y+n.height/2,3,0,Math.PI*2);ctx.fill();
      ctx.fillStyle='#2a2d3e';ctx.beginPath();ctx.arc(n.x+n.width,n.y+n.height/2,4,0,Math.PI*2);ctx.fill();
      ctx.fillStyle=sel?n.color:'#4a4d6a';ctx.beginPath();ctx.arc(n.x+n.width,n.y+n.height/2,3,0,Math.PI*2);ctx.fill();
    }
    ctx.shadowColor='transparent';
  }
  clear(){this.nodes=[];this.edges=[];this.selectedNode=null;this.nodeCounter=0;this.updateJSON();this.render();}
  exportJSON(){
    const data={name:'custom_dag',nodes:this.nodes.map(n=>({id:n.id,type:n.type,label:n.label})),edges:this.edges};
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download='dag.json';a.click();URL.revokeObjectURL(url);
  }
  updateJSON(){
    const data={name:'custom_dag',nodes:this.nodes.map(n=>({id:n.id,type:n.type,label:n.label})),edges:this.edges};
    const el=document.getElementById('dag-json');if(el)el.value=JSON.stringify(data,null,2);
  }
  updateProperties(){
    const el=document.getElementById('node-props');if(!el)return;
    if(!this.selectedNode){el.innerHTML='<div class="empty-state" style="padding:1rem"><p>Select a node to edit.</p></div>';return;}
    const n=this.selectedNode;
    el.innerHTML='<label>Label</label><input type="text" value="'+n.label+'" onchange="dagEditor.selectedNode.label=this.value;dagEditor.render();dagEditor.updateJSON();" style="margin-bottom:0.5rem">'
      +'<label>Type</label><select onchange="dagEditor.selectedNode.type=this.value;dagEditor.render();dagEditor.updateJSON();" style="margin-bottom:0.5rem">'
      +['step','input','output','router','merge'].map(t=>'<option value="'+t+'"'+(t===n.type?'selected':'')+'>'+t+'</option>').join('')+'</select>'
      +'<div style="margin-top:0.75rem"><button class="btn btn-sm" onclick="dagEditor.deleteSelected()" style="color:var(--red)">Delete Node</button></div>';
  }
  async runDAG(){
    const el=document.getElementById('dag-output');if(!el)return;
    el.innerHTML='<div class="log">Executing DAG...</div>';
    const data={name:'custom_dag',nodes:this.nodes.map(n=>({id:n.id,type:n.type,label:n.label,description:n.description||''})),edges:this.edges};
    try{
      const resp=await fetch('/api/v1/dag/stream?dag='+encodeURIComponent(JSON.stringify(data)));
      if(!resp.ok)throw new Error('Server error: '+resp.status);
      const reader=resp.body.getReader(),decoder=new TextDecoder();let buffer='';
      while(true){const{done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const lines=buffer.split('\n');buffer=lines.pop()||'';for(const l of lines){if(l.startsWith('data: ')){try{const ev=JSON.parse(l.slice(6));el.innerHTML+='<div class="'+(ev.type==='error'?'error':'log')+'">'+ev.content+'</div>';el.scrollTop=el.scrollHeight;}catch(e){}}}}
    }catch(err){el.innerHTML+='<div class="error">Error: '+err.message+'</div>';}
  }
}
document.addEventListener('DOMContentLoaded',()=>{if(document.getElementById('dag-canvas'))window.dagEditor=new DagEditor('dag-canvas');});