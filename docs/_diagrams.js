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

/* page → [diagram key, caption]. Auto-injected right after the page <h1>. */
const DIAGRAMS = {
  "README.md": ["ingest","Index time: documents become searchable vectors"],
  "07-full-pipeline/README.md": ["query","Query time: a question becomes an answer with citations"],
  "07-full-pipeline/4-step-flow.md": ["query","The four steps every query runs through"],
  "04-vector-similarity/cosine-similarity.md": ["cosine","Cosine similarity — the angle between two unit vectors"],
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
};

module.exports = { D, DIAGRAMS, SECTIONS, fig };
