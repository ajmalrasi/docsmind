/* Theme-aware SVG diagrams + section metadata, consumed by build.js.
 * SVGs use CSS classes (styled in _site.css) so they adapt to light/dark
 * and the per-section accent colour. No hard-coded colours here. */

/* ---- small helpers ---- */
function box(x, y, w, h, label, sub, cls){
  const r = 12;
  let t = '<rect class="'+(cls||'dg-box')+'" x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="'+r+'"/>';
  const cx = x + w/2;
  if (sub){
    t += '<text class="dg-label" x="'+cx+'" y="'+(y+h/2-2)+'" text-anchor="middle">'+label+'</text>';
    t += '<text class="dg-sub" x="'+cx+'" y="'+(y+h/2+15)+'" text-anchor="middle">'+sub+'</text>';
  } else {
    t += '<text class="dg-label" x="'+cx+'" y="'+(y+h/2+5)+'" text-anchor="middle">'+label+'</text>';
  }
  return t;
}
function arrow(x1, y, x2){ // horizontal →
  return '<line class="dg-line" x1="'+x1+'" y1="'+y+'" x2="'+(x2-7)+'" y2="'+y+'"/>'+
         '<polygon class="dg-arrow" points="'+(x2-7)+','+(y-5)+' '+x2+','+y+' '+(x2-7)+','+(y+5)+'"/>';
}
function arrowV(x, y1, y2){ // vertical ↓ (or ↑ if y2 < y1)
  const s = y2 > y1 ? 1 : -1;
  return '<line class="dg-line" x1="'+x+'" y1="'+y1+'" x2="'+x+'" y2="'+(y2-7*s)+'"/>'+
         '<polygon class="dg-arrow" points="'+(x-5)+','+(y2-7*s)+' '+x+','+y2+' '+(x+5)+','+(y2-7*s)+'"/>';
}
function fig(svg, caption){
  return '<figure class="diagram"><svg viewBox="0 0 720 '+svg.h+'" role="img" aria-label="'+
    caption.replace(/"/g,"'")+'">'+svg.body+'</svg><figcaption>'+caption+'</figcaption></figure>';
}

/* ---- diagrams ---- */
const D = {};

// Ingest pipeline: documents → chunk → embed → normalize → FAISS
D.ingest = (()=>{
  const y=46,h=58; const labels=[
    ["Documents","raw text"],["Chunk","~512 tokens"],["Embed","bge-small"],
    ["Normalize","L2 → len 1"],["FAISS","store vectors"]];
  let b=""; const w=112, step=138, x0=16;
  labels.forEach((l,i)=>{ const x=x0+i*step; b+=box(x,y,w,h,l[0],l[1], i===4?'dg-box dg-hot':'dg-box');
    if(i<labels.length-1) b+=arrow(x+w, y+h/2, x+step); });
  return {h:132, body:b+
    '<text class="dg-sub" x="360" y="20" text-anchor="middle">Index time — done once, ahead of any question</text>'};
})();

// Query pipeline: question → embed → search → top-k → Claude → answer
D.query = (()=>{
  const y=46,h=58; const labels=[
    ["Question","user text"],["Embed","same model"],["Search","FAISS top-k"],
    ["Context","chunks"],["Claude","generate"],["Answer","+ citations"]];
  let b=""; const w=100, step=116, x0=18;
  labels.forEach((l,i)=>{ const x=x0+i*step; b+=box(x,y,w,h,l[0],l[1], i===4?'dg-box dg-hot':'dg-box');
    if(i<labels.length-1) b+=arrow(x+w, y+h/2, x+step); });
  return {h:132, body:b+
    '<text class="dg-sub" x="360" y="20" text-anchor="middle">Query time — runs live for every question</text>'};
})();

// Cosine similarity: two unit vectors and the angle between them
D.cosine = (()=>{
  const cx=360, cy=150, R=110;
  const a1=-18*Math.PI/180, a2=-70*Math.PI/180;
  const x1=cx+R*Math.cos(a1), y1=cy+R*Math.sin(a1);
  const x2=cx+R*Math.cos(a2), y2=cy+R*Math.sin(a2);
  let b='';
  b+='<line class="dg-line" x1="'+cx+'" y1="'+cy+'" x2="'+cx+150+'" y2="'+cy+'"/>';
  b+='<line class="dg-line" x1="'+cx+'" y1="'+cy+'" x2="'+cx+'" y2="'+(cy-150)+'"/>';
  b+='<line class="dg-arrow" x1="'+cx+'" y1="'+cy+'" x2="'+x1+'" y2="'+y1+'" stroke-width="3"/>';
  b+='<line class="dg-arrow" x1="'+cx+'" y1="'+cy+'" x2="'+x2+'" y2="'+y2+'" stroke-width="3"/>';
  b+='<circle class="dg-hot" cx="'+x1+'" cy="'+y1+'" r="5"/>';
  b+='<circle class="dg-hot" cx="'+x2+'" cy="'+y2+'" r="5"/>';
  b+='<text class="dg-label" x="'+(x1+14)+'" y="'+(y1+4)+'">query</text>';
  b+='<text class="dg-label" x="'+(x2-10)+'" y="'+(y2-10)+'">chunk</text>';
  b+='<text class="dg-sub" x="'+(cx+34)+'" y="'+(cy-20)+'">θ — small angle = similar</text>';
  return {h:200, body:b};
})();

// HyDE: question → fake answer → embed → search (vs direct path)
D.hyde = (()=>{
  let b='';
  const w=130,h=48;
  // today's path
  b+=box(20,30,w,h,"Question","user text");
  b+=box(420,30,w,h,"Embed","bge-small");
  b+=box(578,30,w,h,"Search","FAISS/BM25");
  b+=arrow(20+w,54,420); b+=arrow(420+w,54,578);
  b+='<text class="dg-sub" x="290" y="44" text-anchor="middle">today: embed the question</text>';
  // hyde path
  b+=box(220,120,w+30,h,"Fake answer","LLM writes it",'dg-box dg-hot');
  b+=arrowV(85,30+h,144); b+='<line class="dg-line" x1="85" y1="144" x2="220" y2="144"/>';
  b+=arrow(220+w+30,144,485); b+=arrowV(485,144,30+h+7);
  b+='<text class="dg-sub" x="290" y="196" text-anchor="middle">HyDE: embed an answer-shaped stand-in, discard it after search</text>';
  return {h:210, body:b};
})();

// Tool calling: the request/execute loop
D.toolcall = (()=>{
  let b='';
  const w=130,h=52,y=40;
  b+=box(16,y,w,h,"Question","user");
  b+=box(196,y,w,h,"LLM","decides",'dg-box dg-hot');
  b+=box(392,y,w,h,"Your code","runs the tool");
  b+=box(572,y,w,h,"Answer","when done");
  b+=arrow(16+w,y+h/2,196);
  b+=arrow(196+w,y+h/2-10,392);
  b+='<text class="dg-sub" x="360" y="30" text-anchor="middle">"call retrieve(x)" — name + JSON args</text>';
  // return path
  b+='<line class="dg-line" x1="457" y1="'+(y+h)+'" x2="457" y2="'+(y+h+34)+'"/>';
  b+='<line class="dg-line" x1="457" y1="'+(y+h+34)+'" x2="261" y2="'+(y+h+34)+'"/>';
  b+=arrowV(261,y+h+34,y+h+7);
  b+='<text class="dg-sub" x="360" y="'+(y+h+52)+'" text-anchor="middle">result fed back as a message — loop until the model answers</text>';
  b+=arrow(196+w+266,y+h/2,572);
  return {h:170, body:b};
})();

// MCP: any client, one protocol, any server
D.mcp = (()=>{
  let b='';
  const w=140,h=44;
  ["LangGraph agent","CrewAI crew","Claude Desktop"].forEach((l,i)=>{
    b+=box(16,20+i*58,w,h,l,null);
    b+='<line class="dg-line" x1="'+(16+w)+'" y1="'+(42+i*58)+'" x2="290" y2="'+(42+58)+'"/>';
  });
  b+=box(290,78,w,h,"MCP","one protocol",'dg-box dg-hot');
  ["retrieve (DocsMind)","GitHub server","Slack server"].forEach((l,i)=>{
    b+=box(564-124+124,20+i*58,150,h,l,null); // x=564
    b+='<line class="dg-line" x1="'+(290+w)+'" y1="'+(42+58)+'" x2="564" y2="'+(42+i*58)+'"/>';
  });
  b+='<text class="dg-sub" x="360" y="196" text-anchor="middle">any client ↔ any server — no custom glue per pair</text>';
  return {h:210, body:b};
})();

// Agent architectures: supervisor routing
D.agents = (()=>{
  let b='';
  const w=150,h=48;
  b+=box(285,18,w,h,"Supervisor","routes only",'dg-box dg-hot');
  const xs=[60,285,510];
  ["Agent A","Agent B","Agent C"].forEach((l,i)=>{
    b+=box(xs[i],120,w,h,l,"own tools + prompt");
    b+=arrowV(xs[i]+w/2, 18+h, 120);
  });
  b+='<line class="dg-line" x1="'+(285+w/2)+'" y1="'+(18+h)+'" x2="'+(60+w/2)+'" y2="'+(18+h+20)+'" opacity="0"/>';
  b+='<text class="dg-sub" x="360" y="200" text-anchor="middle">sub-agents report back up — one place decisions get made and logged</text>';
  return {h:214, body:b};
})();

// Serving internals: inside the vLLM box
D.serving = (()=>{
  let b='';
  b+=box(16,66,120,52,"Prompt","request in");
  b+='<rect class="dg-box" x="196" y="20" width="330" height="150" rx="14" opacity="0.35"/>';
  b+='<text class="dg-sub" x="361" y="40" text-anchor="middle">vLLM — inside the serving box</text>';
  b+=box(226,52,270,32,"KV cache","remember attention history");
  b+=box(226,92,270,32,"Continuous batching","refill GPU slots mid-batch");
  b+=box(226,132,270,32,"Speculative decoding","draft small, verify big",'dg-box dg-hot');
  b+=box(586,66,118,52,"Tokens","streamed out");
  b+=arrow(136,92,196); b+=arrow(526,92,586);
  return {h:190, body:b};
})();

// Concurrency: thread pool vs event loop
D.concurrency = (()=>{
  let b='';
  const w=150,h=48;
  b+=box(16,40,130,h,"Request","POST /query");
  b+=box(216,40,w,h,"def query()","plain sync",'dg-box dg-hot');
  b+=box(436,40,170,h,"Thread pool","one thread waits");
  b+=arrow(146,64,216); b+=arrow(216+w,64,436);
  b+='<text class="dg-sub" x="360" y="126" text-anchor="middle">FastAPI runs sync handlers in a thread pool — the blocking</text>'+
     '<text class="dg-sub" x="360" y="144" text-anchor="middle">Anthropic call occupies one thread; other requests keep moving</text>';
  return {h:160, body:b};
})();

// HTTP semantics: GET vs POST
D.http = (()=>{
  let b='';
  const h=48;
  b+=box(16,26,150,h,"GET /health","no body");
  b+=box(360,26,170,h,"reads status","safe · cacheable");
  b+=arrow(166,50,360);
  b+=box(16,110,150,h,"POST /query","JSON body",'dg-box dg-hot');
  b+=box(360,110,170,h,"does real work","retrieval + LLM call");
  b+=arrow(166,134,360);
  b+='<text class="dg-sub" x="620" y="55" text-anchor="middle">poll it freely</text>';
  b+='<text class="dg-sub" x="620" y="139" text-anchor="middle">never retry blindly</text>';
  return {h:186, body:b};
})();

// Security: checkpoints along the query path
D.security = (()=>{
  let b='';
  const h=46,y=60;
  b+=box(10,y,104,h,"Question",null);
  b+=box(148,y,104,h,"Classify","jailbreak?",'dg-box dg-hot');
  b+=box(286,y,104,h,"Retrieve","RBAC filter",'dg-box dg-hot');
  b+=box(424,y,104,h,"Generate","injection-aware");
  b+=box(562,y,104,h,"Moderate","then answer",'dg-box dg-hot');
  b+=arrow(114,y+h/2,148); b+=arrow(252,y+h/2,286); b+=arrow(390,y+h/2,424); b+=arrow(528,y+h/2,562);
  b+='<text class="dg-sub" x="360" y="34" text-anchor="middle">security is several checkpoints, not one stage</text>';
  b+='<text class="dg-sub" x="360" y="140" text-anchor="middle">hard boundaries (RBAC, in code) before soft ones (prompt-level)</text>';
  return {h:156, body:b};
})();

// Fine-tuning: notes vs habits
D.finetune = (()=>{
  let b='';
  const h=48;
  b+=box(16,26,180,h,"RAG","frozen model");
  b+=box(266,26,200,h,"+ retrieved context","new facts at query time");
  b+=arrow(196,50,266);
  b+='<text class="dg-sub" x="580" y="55" text-anchor="middle">fixes knowledge</text>';
  b+=box(16,110,180,h,"Fine-tuning","new weights",'dg-box dg-hot');
  b+=box(266,110,200,h,"changed behavior","baked in by training");
  b+=arrow(196,134,266);
  b+='<text class="dg-sub" x="580" y="139" text-anchor="middle">fixes habits</text>';
  return {h:186, body:b};
})();

// Monitoring: events flowing to four dashboards
D.monitoring = (()=>{
  let b='';
  b+=box(16,64,170,52,"RAGPipeline.query()","already computes latency_ms");
  b+=box(276,64,140,52,"events","tokens · ms · model",'dg-box dg-hot');
  b+=arrow(186,90,276);
  const labels=[["Cost","per request"],["Latency","p50/p95/p99"],["Quality","golden set"],["Drift","vs baseline"]];
  labels.forEach((l,i)=>{
    b+=box(486,10+i*50,190,40,l[0],l[1]);
    b+='<line class="dg-line" x1="416" y1="90" x2="486" y2="'+(30+i*50)+'"/>';
  });
  return {h:216, body:b};
})();

// Multimodal: four sources converge into one pipeline
D.multimodal = (()=>{
  let b='';
  const srcs=[["Digital PDF","text extractor"],["Table","layout parser"],["Scan","OCR"],["Chart","vision model"]];
  srcs.forEach((l,i)=>{
    b+=box(16,10+i*52,150,42,l[0],l[1]);
    b+='<line class="dg-line" x1="166" y1="'+(31+i*52)+'" x2="286" y2="106"/>';
  });
  b+=box(286,80,150,52,"Normalize","same Document shape",'dg-box dg-hot');
  b+=box(506,80,190,52,"chunk → embed → index","existing pipeline, untouched");
  b+=arrow(436,106,506);
  return {h:226, body:b};
})();

/* page → [diagram key, caption]. Auto-injected right after the page <h1>. */
const DIAGRAMS = {
  "README.md": ["ingest","Index time: documents become searchable vectors"],
  "07-full-pipeline/README.md": ["query","Query time: a question becomes an answer with citations"],
  "07-full-pipeline/4-step-flow.md": ["query","The four steps every query runs through"],
  "04-vector-similarity/cosine-similarity.md": ["cosine","Cosine similarity — the angle between two unit vectors"],
  "11-hyde/README.md": ["hyde","HyDE — search with an answer-shaped stand-in, then throw it away"],
  "12-tool-calling/README.md": ["toolcall","Tool calling — the model requests, your code executes, results loop back"],
  "13-mcp/README.md": ["mcp","MCP — standardize the plug, not the electricity"],
  "14-agent-architectures/README.md": ["agents","Supervisor pattern — one router, specialist sub-agents, one audit trail"],
  "15-llm-serving-internals/README.md": ["serving","Inside the serving box — what vLLM does that Ollama hides"],
  "16-python-concurrency/README.md": ["concurrency","Why a plain def handler is correct for a blocking LLM call"],
  "17-fastapi-http-semantics/README.md": ["http","GET promises safety; POST carries a body and does real work"],
  "18-llm-security/README.md": ["security","Security checkpoints along the query path — several, not one"],
  "19-fine-tuning/README.md": ["finetune","RAG changes what the model sees; fine-tuning changes what it is"],
  "20-production-monitoring/README.md": ["monitoring","One event stream, four different signals"],
  "21-multimodal-document-rag/README.md": ["multimodal","Four extraction paths converge — the pipeline never knows the difference"],
};

/* section metadata: icon (emoji), accent, tagline.
 * Accents are mid-tones chosen to read on BOTH the cream light bg and the dark bg. */
const SECTIONS = {
  "Start here":            { icon:"🧭", accent:"#d4663f", tag:"The big picture and how to use this site" },
  "1 · Chunks & Overlap":  { icon:"✂️", accent:"#14a3a3", tag:"Why we split documents, and what overlap buys" },
  "2 · Embeddings":        { icon:"🔢", accent:"#8b6dff", tag:"Turning text into meaning-carrying numbers" },
  "3 · Normalization":     { icon:"📐", accent:"#d39a1f", tag:"The vector math that makes search fair" },
  "4 · Vector Similarity": { icon:"🎯", accent:"#34ad7c", tag:"Measuring closeness between two vectors" },
  "5 · FAISS":             { icon:"🗄️", accent:"#4a8bd1", tag:"Storing vectors and finding the nearest fast" },
  "6 · Generation":        { icon:"💬", accent:"#dd5b54", tag:"Context, prompting, citations, the guardrail" },
  "7 · Full Pipeline":     { icon:"🔗", accent:"#cc5fab", tag:"Every piece wired together, end to end" },
  "8 · Interview Prep":    { icon:"🎤", accent:"#7479e6", tag:"Every \"why X over Y\", quiz-ready" },
  "9 · Hybrid Retrieval":  { icon:"⚖️", accent:"#19a4d1", tag:"Dense + BM25 + reranking (Phase 3)" },
  "10 · Qdrant":           { icon:"🧩", accent:"#b5651d", tag:"A vector store you talk to (Phase 2b)" },
  "11 · HyDE":             { icon:"🔮", accent:"#9c55d4", tag:"Search with a fake answer (Phase 5 preview)" },
  "12 · Tool Calling":     { icon:"🛠️", accent:"#2e9e6b", tag:"The LLM asks, your code answers" },
  "13 · MCP":              { icon:"🔌", accent:"#5a7fd6", tag:"A USB port for tools" },
  "14 · Agent Architectures": { icon:"🕸️", accent:"#c25a8a", tag:"One loop vs many, and who's in charge" },
  "15 · LLM Serving Internals": { icon:"⚙️", accent:"#d97f2f", tag:"KV cache, batching, speculative decoding" },
  "16 · Python Concurrency":  { icon:"🧵", accent:"#43a89a", tag:"Sync, async, threads, processes — the right lever" },
  "17 · FastAPI & HTTP Semantics": { icon:"🌐", accent:"#6e9e3f", tag:"GET vs POST, and contracts that enforce themselves" },
  "18 · LLM Security":     { icon:"🛡️", accent:"#c0564f", tag:"PII, injection, jailbreaks, RBAC, moderation" },
  "19 · Fine-Tuning":      { icon:"🎛️", accent:"#7a5fd0", tag:"When RAG isn't the right tool" },
  "20 · Production Monitoring": { icon:"📈", accent:"#3f8fbf", tag:"Cost, latency, quality, drift" },
  "21 · Multimodal Document RAG": { icon:"📄", accent:"#b58a2a", tag:"PDFs, tables, scans, charts — an ingest problem" },
  "22 · LangGraph":        { icon:"🕸️", accent:"#5a7fd6", tag:"State, nodes, edges — build the agent graph" },
};

module.exports = { D, DIAGRAMS, SECTIONS, fig };
