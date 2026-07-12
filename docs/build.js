#!/usr/bin/env node
/* Build a single self-contained index.html from the markdown files.
 * Renders all .md to HTML at build time (no runtime markdown engine, no fetch).
 * Result works offline by double-click (file://) AND when served.
 *
 *   node build.js
 *
 * Edit the .md files, then re-run this to regenerate index.html.
 */
const fs = require("fs");
const path = require("path");
const ROOT = __dirname;
const { D, DIAGRAMS, SECTIONS, fig } = require("./_diagrams.js");

/* ----------------------------- site structure ----------------------------- */
const SITE = [
  { label:"Start here", items:[
    { dir:"", file:"README.md", title:"Overview & Learning Path" },
    { dir:"", file:"RUN-ON-PI.md", title:"Run on a Raspberry Pi" },
  ]},
  { label:"1 · Chunks & Overlap", dir:"01-chunks-and-overlap", items:[
    { file:"README.md", title:"Overview" },
    { file:"what-is-a-chunk.md", title:"What Is a Chunk?" },
    { file:"why-overlap.md", title:"Why Overlap?" },
    { file:"real-examples.md", title:"Real Examples" },
  ]},
  { label:"2 · Embeddings", dir:"02-embeddings", items:[
    { file:"README.md", title:"Overview" },
    { file:"problem-text-is-not-numbers.md", title:"The Problem: Text Is Not Numbers" },
    { file:"what-is-an-embedding.md", title:"What Is an Embedding?" },
    { file:"similar-text-similar-vectors.md", title:"Similar Text → Similar Vectors" },
    { file:"bge-small-model.md", title:"The bge-small Model" },
    { file:"real-examples.md", title:"Real Examples" },
  ]},
  { label:"3 · Normalization", dir:"03-normalization", items:[
    { file:"README.md", title:"Overview" },
    { file:"why-length-1.md", title:"Why Length 1.0 Is Fair" },
    { file:"l2-normalization-math.md", title:"L2 Normalization — The Math" },
    { file:"code-example.md", title:"Normalization in Code" },
  ]},
  { label:"4 · Vector Similarity", dir:"04-vector-similarity", items:[
    { file:"README.md", title:"Overview" },
    { file:"cosine-similarity.md", title:"Cosine Similarity" },
    { file:"similarity-scores.md", title:"Reading Similarity Scores" },
    { file:"search-example.md", title:"Search Example — Question to Top-k" },
  ]},
  { label:"5 · FAISS", dir:"05-faiss", items:[
    { file:"README.md", title:"Overview" },
    { file:"problem-slow-search.md", title:"The Problem: Brute-Force Doesn't Scale" },
    { file:"indexflatip-explained.md", title:"IndexFlatIP — Phase 1's Index" },
    { file:"how-search-works.md", title:"How FAISS Search Works" },
    { file:"code-walkthrough.md", title:"Code Walkthrough" },
    { file:"benchmark-results.md", title:"Benchmark Results" },
    { file:"phase1-vs-phase2.md", title:"Flat vs IVF vs HNSW vs PQ" },
  ]},
  { label:"6 · Generation", dir:"06-generation", items:[
    { file:"README.md", title:"Overview" },
    { file:"system-prompt.md", title:"The System Prompt" },
    { file:"building-context.md", title:"Building the Context" },
    { file:"claude-generates.md", title:"The LLM Generates the Answer" },
    { file:"citation-extraction.md", title:"Citation Extraction" },
    { file:"guardrail.md", title:"The Guardrail — INSUFFICIENT_CONTEXT" },
  ]},
  { label:"7 · Full Pipeline", dir:"07-full-pipeline", items:[
    { file:"README.md", title:"Overview" },
    { file:"4-step-flow.md", title:"The 4-Step Flow" },
    { file:"phase1-end-to-end.md", title:"How the Code Wires Together" },
    { file:"real-query-example.md", title:"Real Query Example — End to End" },
  ]},
  { label:"8 · Interview Prep", dir:"08-interview-prep", items:[
    { file:"README.md", title:"Overview" },
    { file:"chunking-questions.md", title:"Chunking Questions", quiz:true },
    { file:"embedding-questions.md", title:"Embedding Questions", quiz:true },
    { file:"retrieval-questions.md", title:"Retrieval Questions", quiz:true },
    { file:"index-questions.md", title:"Index & Vector DB Questions", quiz:true },
    { file:"hybrid-questions.md", title:"Hybrid & Reranking Questions", quiz:true },
    { file:"generation-questions.md", title:"Generation Questions", quiz:true },
    { file:"pipeline-questions.md", title:"Pipeline Questions", quiz:true },
    { file:"cheat-sheet.md", title:"Cheat Sheet — One Page" },
  ]},
  { label:"9 · Hybrid Retrieval", dir:"09-hybrid-retrieval", items:[
    { file:"README.md", title:"Overview" },
    { file:"reranking-deep-dive.md", title:"Reranking — The Deep Dive" },
    { file:"search-evaluation.md", title:"Search Evaluation" },
    { file:"eval-results.md", title:"Eval Results — Does Hybrid Win?" },
  ]},
  { label:"10 · Qdrant", dir:"10-qdrant", items:[
    { file:"README.md", title:"Overview" },
  ]},
  { label:"11 · HyDE", dir:"11-hyde", items:[
    { file:"README.md", title:"Overview" },
    { file:"problem-and-fix.md", title:"The Problem and the Fix" },
    { file:"code-seam-and-tradeoffs.md", title:"The Code Seam and the Cost" },
    { file:"query-transformations.md", title:"Query Transformations — The Family" },
  ]},
  { label:"12 · Tool Calling", dir:"12-tool-calling", items:[
    { file:"README.md", title:"Overview" },
    { file:"the-loop.md", title:"The Loop — Request, Execute, Continue" },
    { file:"code-seam.md", title:"The Code Seam — Two Precise Places" },
    { file:"reliability-and-security.md", title:"Reliability & Security — The Real Work" },
  ]},
  { label:"13 · MCP", dir:"13-mcp", items:[
    { file:"README.md", title:"Overview" },
    { file:"why-a-protocol.md", title:"Why a Protocol — The N × M Problem" },
    { file:"docsmind-as-a-server.md", title:"DocsMind as a Server — and Why Not Yet" },
  ]},
  { label:"14 · Agent Architectures", dir:"14-agent-architectures", items:[
    { file:"README.md", title:"Overview" },
    { file:"framework-comparison.md", title:"Frameworks — Four Tools, Four Layers" },
    { file:"patterns.md", title:"Single vs Multi-Agent vs Supervisor" },
    { file:"docsmind-choice.md", title:"DocsMind's Choice — One LangGraph Loop" },
  ]},
  { label:"15 · LLM Serving Internals", dir:"15-llm-serving-internals", items:[
    { file:"README.md", title:"Overview" },
    { file:"kv-cache.md", title:"KV Cache — Memory for Compute" },
    { file:"continuous-batching.md", title:"Continuous Batching — No Idle GPU" },
    { file:"speculative-decoding.md", title:"Speculative Decoding — Guess & Verify" },
  ]},
  { label:"16 · Python Concurrency", dir:"16-python-concurrency", items:[
    { file:"README.md", title:"Overview" },
    { file:"four-models.md", title:"Sync, Async, Threads, Processes & the GIL" },
    { file:"docsmind-server.md", title:"DocsMind's Server & the Async Footgun" },
  ]},
  { label:"17 · FastAPI & HTTP Semantics", dir:"17-fastapi-http-semantics", items:[
    { file:"README.md", title:"Overview" },
    { file:"get-vs-post.md", title:"GET vs POST — Semantics, Not Convention" },
    { file:"request-contract.md", title:"The Request/Response Contract" },
    { file:"async-endpoint.md", title:"Building a Genuinely Async Endpoint" },
  ]},
  { label:"18 · LLM Security", dir:"18-llm-security", items:[
    { file:"README.md", title:"Overview" },
    { file:"five-problems.md", title:"The Five Problems" },
    { file:"code-seams.md", title:"The Code Seams — Where Defenses Slot In" },
    { file:"red-team-validation.md", title:"Costs, Severity & Red-Team Validation" },
  ]},
  { label:"19 · Fine-Tuning", dir:"19-fine-tuning", items:[
    { file:"README.md", title:"Overview" },
    { file:"rag-vs-fine-tuning.md", title:"RAG vs Fine-Tuning — Knowledge vs Behavior" },
    { file:"lora-qlora-peft-rlhf.md", title:"LoRA, QLoRA, PEFT, RLHF — Untangled" },
    { file:"tool-call-fix-path.md", title:"The Tool-Call Fix Path, in Cost Order" },
  ]},
  { label:"20 · Production Monitoring", dir:"20-production-monitoring", items:[
    { file:"README.md", title:"Overview" },
    { file:"four-signals.md", title:"The Four Signals — Cost, Latency, Quality, Drift" },
    { file:"wiring-it-in.md", title:"Wiring It In — Seams & Fire-Testing" },
  ]},
  { label:"21 · Multimodal Document RAG", dir:"21-multimodal-document-rag", items:[
    { file:"README.md", title:"Overview" },
    { file:"four-content-types.md", title:"Four Content Types, Four Extraction Problems" },
    { file:"classify-route-normalize.md", title:"The Design — Classify, Route, Normalize" },
  ]},
  { label:"22 · LangGraph", dir:"22-langgraph", items:[
    { file:"README.md", title:"Overview" },
    { file:"state-nodes-edges.md", title:"State, Nodes, Edges — The Whole Model" },
    { file:"build-a-graph.md", title:"Build a Graph — Retrieve → Generate" },
    { file:"conditional-edges.md", title:"Conditional Edges — Branch & Loop" },
  ]},
];

/* ----------------------------- markdown parser ----------------------------- */
function escapeHtml(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function slug(s){return s.toLowerCase().replace(/<[^>]+>/g,"").replace(/[^\w\s-]/g,"").trim().replace(/\s+/g,"-");}

/* ----- lightweight build-time syntax highlighter (Python / bash) ----- */
const HL = {
  python: {
    re: /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?''')|([rbfRBF]{0,2}"(?:\\.|[^"\\])*"|[rbfRBF]{0,2}'(?:\\.|[^'\\])*')|(@[A-Za-z_]\w*)|\b(def|class|return|if|elif|else|for|while|try|except|finally|with|as|import|from|in|not|and|or|lambda|yield|pass|break|continue|global|nonlocal|raise|assert|del|is|async|await|None|True|False|self)\b|\b(print|len|range|int|str|float|list|dict|set|tuple|bool|bytes|open|enumerate|zip|map|filter|isinstance|super|hash|abs|min|max|sum|np|cv2|faiss|torch|Gst|GLib|GObject|gi|pyds)\b|\b(0[xX][0-9a-fA-F]+|\d+\.?\d*)\b/g,
    cls: ["comment","string","string","decorator","keyword","builtin","number"]
  },
  bash: {
    re: /(#[^\n]*)|("(?:\\.|[^"\\])*"|'[^']*')|\b(gst-launch-1\.0|gst-inspect-1\.0|ffprobe|ffmpeg|python3?|node|pip3?|uv|bash|sudo|export|cd|dot|curl|docker|systemctl|journalctl|scp|git|cat|grep|ls|make)\b|(\$\{[^}]+\}|\$\w+)|(?<![\w-])(-{1,2}[A-Za-z][\w-]*)|\b(0[xX][0-9a-fA-F]+|\d+\.?\d*)\b/g,
    cls: ["comment","string","command","variable","flag","number"]
  }
};
HL.py = HL.python; HL.sh = HL.bash; HL.shell = HL.bash;
function highlight(code, lang){
  const spec = HL[lang];
  if(!spec) return escapeHtml(code);
  let out="", last=0, m;
  spec.re.lastIndex = 0;
  while((m = spec.re.exec(code))){
    if(m.index>last) out += escapeHtml(code.slice(last, m.index));
    let cls="text";
    for(let g=1; g<m.length; g++){ if(m[g]!==undefined){ cls=spec.cls[g-1]; break; } }
    out += '<span class="tok-'+cls+'">'+escapeHtml(m[0])+'</span>';
    last = spec.re.lastIndex;
    if(m[0]===""){ spec.re.lastIndex++; last = spec.re.lastIndex; }
  }
  out += escapeHtml(code.slice(last));
  return out;
}

function inlineMd(s){
  const codes=[];
  s = s.replace(/`([^`]+)`/g, (m,c)=>{ codes.push(c); return "@@CODE"+(codes.length-1)+"@@"; });
  s = escapeHtml(s);
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m,t,u)=>{
    const ext = /^(https?:)?\/\//.test(u) || /^mailto:/.test(u);
    if(ext) return '<a href="'+u+'" target="_blank" rel="noopener">'+t+'</a>';
    if(u.charAt(0)==='#') return '<a href="'+u+'">'+t+'</a>';
    // Links to repo source files (.py, .json, …) aren't pages in this site.
    // Render them as an inert file reference instead of a dead link.
    const clean = u.split("#")[0];
    if(/\.[a-z0-9]+$/i.test(clean) && !/\.md$/i.test(clean))
      return '<code class="srcref" title="source file in the repo">'+t+'</code>';
    return '<a class="mdlink" data-href="'+u.replace(/"/g,'&quot;')+'" href="#">'+t+'</a>';
  });
  s = s.replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>");
  s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g,"$1<em>$2</em>");
  s = s.replace(/@@CODE(\d+)@@/g,(m,i)=>"<code>"+escapeHtml(codes[+i])+"</code>");
  return s;
}
function isSep(line){ return /^\s*\|?[\s:|-]*-[-\s:|]*\|?\s*$/.test(line) && line.indexOf("-")>=0; }
function splitRow(line){
  let s = line.trim();
  if(s.charAt(0)==="|") s=s.slice(1);
  if(s.charAt(s.length-1)==="|") s=s.slice(0,-1);
  return s.split("|").map(c=>c.trim());
}
function renderMarkdown(md){
  const lines = md.replace(/\r\n?/g,"\n").split("\n");
  let i=0, out=[];
  const isListItem = l => /^(\s*)([-*+]|\d+\.)\s+/.test(l);
  while(i<lines.length){
    let line = lines[i];
    if(line.trim()===""){ i++; continue; }
    if(/^\s*```/.test(line)){
      const lang = line.trim().replace(/^```/,"").trim();
      i++; let buf=[];
      while(i<lines.length && !/^\s*```/.test(lines[i])){ buf.push(lines[i]); i++; }
      i++;
      const code = buf.join("\n");
      if(/^fig:/.test(lang)){                       // inline SVG diagram
        const name = lang.slice(4).trim();
        const cap = code.trim().replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
        out.push(D[name] ? fig(D[name], cap) : '<pre><code>'+escapeHtml(code)+'</code></pre>');
        continue;
      }
      out.push('<pre><code'+(lang?' class="language-'+lang+'"':'')+'>'+highlight(code, lang)+'</code></pre>');
      continue;
    }
    let h = line.match(/^(#{1,6})\s+(.*)$/);
    if(h){
      const lvl=h[1].length, txt=h[2].trim();
      out.push('<h'+lvl+' id="'+slug(txt)+'">'+inlineMd(txt)+'</h'+lvl+'>');
      i++; continue;
    }
    if(/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)){ out.push("<hr>"); i++; continue; }
    if(/^\s*>/.test(line)){
      let buf=[];
      while(i<lines.length && /^\s*>/.test(lines[i])){ buf.push(lines[i].replace(/^\s*>\s?/,"")); i++; }
      out.push("<blockquote>"+renderMarkdown(buf.join("\n"))+"</blockquote>");
      continue;
    }
    if(line.indexOf("|")>=0 && i+1<lines.length && isSep(lines[i+1])){
      const header = splitRow(line);
      i+=2; let rows=[];
      while(i<lines.length && lines[i].indexOf("|")>=0 && lines[i].trim()!==""){ rows.push(splitRow(lines[i])); i++; }
      let t='<table><thead><tr>'+header.map(c=>"<th>"+inlineMd(c)+"</th>").join("")+"</tr></thead><tbody>";
      rows.forEach(r=>{ t+="<tr>"+header.map((_,k)=>"<td>"+inlineMd(r[k]||"")+"</td>").join("")+"</tr>"; });
      t+="</tbody></table>";
      out.push('<div class="table-scroll">'+t+'</div>');
      continue;
    }
    if(isListItem(line)){
      let items=[];
      while(i<lines.length && isListItem(lines[i])){
        const m=lines[i].match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
        items.push({ indent:m[1].length, ordered:/\d+\./.test(m[2]), text:m[3] });
        i++;
      }
      out.push(buildList(items));
      continue;
    }
    let buf=[];
    while(i<lines.length){
      const l=lines[i];
      if(l.trim()==="" || /^\s*```/.test(l) || /^#{1,6}\s/.test(l) ||
         /^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(l) || /^\s*>/.test(l) || isListItem(l) ||
         (l.indexOf("|")>=0 && i+1<lines.length && isSep(lines[i+1]))) break;
      buf.push(l); i++;
    }
    out.push("<p>"+inlineMd(buf.join(" ").trim())+"</p>");
  }
  return out.join("\n");
}
function buildList(items){
  let pos=0;
  function helper(curIndent){
    const ordered=items[pos].ordered;
    let html=ordered?"<ol>":"<ul>";
    while(pos<items.length && items[pos].indent>=curIndent){
      if(items[pos].indent>curIndent){
        const sub=helper(items[pos].indent);
        html=html.replace(/<\/li>$/, sub+"</li>");
      } else {
        html+="<li>"+inlineMd(items[pos].text)+"</li>";
        pos++;
      }
    }
    html+=ordered?"</ol>":"</ul>";
    return html;
  }
  return helper(items[0].indent);
}

/* ------------------- transforms applied to rendered HTML ------------------- */
// Turn "## Q: ... ?" headings + following answer into collapsible <details>.
// docs_mind interview files use "## Q: ..." headings (not bold Q: paragraphs).
function wrapQA(html){
  html = html.replace(
    /<h2 id="[^"]*">\s*(Q:[\s\S]*?)<\/h2>([\s\S]*?)(?=<h2 |<h1 |<hr>|$)/g,
    (m, q, body) =>
      '<details class="qa" open><summary>'+q.trim()+'</summary><div class="qa-body">'+body.trim()+'</div></details>'
  );
  // drop the "---" separators that sat between consecutive questions
  html = html.replace(/<\/details>\s*<hr>\s*(?=<details class="qa")/g, "</details>\n");
  return html;
}
function extractTOC(html){
  const toc=[]; const re=/<h([23]) id="([^"]+)">([\s\S]*?)<\/h\1>/g; let m;
  while((m=re.exec(html))) toc.push({ level:+m[1], id:m[2], text:m[3].replace(/<[^>]+>/g,"") });
  return toc;
}
function stripTags(html){ return html.replace(/<[^>]+>/g," ").replace(/&amp;/g,"&").replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/\s+/g," ").trim(); }

/* Set of every page path in the site (for dead-link detection). */
const ALL_PATHS = new Set();
SITE.forEach(sec => sec.items.forEach(it => ALL_PATHS.add((sec.dir?sec.dir+"/":"")+it.file)));
function resolveRel(curPath, href){
  href = href.split("#")[0];
  if(href==="") return null;
  if(/\/$/.test(href)) href += "README.md";
  const base = curPath.split("/").slice(0,-1);
  href.split("/").forEach(p=>{ if(p==="."||p==="") return; if(p==="..") base.pop(); else base.push(p); });
  return base.join("/");
}
// Any internal mdlink that doesn't resolve to a real page (source files, sample
// corpus docs, etc.) becomes an inert file reference instead of a dead link.
function fixDeadLinks(html, relPath){
  return html.replace(/<a class="mdlink" data-href="([^"]*)" href="#">([\s\S]*?)<\/a>/g,
    (m, href, txt) => {
      const tgt = resolveRel(relPath, href.replace(/&quot;/g,'"'));
      return (tgt && ALL_PATHS.has(tgt)) ? m : '<code class="srcref" title="file in the repo">'+txt+'</code>';
    });
}

/* ------------------------------- build data -------------------------------- */
// Turn "**TL;DR:** ..." into a highlighted insight card.
function calloutTLDR(html){
  return html.replace(/<p><strong>TL;DR:?<\/strong>\s*([\s\S]*?)<\/p>/,
    (m, body) => '<div class="callout tldr"><div class="cic">💡</div><div class="cbody"><span class="clead">TL;DR</span> '+body.trim()+'</div></div>');
}
// Inject a concept diagram right after the page's <h1>.
function injectDiagram(rel, html){
  const d = DIAGRAMS[rel]; if(!d) return html;
  const svg = fig(D[d[0]], d[1]);
  return /<\/h1>/.test(html) ? html.replace(/<\/h1>/, "</h1>\n"+svg) : svg+html;
}
// Graphical section cards for the home page.
function homeCards(){
  const cards = SITE.filter(s=>s.dir).map(sec=>{
    const m = SECTIONS[sec.label] || {};
    const href = sec.dir + "/README.md";
    return '<a class="seccard mdlink" data-href="'+href+'" href="#" style="--card:'+m.accent+'">'+
      '<span class="sc-ic">'+(m.icon||"•")+'</span>'+
      '<span class="sc-lbl">'+sec.label+'</span>'+
      '<span class="sc-tag">'+(m.tag||"")+'</span></a>';
  }).join("");
  return '<h2 id="jump-in">Jump in</h2><div class="section-cards">'+cards+'</div>';
}
const HOME_HERO =
  '<div class="hero"><span class="hero-badge">DocsMind · RAG from Scratch</span>'+
  '<div class="hero-title">Retrieval-Augmented Generation, Explained</div>'+
  '<p class="hero-sub">How a question finds the right passages and turns them into a cited answer — '+
  'chunking, embeddings, normalization, similarity, FAISS, and generation, one chapter at a time.</p></div>';

const PAGES = [];
SITE.forEach(sec => sec.items.forEach(it => {
  const rel = (sec.dir ? sec.dir + "/" : "") + it.file;
  const md = fs.readFileSync(path.join(ROOT, rel), "utf8");
  let html = renderMarkdown(md);
  if(it.quiz) html = wrapQA(html);
  html = calloutTLDR(html);
  html = injectDiagram(rel, html);
  html = fixDeadLinks(html, rel);
  if(rel === "README.md"){
    html = HOME_HERO + html;
    html = /<\/figure>/.test(html) ? html.replace(/<\/figure>/, "</figure>\n"+homeCards())
                                   : html + homeCards();
  }
  const toc = extractTOC(html);
  const text = stripTags(html).toLowerCase();
  const meta = SECTIONS[sec.label] || {};
  PAGES.push({ path:rel, title:it.title, section:sec.label, quiz:!!it.quiz,
    accent:meta.accent||"", html, toc, text, words: text.split(" ").length });
}));

const NAV = SITE.map(sec => {
  const m = SECTIONS[sec.label] || {};
  return { label: sec.label, icon: m.icon||"", accent: m.accent||"var(--accent)",
    items: sec.items.map(it => ({ path:(sec.dir?sec.dir+"/":"")+it.file, title:it.title })) };
});

const DATA = { nav: NAV, pages: PAGES };
let dataJson = JSON.stringify(DATA).replace(/<\//g, "<\\/");  // keep </script> safe

/* --------------------------------- template -------------------------------- */
const CSS = fs.readFileSync(path.join(ROOT, "_site.css"), "utf8");
const APP = fs.readFileSync(path.join(ROOT, "_app.js"), "utf8");

const HTML =
'<!doctype html>\n<html lang="en">\n<head>\n' +
'<meta charset="utf-8">\n' +
'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' +
'<meta name="theme-color" content="#d97757">\n' +
'<title>DocsMind — RAG from Scratch</title>\n' +
'<style>\n' + CSS + '\n</style>\n</head>\n<body>\n' +
'<div class="app">\n' +
'  <aside class="sidebar" id="sidebar">\n' +
'    <div class="brand">\n' +
'      <h1>DocsMind</h1>\n' +
'      <div class="sub">RAG from Scratch — a learning path</div>\n' +
'      <div class="tools">\n' +
'        <input id="search" type="search" placeholder="Search all pages…" autocomplete="off" autocapitalize="off" spellcheck="false">\n' +
'        <button class="iconbtn theme-toggle" title="Toggle light / dark">◐</button>\n' +
'      </div>\n' +
'    </div>\n' +
'    <nav id="nav"></nav>\n' +
'  </aside>\n' +
'  <main class="main">\n' +
'    <div class="topbar">\n' +
'      <button class="iconbtn" id="menu" aria-label="Open menu">☰</button>\n' +
'      <span class="tb-title" id="tbTitle">DocsMind</span>\n' +
'      <button class="iconbtn" id="searchBtn" aria-label="Search">🔍</button>\n' +
'      <button class="iconbtn theme-toggle" aria-label="Toggle theme">◐</button>\n' +
'    </div>\n' +
'    <div class="content-wrap">\n' +
'      <div id="pagetools"></div>\n' +
'      <article id="content"></article>\n' +
'      <div class="pager" id="pager"></div>\n' +
'    </div>\n' +
'  </main>\n' +
'</div>\n' +
'<div class="scrim" id="scrim"></div>\n' +
'<div class="searchpanel" id="searchpanel"></div>\n' +
'<script>\nconst DATA=' + dataJson + ';\n' + APP + '\n</script>\n' +
'</body>\n</html>\n';

fs.writeFileSync(path.join(ROOT, "index.html"), HTML);
const kb = (Buffer.byteLength(HTML)/1024).toFixed(0);
const totalWords = PAGES.reduce((a,p)=>a+p.words,0);
console.log("Built index.html  ("+kb+" KB, "+PAGES.length+" pages, ~"+totalWords+" words embedded)");
