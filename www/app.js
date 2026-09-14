/* YahBible Mobile — offline app logic. Reuses the desktop study renderers over bundled data. */
"use strict";
const $ = (s, r) => (r || document).querySelector(s);
const CMDS = (window.YB_CMDS || []);
const REPENT = (window.YB_REPENT || null);
const NEWS = (window.YB_NEWS || { version: "", entries: [] });
const KJV = (window.YB_KJV || { books: [] });
/* resolve a scripture reference's book name to a KJV book index */
const BOOKMAP = {};
KJV.books.forEach((b,i)=>{ BOOKMAP[b.n.toLowerCase()]=i; BOOKMAP[b.a.toLowerCase()]=i; });
BOOKMAP['psalm']=BOOKMAP['psalms']; BOOKMAP['song of songs']=BOOKMAP['song of solomon'];
BOOKMAP['canticles']=BOOKMAP['song of solomon']; BOOKMAP['1 cor']=BOOKMAP['1 corinthians'];
function resolveBook(name){ if(!name) return -1; const k=name.trim().toLowerCase();
  if(k in BOOKMAP) return BOOKMAP[k];
  for(const b in BOOKMAP){ if(b.indexOf(k)===0||k.indexOf(b)===0) return BOOKMAP[b]; }
  return -1; }
const DIMHUE = {Physical:'#e0563b',Emotional:'#e8912e',Mental:'#e7c94e',Ambitional:'#5fd39a',Vocal:'#59b8ff',Intentional:'#8a7be8',Spiritual:'#c07ad9'};
const DIMLAYERS=[
  {name:'Spiritual',hue:'#c07ad9',sub:'allegiance, counsel, obedience'},
  {name:'Intentional',hue:'#8a7be8',sub:'will, consent, choice'},
  {name:'Vocal',hue:'#59b8ff',sub:'speech, vows, testimony'},
  {name:'Ambitional',hue:'#5fd39a',sub:'desires, pursuits, kingdom'},
  {name:'Mental',hue:'#e7c94e',sub:'thoughts, reasoning, judgment'},
  {name:'Emotional',hue:'#e8912e',sub:'affections, fears, attachments'},
  {name:'Physical',hue:'#e0563b',sub:'the body, actions, habits'}];
const MAN_PATH='M50 8 C57 8 62 14 62 22 C62 28 58 33 52 34 C66 37 74 52 76 78 C76 100 62 112 50 112 C38 112 24 100 24 78 C26 52 34 37 48 34 C42 33 38 28 38 22 C38 14 43 8 50 8 Z';
const _LAYERSUB={Spiritual:'the core — allegiance and counsel: whom do I obey?',Intentional:'the will — consent and choice',Vocal:'speech — vows and testimony',Ambitional:'desire — what I pursue as a kingdom',Mental:'thought — reasoning and judgment',Emotional:'affection — fears and attachments',Physical:'the surface — the body and its actions'};
const GENDIMS = [
  {name:'Physical',marker:'🔴',sub:'the body, actions, habits'},
  {name:'Emotional',marker:'🟠',sub:'affections, fears, attachments'},
  {name:'Mental',marker:'🟡',sub:'thoughts, reasoning, judgment'},
  {name:'Ambitional',marker:'🟢',sub:'desires, pursuits, kingdom'},
  {name:'Vocal',marker:'🔵',sub:'speech, vows, testimony'},
  {name:'Intentional',marker:'🟣',sub:'will, consent, choice'},
  {name:'Spiritual',marker:'🟪',sub:'allegiance, counsel, obedience'}];
let _curCmd = null, _lordsSeen = false, _tab = 'home';

function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
let _toastT = null;
function toast(msg){ let t=$('#toast'); if(!t){t=document.createElement('div');t.id='toast';document.body.appendChild(t);}
  t.textContent=msg; t.classList.add('on'); clearTimeout(_toastT); _toastT=setTimeout(()=>t.classList.remove('on'),2600); }

function linkifyScripture(text){ if(!text) return '';
  return esc(text).replace(/((?:[1-3]\s)?[A-Z][A-Za-z]+)\s+(\d+):(\d+(?:[–\-]\d+)?)/g,
    (mm,b,c,v)=>'<span class="scref" data-ref="'+esc(b+' '+c+':'+v)+'">'+mm+'</span>'); }
function wireScref(scope){ (scope||document).querySelectorAll('.scref').forEach(el=>el.onclick=e=>{
  e.stopPropagation(); const m=/^(.+?)\s+(\d+):(\d+)/.exec(el.dataset.ref||'');
  if(m){ const bi=resolveBook(m[1]); if(bi>=0){ openReader(bi,+m[2],+m[3]); return; } }
  toast('📖 '+(el.dataset.ref||'')); }); }

function renderBlocks(blocks){ if(!blocks||!blocks.length) return '';
  return blocks.map(b=>{
    if(b.t==='s') return '<div class="cscr">&ldquo;'+linkifyScripture(b.text||'')+'&rdquo;'+(b.ref?'<span class="cscrref">'+linkifyScripture(b.ref)+'</span>':'')+'</div>';
    if(b.t==='ref') return '<div class="cxrefs"><span class="cxrl">Scriptures</span>'+linkifyScripture(b.text||'')+'</div>';
    if(b.t==='belief') return '<div class="beliefbox"><span class="bblbl">Believe</span>'+allowBold(linkifyScripture(b.text||''))+'</div>';
    if(b.t==='prayer') return '<div class="prayerbox">&ldquo;'+linkifyScripture(b.text||'')+'&rdquo;'+(b.ref?'<span class="cscrref">'+linkifyScripture(b.ref)+'</span>':'')+'</div>';
    if(b.t==='refline') return '<div class="refline"><span class="rlt">'+esc(b.text||'')+'</span>'+(b.ref?'<span class="scref" data-ref="'+esc(b.ref)+'">'+linkifyScripture(b.ref)+'</span>':'')+'</div>';
    return '<p>'+allowBold(linkifyScripture(b.text||''))+'</p>';
  }).join(''); }
function allowBold(h){ return (h||'').replace(/&lt;(\/?)b&gt;/g,'<$1b>'); }

function renderOnion(dims){
  const draw=DIMLAYERS.slice().reverse();
  const men=draw.map((d,i)=>{ const s=(1.0-i*0.108).toFixed(3);
    return '<g class="onlayer" data-dim="'+esc(d.name)+'" transform="translate(50,62) scale('+s+') translate(-50,-62)"><path d="'+MAN_PATH+'" fill="'+d.hue+'"/></g>'; }).join('');
  const leg=DIMLAYERS.map(d=>'<button class="onionlegitem" data-dim="'+esc(d.name)+'"><span class="oldot" style="background:'+d.hue+'"></span>'+
    '<span class="olname">'+esc(d.name)+'</span><span class="olsub">'+esc(d.sub||'')+'</span></button>').join('');
  return '<div class="onionwrap"><div class="onion"><svg viewBox="0 0 100 124" class="onionsvg" role="img" aria-label="The person in seven layers, spirit at the core">'+
    men+'</svg></div><div class="onilbl">The person, layer by layer</div><div class="onionleg">'+leg+'</div>'+
    '<div class="onioncap" id="onioncap">Spirit at the core (violet), flesh on the surface (scarlet). Sin forms in a deeper layer first — tap a layer to see its role.</div></div>'; }
function renderLadder(g){ if(!g||!g.ladder||!g.ladder.length) return '';
  const steps=g.ladder.map(l=>'<div class="ladrow" data-dim="'+esc(l.dim)+'"><span class="ladn" style="background:'+l.hue+'">'+l.n+'</span>'+
    '<div class="ladtx"><div class="ladlabel">'+esc(l.label)+' <span class="laddim" style="color:'+l.hue+'">'+esc(l.dim)+'</span></div>'+
    (l.note?'<div class="ladnote">'+esc(l.note)+'</div>':'')+'</div></div>').join('');
  const up=(g.ladder_up||[]).map(x=>'<span class="rup">'+esc(x)+'</span>').join('<span class="rarr">→</span>');
  return (g.ladder_intro?'<p class="ladintro">'+esc(g.ladder_intro)+'</p>':'')+'<div class="ladder2">'+steps+'</div>'+
    (up?'<div class="ladderup"><div class="cxlbl">Then turn — from 1 back up to 7</div>'+up+'</div>':''); }
function onionSelect(scope,name){ if(!name) return;
  scope.querySelectorAll('.onlayer,.onionlegitem,.ladrow').forEach(el=>el.classList.toggle('sel',el.dataset.dim===name));
  const on=scope.querySelector('.onion'); if(on) on.classList.add('picked');
  const acc=scope.querySelector('.dimacc[data-dim="'+name+'"]');
  if(acc){ acc.classList.add('open'); acc.scrollIntoView({block:'center',behavior:'smooth'}); }
  const cap=scope.querySelector('#onioncap'); if(cap) cap.innerHTML='<b style="color:'+(DIMHUE[name]||'#c07ad9')+'">'+esc(name)+'</b> — '+esc(_LAYERSUB[name]||''); }

const CATCHQ={Physical:'How is it broken physically?',Emotional:'How is it broken emotionally?',Mental:'How is it broken mentally?',Ambitional:'How is it broken in ambition?',Vocal:'How is it broken in speech?',Intentional:'How is it broken in the will?',Spiritual:'How is it broken spiritually?'};
function _stageFor(name){ if(!_curCmd||!_curCmd.repentance) return null; return (_curCmd.repentance.stages||[]).find(s=>s.dimension===name)||null; }
function repStageHtml(st){ if(!st) return '';
  const sc=(st.scriptures||[]).map(r=>linkifyScripture(r)).join(' · ');
  return '<div class="repdim"><button class="repdimhdr">🕊 Repentance in this dimension <span class="dimcar">▸</span></button><div class="repdimbody">'+
    '<div class="repline"><b>Catch it here:</b> '+esc(st.catch||'')+'</div>'+
    '<div class="repline"><b>Confess it:</b> '+esc(st.confess||'')+'</div>'+
    '<div class="repline"><b>Turn:</b> '+esc(st.turn||'')+'</div>'+
    '<div class="repline"><b>Seek counsel:</b> '+esc(st.seek||'')+'</div>'+
    (st.walk?'<div class="repline"><b>Walk differently:</b> '+linkifyScripture(st.walk)+'</div>':'')+
    (sc?'<div class="cxrefs"><span class="cxrl">Scriptures</span>'+sc+'</div>':'')+'</div></div>'; }

function renderDim(d){ const hue=DIMHUE[d.name]||'#9a86e6';
  const ex=(d.examples||[]).map(x=>'<li>'+linkifyScripture(x)+'</li>').join('');
  return '<div class="dimacc" data-dim="'+esc(d.name)+'"><button class="dimhdr"><span class="dimdot" style="background:'+hue+'"></span>'+
    '<span class="dimname">'+esc((d.marker?d.marker+' ':'')+d.name)+'</span><span class="dimsub">'+esc(d.subtitle||'')+'</span>'+
    (ex?'<span class="dimcount">'+d.examples.length+'</span>':'')+'<span class="dimcar">▸</span></button>'+
    '<div class="dimbody">'+(d.q?'<div class="dimq">'+esc(d.q||CATCHQ[d.name]||'')+'</div>':'')+renderBlocks(d.blocks)+
    (ex?'<div class="cxlbl">Examples of violation</div><ul class="cxlist">'+ex+'</ul>':'')+renderBlocks(d.after)+
    (d.keeping?'<div class="keepbox"><b>How to keep it here:</b> '+linkifyScripture(d.keeping)+'</div>':'')+
    repStageHtml(_stageFor(d.name))+'</div></div>'; }

function renderSection(s){
  if(s.kind==='dimensions'){ const dims=(s.dims||[]).map(renderDim).join('');
    return '<div class="cmdsec cmddims"><div class="cmdeye">'+esc(s.title||'')+'</div>'+(s.q?'<h3>'+esc(s.q)+'</h3>':'')+
      renderOnion(s.dims)+'<div class="dimhint">tap a dimension to open it</div>'+renderBlocks(s.blocks)+dims+'</div>'; }
  if(s.kind==='insight') return '<div class="cmdsec cmdinsight"><div class="cmdeye">Insight</div><h3>'+esc(s.title||'')+'</h3>'+renderBlocks(s.blocks)+'</div>';
  if(s.kind==='pray') return '<div class="cmdsec cmdprayer"><div class="cmdeye">'+esc(s.title||'')+'</div>'+(s.q?'<h3>'+esc(s.q)+'</h3>':'')+renderBlocks(s.blocks)+
    '<div class="prayacts"><button class="seekcounsel">🕊 Seek Counsel in Prayer</button><button class="lordsprayer'+(_lordsSeen?'':' pulse')+'">📖 Read the Full Lord\'s Prayer — KJV</button></div></div>';
  const cls={define:'cmddefine',keep:'cmdkeep',tempted:'cmdtempt'}[s.kind]||'';
  return '<div class="cmdsec '+cls+'"><div class="cmdeye">'+esc(s.title||'')+'</div>'+(s.q?'<h3>'+esc(s.q)+'</h3>':'')+renderBlocks(s.blocks)+'</div>'; }

function renderRepentanceSection(t){ if(!t.repentance) return ''; const g=REPENT||{};
  const stages=(t.repentance.stages||[]).map(st=>{ const hue=DIMHUE[st.dimension]||'#9a86e6';
    const warn=(st.warningSigns||[]).map(w=>'<li>'+linkifyScripture(w)+'</li>').join('');
    const sc=(st.scriptures||[]).map(r=>linkifyScripture(r)).join(' · ');
    return '<div class="repstage"><div class="repsttl"><span class="dimdot" style="background:'+hue+'"></span>'+esc((st.marker?st.marker+' ':'')+st.dimension)+' <span class="repstsub">'+esc(st.subtitle||'')+'</span></div>'+
      (warn?'<div class="cxlbl">Warning signs</div><ul class="cxlist">'+warn+'</ul>':'')+
      '<div class="repline"><b>Catch it here:</b> '+esc(st.catch||'')+'</div><div class="repline"><b>Confess it:</b> '+esc(st.confess||'')+'</div>'+
      '<div class="repline"><b>Turn:</b> '+esc(st.turn||'')+'</div><div class="repline"><b>Seek counsel:</b> '+esc(st.seek||'')+'</div>'+
      (st.walk?'<div class="keepbox"><b>Walk differently:</b> '+linkifyScripture(st.walk)+'</div>':'')+
      (sc?'<div class="cxrefs"><span class="cxrl">Scriptures</span>'+sc+'</div>':'')+'</div>'; }).join('');
  return '<div class="cmdsec cmdrepent"><div class="cmdeye">Repentance</div><h3>How do you turn from this, and turn early?</h3>'+
    '<p>'+esc(t.repentance.intro||'')+'</p>'+
    renderLadder(g)+
    stages+
    '<div class="prayacts"><button class="seekcounsel">🕊 Seek Counsel in Prayer</button><button class="lordsprayer'+(_lordsSeen?'':' pulse')+'">📖 Read the Full Lord\'s Prayer — KJV</button></div></div>'; }

/* ---------- screens ---------- */
function setView(html){ const v=$('#view'); v.innerHTML=html; v.scrollTop=0; }
function wireStudy(scope){ if(!scope) return;
  scope.querySelectorAll('.dimacc .dimhdr').forEach(h=>h.onclick=()=>h.parentElement.classList.toggle('open'));
  scope.querySelectorAll('.repdim .repdimhdr').forEach(h=>h.onclick=e=>{e.stopPropagation();h.parentElement.classList.toggle('open');});
  scope.querySelectorAll('.onlayer,.onionlegitem,.ladrow').forEach(el=>el.onclick=()=>onionSelect(scope,el.dataset.dim));
  scope.querySelectorAll('.seekcounsel').forEach(b=>b.onclick=seekCounsel);
  scope.querySelectorAll('.lordsprayer').forEach(b=>b.onclick=openLordsPrayer);
  scope.querySelectorAll('.backbtn').forEach(b=>b.onclick=()=>nav(b.dataset.back||'home'));
  wireScref(scope); }

const QUOTES=[
  ['In the beginning was the Word, and the Word was with God, and the Word was God.','John 1:1'],
  ['Thou shalt love the Lord thy God with all thy heart, and with all thy soul, and with all thy mind.','Matthew 22:37'],
  ['Trust in the LORD with all thine heart; and lean not unto thine own understanding.','Proverbs 3:5'],
  ['Seek ye first the kingdom of God, and his righteousness.','Matthew 6:33'],
  ['Nevertheless not my will, but thine, be done.','Luke 22:42'],
  ['He created it not in vain, he formed it to be inhabited.','Isaiah 45:18']];
let _qi=0, _qTimer=null;
function showHome(){ _qi=Math.floor(Math.random()*QUOTES.length);
  setView('<div class="screen home">'+
    '<div class="heb" style="font:700 22px \'Cormorant Garamond\',serif">א &nbsp; ת</div>'+
    '<div class="big"><span class="yb">YahBible</span></div>'+
    '<div class="quote" id="homeq"></div><div class="qref" id="homeqr"></div>'+
    '<div class="cta">'+
      '<button class="homebtn" data-go="commandments"><span class="hi">📜</span><span>The Ten Commandments<span class="hs">study each as a question, in seven dimensions</span></span></button>'+
      '<button class="homebtn" data-go="repentance"><span class="hi">🕊</span><span>Repentance<span class="hs">turn toward the Father, and turn early</span></span></button>'+
      '<button class="homebtn" data-go="news"><span class="hi">✨</span><span>What\'s New<span class="hs">v'+esc(NEWS.version||'')+'</span></span></button>'+
    '</div></div>');
  $('#view').querySelectorAll('.homebtn').forEach(b=>b.onclick=()=>nav(b.dataset.go));
  rotQuote(); clearInterval(_qTimer); _qTimer=setInterval(rotQuote,7000); }
function rotQuote(){ const q=$('#homeq'), r=$('#homeqr'); if(!q) return; const [txt,ref]=QUOTES[_qi%QUOTES.length];
  q.style.opacity=0; setTimeout(()=>{ q.textContent='“'+txt+'”'; r.textContent=ref; q.style.transition='opacity .5s'; q.style.opacity=1; },250); _qi++; }

function showCommandments(){ clearInterval(_qTimer);
  setView('<div class="screen"><div class="navcards">'+
    '<button class="navcard news" data-go="news"><span class="ni">✨</span>News</button>'+
    '<button class="navcard rep" data-go="repentance"><span class="ni">🕊</span>Repentance</button></div>'+
    '<div class="listhdr">The Ten Commandments</div>'+
    CMDS.map(t=>'<button class="cmdrow" data-c="'+t.n+'"><span class="num">'+t.n+'</span><span class="ct">'+esc(t.cmd)+'</span></button>').join('')+
    '</div>');
  $('#view').querySelectorAll('.cmdrow').forEach(b=>b.onclick=()=>openCommandment(+b.dataset.c));
  $('#view').querySelectorAll('.navcard').forEach(b=>b.onclick=()=>nav(b.dataset.go)); }

function openCommandment(n){ const t=CMDS.find(x=>x.n===n); if(!t) return; _curCmd=t;
  let secs='', injected=false;
  (t.sections||[]).forEach(s=>{ if(s.kind==='tempted'&&!injected){ secs+=renderRepentanceSection(t); injected=true; } secs+=renderSection(s); });
  if(!injected) secs+=renderRepentanceSection(t);
  setView('<div class="screen study"><button class="backbtn" data-back="commandments">◀ the ten commandments</button>'+
    '<div class="cmdno">Commandment '+t.n+' of Ten</div><h2 class="cmdttl">'+esc(t.cmd)+'</h2>'+
    ((t.verse||t.full)?'<div class="cmdfull">&ldquo;'+esc(t.verse||t.full)+'&rdquo;<span class="cmdref">'+esc(t.ref||'')+'</span></div>':'')+secs+'</div>');
  wireStudy($('#view')); }

function openRepentance(){ _curCmd=null; clearInterval(_qTimer); const g=REPENT||{};
  const ov=(g.overview||[]).map(b=> b.t==='contrast'
      ? '<div class="repcontrast"><div class="rc rcr">'+esc(b.regret||'')+'</div><div class="rc rcp">'+esc(b.repent||'')+'</div></div>'
      : '<p>'+allowBold(linkifyScripture(b.text||''))+'</p>').join('');
  const el=(g.elements||[]).map(x=>'<span class="repel">'+esc(x)+'</span>').join('');
  const qs=(g.questions||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
  const csteps=(g.counsel_steps||[]).map(s=>'<div class="counselstep"><div class="csnum">'+s.n+'</div><div class="csbody">'+
    '<div class="csttl">'+esc(s.title)+'</div>'+(s.subtitle?'<div class="cssub">'+esc(s.subtitle)+'</div>':'')+renderBlocks(s.blocks)+'</div></div>').join('');
  setView('<div class="screen study"><button class="backbtn" data-back="commandments">◀ back</button>'+
    '<div class="cmdno">A Foundational Discipline</div><h2 class="cmdttl">'+esc(g.title||'Repentance')+'</h2>'+
    (g.subtitle?'<div class="repsubtitle">'+esc(g.subtitle)+'</div>':'')+
    (g.epigraph?'<div class="repepigraph">&ldquo;'+linkifyScripture(g.epigraph.quote||'')+'&rdquo;<span class="cscrref">'+linkifyScripture(g.epigraph.ref||'')+'</span></div>':'')+
    '<div class="cmdsec cmddefine"><div class="cmdeye">What it is</div><h3>What is repentance?</h3>'+ov+
      (el?'<div class="cxlbl">Repentance includes</div><div class="repels">'+el+'</div>':'')+'</div>'+
    '<div class="cmdsec cmddims"><div class="cmdeye">Where sin forms</div><h3>See the layer where it begins</h3>'+renderOnion(null)+'</div>'+
    '<div class="cmdsec cmdrepent"><div class="cmdeye">Catching it earlier</div><h3>The inward ladder — a countdown, 7 to 1</h3>'+renderLadder(g)+
      (qs?'<div class="cxlbl">Ask yourself</div><ul class="cxlist">'+qs+'</ul>':'')+'</div>'+
    (csteps?'<div class="cmdsec cmdcounsel"><div class="cmdeye">Spiritual alignment</div><h3>'+esc(g.counsel_title||"Seeking the Father's Counsel")+'</h3>'+
      (g.counsel_lead?'<div class="cscr">&ldquo;'+linkifyScripture(g.counsel_lead)+'&rdquo;<span class="cscrref">'+linkifyScripture(g.counsel_lead_ref||'')+'</span></div>':'')+csteps+'</div>':'')+
    '<div class="cmdsec cmdprayer"><div class="cmdeye">Prayer</div><h3>How should you pray?</h3><div class="prayacts"><button class="seekcounsel">🕊 Seek Counsel in Prayer</button><button class="lordsprayer'+(_lordsSeen?'':' pulse')+'">📖 Read the Full Lord\'s Prayer — KJV</button></div>'+
      (g.prayer_refs?'<div class="cxrefs"><span class="cxrl">Suggested Scriptures</span>'+linkifyScripture(g.prayer_refs)+'</div>':'')+'</div></div>');
  wireStudy($('#view')); }

function openNews(){ clearInterval(_qTimer); markNewsSeen();
  const cats={feature:'#5fd39a',repentance:'#c07ad9',scripture:'#59b8ff',content:'#e8912e',ui:'#e7c94e',performance:'#9a86e6',bugfix:'#e0563b'};
  const items=(NEWS.entries||[]).map(e=>{ const col=cats[e.category]||'#9a86e6';
    const link=e.deepLink?'<button class="newsgo" data-link="'+esc(e.deepLink)+'">Explore →</button>':'';
    return '<div class="newsentry"><div class="newshdr"><span class="newsic">'+(e.icon||'✨')+'</span><div><div class="newstitle">'+esc(e.title)+'</div>'+
      '<div class="newsmeta"><span class="newscat" style="color:'+col+';border-color:'+col+'">'+esc(e.category||'')+'</span> '+esc(e.date||'')+'</div></div></div><p>'+esc(e.summary||'')+'</p>'+link+'</div>'; }).join('');
  setView('<div class="screen study"><button class="backbtn" data-back="commandments">◀ back</button>'+
    '<div class="cmdno">Release Notes & Guided Tour</div><h2 class="cmdttl">News & Updates</h2>'+
    '<div class="cmdfull">What\'s new · v'+esc(NEWS.version||'')+'</div>'+(items||'<p>No updates yet.</p>')+'</div>');
  $('#view').querySelectorAll('.backbtn').forEach(b=>b.onclick=()=>nav('commandments'));
  $('#view').querySelectorAll('.newsgo').forEach(b=>b.onclick=()=>{ const l=b.dataset.link;
    if(l==='repentance') nav('repentance'); else if(l&&l.indexOf('cmd:')===0){ nav('commandments'); openCommandment(+l.slice(4)); } }); }

/* ---------- Bible reader (offline KJV) ---------- */
let _rd={bi:42,ch:1};
function bookGrid(list){ return '<div class="bookgrid">'+list.map(b=>{ const i=KJV.books.indexOf(b);
  return '<button class="bookcell" data-bi="'+i+'">'+esc(b.n)+'</button>'; }).join('')+'</div>'; }
function openBible(){ clearInterval(_qTimer);
  const ot=KJV.books.filter(b=>b.t==='OT'), nt=KJV.books.filter(b=>b.t==='NT');
  setView('<div class="screen"><div class="listhdr">Holy Bible · KJV</div>'+
    '<div class="testlbl">Old Testament</div>'+bookGrid(ot)+
    '<div class="testlbl">New Testament</div>'+bookGrid(nt)+'</div>');
  $('#view').querySelectorAll('.bookcell').forEach(b=>b.onclick=()=>openBook(+b.dataset.bi)); }
function openBook(bi){ const b=KJV.books[bi]; if(!b) return; _rd.bi=bi;
  const chs=b.ch.map((_,i)=>'<button class="chcell" data-ch="'+(i+1)+'">'+(i+1)+'</button>').join('');
  setView('<div class="screen"><button class="backbtn" id="bkback">◀ books</button>'+
    '<h2 class="cmdttl" style="margin:8px 0 4px">'+esc(b.n)+'</h2><div class="cmdno">choose a chapter</div>'+
    '<div class="chgrid">'+chs+'</div></div>');
  $('#bkback').onclick=openBible;
  $('#view').querySelectorAll('.chcell').forEach(c=>c.onclick=()=>openReader(bi,+c.dataset.ch)); }
function openReader(bi,ch,verse){ const b=KJV.books[bi]; if(!b) return; _tab='bible';
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x.dataset.tab==='bible'));
  ch=Math.max(1,Math.min(b.ch.length,ch||1)); _rd={bi:bi,ch:ch};
  const verses=b.ch[ch-1]||[];
  const body=verses.map((tx,i)=>'<p class="rv'+(verse===i+1?' hl':'')+'" id="rv'+(i+1)+'"><span class="rvn">'+(i+1)+'</span>'+wordize(tx,i+1)+'<span class="ilslot" id="il'+(i+1)+'"></span></p>').join('');
  const prev=ch>1, next=ch<b.ch.length;
  setView('<div class="screen reader"><div class="rdbar"><button class="backbtn" id="rdbooks">📚 '+esc(b.a)+'</button>'+
    '<div class="rdttlwrap"><span class="rdttl">'+esc(b.n)+' '+ch+'</span>'+
      '<span class="ileye" id="ilbtn" title="Show the Hebrew/Greek under each verse">&#128065;</span>'+
      '<span class="treeeye" id="verbtn" title="Compare versions under each verse"><svg viewBox="0 0 24 24"><path d="M12 2 L16 10 L14 10 L18 16 L13 16 L13 21 L11 21 L11 16 L6 16 L10 10 L8 10 Z"/></svg></span></div>'+
    '<div class="rdswipehint">swipe ← → for chapters</div></div>'+
    '<div class="rdbody" id="rdbody">'+body+'</div></div>');
  $('#rdbooks').onclick=()=>openBook(bi);
  const go=d=>{ const t=ch+d; if(t>=1&&t<=b.ch.length) openReader(bi,t); };
  // WORD tap -> word study (desktop-style); tapping a verse number selects the verse
  $('#view').querySelectorAll('.rvn').forEach((n)=>n.onclick=e=>{e.stopPropagation();selectVerse(bi,ch,+n.parentElement.id.slice(2));});
  $('#view').querySelectorAll('.rw').forEach((w)=>w.onclick=e=>{e.stopPropagation();tapWord(b,ch,+w.dataset.v,w.textContent,w);});
  $('#ilbtn').onclick=()=>toggleChapterInterlinear(b,ch);
  $('#verbtn').onclick=()=>toggleChapterVersions(b,ch);
  initSwipe($('#rdbody'),go);
  _rd={bi:bi,ch:ch}; _ilOn=false; _verOn=false;
  colorOriginals(b,ch);   // highlight which words have an original (desktop-style), if the pack is here
  if(verse){ const el=$('#rv'+verse); if(el) setTimeout(()=>el.scrollIntoView({block:'center'}),60); }
}
function wordize(tx,v){ return tx.split(/(\s+)/).map(t=>/[A-Za-z]/.test(t)
  ? '<span class="rw" data-v="'+v+'">'+esc(t)+'</span>' : esc(t)).join(''); }
/* left/right swipe to change chapters */
function initSwipe(el,go){ if(!el) return; let x0=null,y0=null;
  el.addEventListener('touchstart',e=>{ if(e.touches.length!==1){x0=null;return;} x0=e.touches[0].clientX; y0=e.touches[0].clientY; },{passive:true});
  el.addEventListener('touchend',e=>{ if(x0==null) return; const t=e.changedTouches[0];
    const dx=t.clientX-x0, dy=t.clientY-y0;
    if(Math.abs(dx)>60 && Math.abs(dx)>Math.abs(dy)*1.6){ go(dx<0?1:-1); } x0=null; },{passive:true}); }
/* colour the words that have a real original in this verse (needs the word-study pack) */
async function colorOriginals(b,ch){
  if(!(window.YBPacks && await YBPacks.have('ws:'+b.a).catch(()=>false))) return;
  try{ const ws=await YBPacks.ensureBookWords(b.a);
    const verses=b.ch[ch-1]||[];
    for(let i=1;i<=verses.length;i++){ const toks=(((ws||{})[String(ch)]||{})[String(i)])||[];
      const origSet=new Set(); toks.forEach(t=>{ (t.e||'').toLowerCase().split(/\s+/).forEach(w=>{const c=w.replace(/[^a-z]/g,''); if(c.length>1)origSet.add(c);}); });
      const p=$('#rv'+i); if(!p) continue;
      p.querySelectorAll('.rw').forEach(w=>{ const c=w.textContent.toLowerCase().replace(/[^a-z]/g,'');
        if(origSet.has(c)||[...origSet].some(o=>o.indexOf(c)>=0||c.indexOf(o)>=0)) w.classList.add('hasorig'); });
    }
  }catch(e){}
}
async function tapWord(b,ch,v,word,el){ _sel={bi:KJV.books.indexOf(b),ch:ch,v:v};
  document.querySelectorAll('.rw.sel').forEach(x=>x.classList.remove('sel')); if(el)el.classList.add('sel');
  openDrawer('right');
  // after the drawer builds, run the word's study
  setTimeout(()=>{ if(window.YBPacks) YBPacks.have('ws:'+b.a).then(h=>{ if(h) showWordPack(word,b,ch,v); }); },250);
}
/* chapter-level interlinear: show the Hebrew/Greek + Strong's + English under each verse (desktop-style) */
let _ilOn=false;
async function toggleChapterInterlinear(b,ch){
  const btn=$('#ilbtn');
  if(_ilOn){ _ilOn=false; document.querySelectorAll('.ilslot').forEach(s=>s.innerHTML=''); if(btn)btn.classList.remove('on'); return; }
  if(!(window.YBPacks && await YBPacks.have('ws:'+b.a).catch(()=>false))){
    toast('Download the word‑study pack to see the original here'); connectPrompt(); return; }
  _ilOn=true; if(btn){btn.classList.add('on','loading');}
  try{
    const ws=await YBPacks.ensureBookWords(b.a); const S=await YBPacks.ensureStrongs().catch(()=>({}));
    const verses=b.ch[ch-1]||[];
    for(let i=1;i<=verses.length;i++){
      const toks=(((ws||{})[String(ch)]||{})[String(i)])||[];
      const slot=$('#il'+i); if(!slot) continue;
      slot.innerHTML = toks.length? '<span class="illine">'+toks.map(t=>{
        const def=strongLook(S,t.s); const dshort=def.split('—').pop().trim().slice(0,40);
        return '<span class="iltok" data-s="'+esc(t.s||'')+'" data-v="'+i+'" data-o="'+esc(t.o||'')+'"><span class="ilo">'+esc(t.o||'')+'</span>'+
          '<span class="ile">'+esc(t.e||'')+'</span><span class="ils">'+esc(t.s||'')+'</span>'+
          (dshort?'<span class="ild">'+esc(dshort)+'</span>':'')+'</span>';
      }).join('')+'</span>' : '';
    }
    // clicking a Hebrew/Greek word opens the RIGHT drawer with its full breakdown (desktop-style)
    document.querySelectorAll('.iltok').forEach(x=>x.onclick=e=>{ e.stopPropagation();
      _sel={bi:KJV.books.indexOf(b),ch:ch,v:+x.dataset.v};
      openDrawer('right');
      setTimeout(()=>showStrongDef(x.dataset.s, x.dataset.o), 220); });
    if(btn)btn.classList.remove('loading');
  }catch(e){ _ilOn=false; if(btn){btn.classList.remove('on','loading');} toast('could not load originals'); }
}
function showStrongDefToast(sid,glyph,S){ const def=strongLook(S,sid); toast(glyph+' · '+sid+(def?' — '+def.split('—').pop().trim().slice(0,60):'')); }
/* chapter-level version comparison: stack the user's favourite versions under each verse (tree, desktop-style) */
let _verOn=false;
function favVersions(){ try{ return JSON.parse(localStorage.getItem('yb_fav_versions')||'null')||['akjv','asv','BSB','basicenglish']; }catch(e){ return ['akjv','asv','BSB','basicenglish']; } }
async function toggleChapterVersions(b,ch){
  const btn=$('#verbtn');
  if(_verOn){ _verOn=false; document.querySelectorAll('.ilslot').forEach(s=>s.innerHTML=''); if(btn)btn.classList.remove('on'); return; }
  if(!(window.YBPacks && await YBPacks.have('ver:'+b.a).catch(()=>false))){
    toast('Download the versions pack to compare here'); connectPrompt(); return; }
  _verOn=true; if(btn)btn.classList.add('on');
  try{
    const data=await YBPacks.ensureBookVersions(b.a); const favs=favVersions();
    const lc={}; Object.keys(data||{}).forEach(k=>lc[k.toLowerCase()]=k);
    const verses=b.ch[ch-1]||[];
    for(let i=1;i<=verses.length;i++){ const slot=$('#il'+i); if(!slot) continue;
      slot.innerHTML='<span class="verstack">'+favs.map(vc=>{ const key=data[vc]?vc:lc[vc.toLowerCase()]; if(!key) return '';
        const t=(((data[key]||{})[String(ch)]||{})[String(i)])||''; if(!t) return '';
        return '<span class="vsrow"><span class="vscode">'+esc(vc)+'</span><span class="vstx">'+esc(t)+'</span></span>'; }).filter(Boolean).join('')+'</span>';
    }
  }catch(e){ _verOn=false; if(btn)btn.classList.remove('on'); toast('could not load versions'); }
}
let _sel=null;   // {bi,ch,v}
function selectVerse(bi,ch,v){ _sel={bi:bi,ch:ch,v:v};
  document.querySelectorAll('.rv.hl').forEach(x=>x.classList.remove('hl'));
  const el=$('#rv'+v); if(el)el.classList.add('hl');
  openStudy();
}

function seekCounsel(){ const g=REPENT||{};
  const steps=(g.counsel_flow||[]).map((x,i)=>'<li><span class="scn">'+(i+1)+'</span>'+esc(x)+'</li>').join('');
  const ov=document.createElement('div'); ov.className='scoverlay'; ov.id='scoverlay';
  ov.innerHTML='<div class="scpanel"><button class="scclose">✕</button><div class="cmdeye">🕊 A quiet way to pray</div><h3 style="font:600 22px \'Cormorant Garamond\',serif;color:var(--gold);margin:2px 0 8px">Seek Counsel in Prayer</h3>'+
    '<p class="scintro">Enter privately, as Yeshua taught. This is a path, not a script to repeat.</p><ol class="scflow">'+steps+'</ol>'+
    (g.counsel_note?'<div class="scnote">'+linkifyScripture(g.counsel_note)+'</div>':'')+
    '<button class="lordsprayer'+(_lordsSeen?'':' pulse')+'">📖 Read the Full Lord\'s Prayer — KJV</button></div>';
  document.body.appendChild(ov);
  $('.scclose',ov).onclick=()=>ov.remove(); ov.onclick=e=>{ if(e.target===ov) ov.remove(); };
  $('.lordsprayer',ov).onclick=()=>{ ov.remove(); openLordsPrayer(); }; wireScref(ov); }
function openLordsPrayer(){ _lordsSeen=true; document.querySelectorAll('.lordsprayer').forEach(b=>b.classList.remove('pulse'));
  const sc=document.querySelector('#scoverlay'); if(sc) sc.remove();
  const bi=resolveBook('Matthew'); if(bi>=0) openReader(bi,6,9); else toast('Matthew 6:9'); }

/* ---------- news pulse (per-version, localStorage) ---------- */
function newsUnseen(){ try{ return NEWS.version && localStorage.getItem('yb_news_seen')!==NEWS.version; }catch(e){ return false; } }
function markNewsSeen(){ try{ localStorage.setItem('yb_news_seen',NEWS.version); }catch(e){} const d=$('#newsdot'); if(d) d.remove(); }

/* ---------- tab navigation ---------- */
function nav(tab){ _tab=tab; try{ window.__tab=tab; }catch(e){}
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on', b.dataset.tab===tab || (tab==='repentance'&&b.dataset.tab==='repent')));
  // the left/right menu buttons appear in the Bible section (sources + verse study), like desktop
  const inBible=(tab==='bible');
  const lb=$('#leftmenubtn'), rb=$('#rightmenubtn'); if(lb)lb.hidden=!inBible; if(rb)rb.hidden=!inBible;
  closeDrawers();
  if(tab==='home') showHome();
  else if(tab==='bible') openBible();
  else if(tab==='commandments') showCommandments();
  else if(tab==='repentance'||tab==='repent') openRepentance();
  else if(tab==='news') openNews(); }

/* ================= DRAWERS (left = sources, right = verse study) — mirrors desktop ================= */
const DESK_KEY='yb_desktop_url';
function deskUrl(){ try{ return localStorage.getItem(DESK_KEY)||''; }catch(e){ return ''; } }
function closeDrawers(){ ['#leftdrawer','#rightdrawer','#scrim'].forEach(s=>{const e=$(s);if(e)e.hidden=true;}); }
function openDrawer(side){ const d=$(side==='left'?'#leftdrawer':'#rightdrawer'); const other=$(side==='left'?'#rightdrawer':'#leftdrawer');
  if(other)other.hidden=true; $('#scrim').hidden=false;
  if(side==='left') buildSources(); else buildStudy();
  d.hidden=false; }
/* LEFT drawer — the sources menu (all the sacred books), grouped like the desktop left menu */
const SRC_LOCKED=[
  {t:'Beyond the KJV — on your desktop',items:[
    ['📜','Ethiopian Apocrypha'],['🔴','Red Letter Words of Christ'],
    ['🕮','1 Enoch (Ethiopic)'],['🕮','2 Enoch (Slavonic)'],['🕮','3 Enoch (Hebrew)'],
    ['✶','The Nag Hammadi Library'],['✶','Pistis Sophia'],['✶','The Gnostic Bible'],
    ['🏛','Second Temple & Apocrypha'],['🌐','120+ comparison versions'],
    ['א','Hebrew / Greek / Aramaic word study'],['🔢',"Strong's + interlinear"]]},
];
function buildSources(){ const d=$('#leftdrawer');
  const ot=KJV.books.filter(b=>b.t==='OT'), nt=KJV.books.filter(b=>b.t==='NT');
  const grp=(lbl,list)=>'<div class="srcgroup"><div class="srclbl">'+esc(lbl)+'</div>'+
    list.map(b=>{const i=KJV.books.indexOf(b);return '<button class="srcitem" data-bi="'+i+'"><span class="si">📖</span>'+esc(b.n)+'</button>';}).join('')+'</div>';
  d.innerHTML='<div class="drawhdr"><span class="dt">Holy Bible &middot; Sources</span><button class="drawx" id="ldx">✕</button></div>'+
    '<button class="srcitem" id="lsettings" style="border-color:rgba(233,200,119,.4)"><span class="si">⚙️</span>Settings &amp; Downloads</button>'+
    grp('Old Testament',ot)+grp('New Testament',nt)+
    '<div class="srcgroup"><div class="srclbl">More sacred books</div><div id="srcextra"><div class="srcnote">loading sources…</div></div></div>';
  $('#ldx',d).onclick=closeDrawers;
  d.querySelectorAll('.srcitem[data-bi]').forEach(b=>b.onclick=()=>{closeDrawers();openBook(+b.dataset.bi);});
  $('#lsettings',d).onclick=()=>{closeDrawers();openSettings();};
  // populate the extra sources (downloadable, then openable)
  if(window.YBPacks){ YBPacks.sourcesIndex().then(async(list)=>{ const box=$('#srcextra'); if(!box) return;
    if(!list.length){ box.innerHTML='<div class="srcnote">Connect to the internet once to list the extra sources.</div>'; return; }
    const rows=await Promise.all(list.map(async s=>{ const got=await YBPacks.have('src:'+s.id).catch(()=>false);
      return '<button class="srcitem'+(got?'':' dl')+'" data-src="'+esc(s.id)+'"><span class="si">'+(got?'📖':'⬇')+'</span>'+esc(s.name)+
        '<span class="srcsz">'+(got?'':fmtMB(s.size||0))+'</span></button>'; }));
    box.innerHTML=rows.join('');
    box.querySelectorAll('.srcitem[data-src]').forEach(b=>b.onclick=()=>openSource(b.dataset.src, b));
  }).catch(()=>{ const box=$('#srcextra'); if(box) box.innerHTML='<div class="srcnote">could not list sources</div>'; }); }
}
let _srcCache={};
async function openSource(id, btn){
  if(btn){ btn.disabled=true; const si=btn.querySelector('.si'); if(si&&si.textContent==='⬇') si.textContent='…'; }
  let data=_srcCache[id];
  try{ if(!data){ data=await YBPacks.ensureSource(id); _srcCache[id]=data; } }
  catch(e){ toast('Download needs internet'); if(btn)btn.disabled=false; return; }
  closeDrawers();
  const books=Object.keys(data||{});
  setView('<div class="screen"><button class="backbtn" id="srcback">◀ sources</button>'+
    '<div class="listhdr">'+esc(id.replace(/_/g,' '))+'</div>'+
    books.map((bk,i)=>'<button class="cmdrow" data-b="'+i+'"><span class="ct">'+esc(bk)+'</span></button>').join('')+'</div>');
  $('#srcback').onclick=()=>{nav('bible');};
  $('#view').querySelectorAll('.cmdrow').forEach(r=>r.onclick=()=>openSourceBook(id,books[+r.dataset.b]));
}
function openSourceBook(id,book){ const data=_srcCache[id]||{}; const units=data[book]||[];
  setView('<div class="screen reader"><div class="rdbar"><button class="backbtn" id="sbk">◀ '+esc(id.replace(/_/g,' '))+'</button><div class="rdttl">'+esc(book)+'</div><div></div></div>'+
    '<div class="rdbody">'+units.map(u=>'<p class="rv"><span class="rvn">'+esc(u[0]||'')+'</span>'+esc(u[1]||'')+'</p>').join('')+'</div></div>');
  $('#sbk').onclick=()=>openSource(id);
}
/* RIGHT drawer — verse study: the selected verse, its words, versions & original language */
async function buildStudy(){ const d=$('#rightdrawer');
  if(!_sel){ d.innerHTML='<div class="drawhdr"><span class="dt">Verse Study</span><button class="drawx" id="rdx">✕</button></div>'+
      '<div class="srcnote">Tap a verse in the reader to study it here — its words, cross‑references, other versions, and the original Hebrew or Greek.</div>';
    $('#rdx',d).onclick=closeDrawers; return; }
  const b=KJV.books[_sel.bi], v=_sel.v, txt=(b.ch[_sel.ch-1]||[])[v-1]||'';
  const ref=b.n+' '+_sel.ch+':'+v;
  const words=txt.replace(/[^A-Za-z' -]/g,' ').split(/\s+/).filter(w=>w.length>1)
    .map(w=>'<button class="wchip" data-w="'+esc(w)+'">'+esc(w)+'</button>').join('');
  // which packs are installed?
  const haveVer=window.YBPacks && await YBPacks.have('ver:'+b.a).catch(()=>false);
  const haveWs =window.YBPacks && await YBPacks.have('ws:'+b.a).catch(()=>false);
  d.innerHTML='<div class="drawhdr"><span class="dt">Verse Study</span><button class="drawx" id="rdx">✕</button></div>'+
    '<div class="vsref holo-gold">'+esc(ref)+'</div>'+
    '<div class="vstext">'+esc(txt)+'</div>'+
    '<div class="vstabs"><button class="vstab'+(haveVer?'':' locked')+'" data-x="versions">Compare versions</button>'+
      '<button class="vstab'+(haveWs?'':' locked')+'" data-x="orig">Original language</button>'+
      '<button class="vstab'+(haveWs?'':' locked')+'" data-x="inter">Interlinear</button></div>'+
    '<div id="vspanel"></div>'+
    '<div class="cxlbl">Words — tap for study</div><div class="wchips">'+words+'</div>'+
    (haveVer&&haveWs?'':'<div class="connectcard"><div class="cct">📦 Get more, offline</div><p>Download the versions &amp; word‑study packs to compare 120+ translations and see the Hebrew/Greek here — no connection needed.</p><button class="connectbtn" id="rconnect">Open Downloads</button></div>');
  $('#rdx',d).onclick=closeDrawers;
  const rc=$('#rconnect',d); if(rc) rc.onclick=()=>connectPrompt();
  d.querySelectorAll('.vstab').forEach(bt=>bt.onclick=()=>{ if(bt.classList.contains('locked')){connectPrompt();return;} showVsPanel(bt.dataset.x,b,_sel.ch,v); });
  d.querySelectorAll('.wchip').forEach(bt=>bt.onclick=()=>{ if(haveWs) showWordPack(bt.dataset.w,b,_sel.ch,v); else connectPrompt(); });
}
async function showVsPanel(kind,b,ch,v){ const el=$('#vspanel'); if(!el) return; el.innerHTML='<div class="srcnote">loading…</div>';
  try{
    if(kind==='versions'){
      const data=await YBPacks.ensureBookVersions(b.a);
      const rows=Object.keys(data||{}).sort().map(vc=>{ const t=(((data[vc]||{})[ch]||{})[v])||''; if(!t) return '';
        return '<div class="vrow"><span class="vcode">'+esc(vc)+'</span><span class="vtxt">'+esc(t)+'</span></div>'; }).filter(Boolean).join('');
      el.innerHTML='<div class="cxlbl">Across '+ (rows?Object.keys(data).length:0) +' versions</div><div class="vlist">'+(rows||'<div class="srcnote">no data for this verse</div>')+'</div>';
    }else{
      const ws=await YBPacks.ensureBookWords(b.a);
      const toks=(((ws||{})[ch]||{})[v])||[];
      if(kind==='orig'){
        el.innerHTML='<div class="cxlbl">Original — '+(toks.length)+' words</div><div class="origline">'+
          toks.map(t=>'<span class="origtok" data-s="'+esc(t.s||'')+'">'+esc(t.o||'')+'</span>').join(' ')+'</div>';
      }else{ // interlinear
        el.innerHTML='<div class="cxlbl">Interlinear</div><div class="interlist">'+
          toks.map(t=>'<div class="intok"><span class="io">'+esc(t.o||'')+'</span><span class="ie">'+esc(t.e||'')+'</span><span class="is">'+esc(t.s||'')+'</span></div>').join('')+'</div>';
      }
      el.querySelectorAll('.origtok').forEach(x=>x.onclick=()=>showStrongDef(x.dataset.s));
    }
  }catch(e){ el.innerHTML='<div class="srcnote">could not load — try Downloads</div>'; }
}
async function showWordPack(word,b,ch,v){ const el=$('#vspanel'); if(!el) return; el.innerHTML='<div class="srcnote">looking up…</div>';
  try{ const ws=await YBPacks.ensureBookWords(b.a); const toks=(((ws||{})[ch]||{})[v])||[];
    const wl=word.toLowerCase().replace(/[^a-z]/g,'');
    const m=toks.find(t=>(t.e||'').toLowerCase().replace(/[^a-z]/g,'')===wl)||toks.find(t=>((t.e||'').toLowerCase().indexOf(wl)>=0));
    if(!m){ el.innerHTML='<div class="srcnote">“'+esc(word)+'” is supplied in English here — no single original word.</div>'; return; }
    await showStrongDef(m.s, m.o);
  }catch(e){ el.innerHTML='<div class="srcnote">could not load — try Downloads</div>'; }
}
function strongLook(S,sid){ if(!S||!sid) return ''; if(S[sid]) return S[sid];
  const m=/^([HG])0*(\d+)$/.exec(sid); if(m){ const k=m[1]+m[2]; if(S[k]) return S[k]; } return ''; }
async function showStrongDef(sid, glyph){ const el=$('#vspanel'); if(!el||!sid) return;
  let def=''; try{ const S=await YBPacks.ensureStrongs(); def=strongLook(S,sid); }catch(e){}
  el.innerHTML='<div class="wsstudy"><div class="wsglyph holo-gold">'+esc(glyph||'')+'</div><div class="wssid">'+esc(sid)+'</div>'+
    '<div class="wsdef">'+esc(def||'(definition in the word‑study pack)')+'</div></div>';
}
function openStudy(){ openDrawer('right'); }
function askTaviel(){ toast('🕊 Ask Tav’iel — the grounded AI — is coming to mobile'); }

/* ============ UPDATES & DOWNLOADABLE PACKS ============ */
const APP_CONTENT_VER='2026.09.14';   // bundled study-content version
let MANIFEST=null;
function fmtMB(n){ if(!n) return ''; return (n/1048576).toFixed(n<10485760?1:0)+' MB'; }
async function checkUpdates(silent){
  if(!window.YBPacks) return;
  MANIFEST=await YBPacks.getManifest();
  if(!MANIFEST){ if(!silent) toast('No connection — updates need internet'); return; }
  // content self-update: if the hosted study content is newer, refresh it into IndexedDB + memory
  if(MANIFEST.contentVersion && MANIFEST.contentVersion>APP_CONTENT_VER){
    markContentUpdate(MANIFEST.contentVersion);
  }
  if(!silent) toast('Up to date · v'+(MANIFEST.contentVersion||APP_CONTENT_VER));
}
function markContentUpdate(v){ try{ localStorage.setItem('yb_update_avail',v); }catch(e){}
  const b=$('#settingsbtn'); if(b) b.classList.add('hasupd'); }
/* the "connect / get more" prompt now opens the Downloads screen */
function connectPrompt(){ closeDrawers(); openSettings(); }

async function openSettings(){ clearInterval(_qTimer);
  const packs=(MANIFEST&&MANIFEST.packs)||[
    {id:'versions',name:'All 120+ Bible versions',size:0,desc:'Compare every verse across 120+ translations, offline.'},
    {id:'wordstudy',name:'Offline word study',size:0,desc:"Hebrew/Greek originals, Strong's & interlinear for the scriptures."}];
  const upd=(function(){try{return localStorage.getItem('yb_update_avail');}catch(e){return null;}})();
  const rows=await Promise.all(packs.map(renderPackRow));
  const acct=getAccount();
  const acctCard = acct
    ? '<div class="cmdsec"><div class="cmdeye">Account</div><h3>Signed in</h3>'+
      '<div class="acctrow"><div class="acctav">'+esc((acct.name||acct.email||'Y')[0].toUpperCase())+'</div>'+
      '<div><div class="acctname">'+esc(acct.name||acct.email)+'</div><div class="acctsub">'+esc(acct.email||'on this device')+'</div></div>'+
      '<button id="signout" class="miniupd" style="margin-left:auto">Sign out</button></div></div>'
    : '<div class="cmdsec cmdlogin"><div class="cmdeye">Account</div><h3>Sign in or create an account</h3>'+
      '<p class="setnote">Your account (the Zion’iel Network) keeps your notes, bookmarks &amp; reading progress across your phone and desktop.</p>'+
      '<input id="lg_name" class="setinput" placeholder="Name or username" style="margin-bottom:8px">'+
      '<input id="lg_email" class="setinput" placeholder="Email (optional)" style="margin-bottom:8px">'+
      '<input id="lg_pw" class="setinput" type="password" placeholder="Password" style="margin-bottom:10px">'+
      '<div class="setrow"><button id="dosignin" class="connectbtn" style="width:auto;padding:10px 16px">Sign in</button>'+
      '<button id="doguest" class="miniupd">Continue as guest</button></div></div>';
  setView('<div class="screen study"><button class="backbtn" data-back="bible">◀ back</button>'+
    '<div class="cmdno">App</div><h2 class="cmdttl">Settings</h2>'+
    acctCard+
    (upd&&upd>APP_CONTENT_VER?'<div class="updbanner">✨ New study content available (v'+esc(upd)+'). <button id="applyupd" class="miniupd">Update now</button></div>':'')+
    '<div class="cmdsec"><div class="cmdeye">Add to the app</div><h3>Expanded, downloadable packs</h3>'+
    '<p class="setnote">These download once and then work offline. Big packs (like all 120+ versions) can be a couple of gigabytes — about the size of one mobile game.</p>'+
    rows.join('')+'</div>'+
    '<div class="cmdsec"><div class="cmdeye">Reading</div><h3>Favourite versions</h3>'+
    '<p class="setnote">Pick the translations to stack under each verse when you tap the tree 🌳 in a chapter.</p>'+
    '<div class="favver" id="favver">'+[['akjv','KJV'],['asv','ASV'],['BSB','BSB'],['basicenglish','BBE'],['ERV','ERV'],['GNV','Geneva'],['ylt','YLT'],['web','WEB'],['darby','Darby'],['aleppo','Aleppo (Heb)']].map(v=>'<button class="favchip'+(favVersions().indexOf(v[0])>=0?' on':'')+'" data-v="'+v[0]+'">'+v[1]+'</button>').join('')+'</div></div>'+
    '<div class="cmdsec"><div class="cmdeye">Beyond the packs</div><h3>Sync with your desktop</h3>'+
    '<p class="setnote">Enter your PC’s <b>network address</b> (not localhost) &mdash; e.g. <b>http://192.168.1.20:41537</b>. Your phone and PC must be on the same Wi‑Fi, and the desktop must have <b>Network / LAN mode</b> turned on (in the desktop app’s settings). <b>127.0.0.1 will not work</b> from a phone.</p>'+
    '<div class="setrow"><input id="deskurl" class="setinput" placeholder="http://192.168.x.x:41537" value="'+esc(deskUrl())+'"><button id="savedesk" class="connectbtn" style="width:auto;padding:9px 14px">Test &amp; save</button></div></div>'+
    '<div class="cmdsec"><div class="cmdeye">Version</div><p class="setnote">Study content v'+APP_CONTENT_VER+' · <button id="chkupd" class="miniupd">Check for updates</button></p></div>'+
    '<button class="cmdback" id="cmdback">◀ back</button></div>');
  $('#view').querySelectorAll('.backbtn,#cmdback').forEach(b=>b.onclick=()=>nav('bible'));
  const cu=$('#chkupd'); if(cu) cu.onclick=()=>checkUpdates(false).then(()=>openSettings());
  const au=$('#applyupd'); if(au) au.onclick=()=>applyContentUpdate();
  const sd=$('#savedesk'); if(sd) sd.onclick=async()=>{ const u=$('#deskurl').value.trim(); try{localStorage.setItem(DESK_KEY,u);}catch(e){}
    if(u){ toast('Testing connection…'); const ok=await pingDesktop(u); toast(ok?'✓ Connected to your desktop':'✗ Could not reach it — see the note below'); } };
  const si=$('#dosignin'); if(si) si.onclick=async()=>{ const n=$('#lg_name').value.trim(), e=$('#lg_email').value.trim(), pw=$('#lg_pw').value;
    if(!n&&!e){ toast('Enter a name or email'); return; }
    const u=deskUrl();
    if(u){ toast('Signing in to your desktop…'); const r=await desktopLogin(u,n||e,pw); if(r.ok){ setAccount({name:n||e,email:e,desktop:u,synced:true}); toast('✓ Signed in & synced'); openSettings(); return; }
      toast(r.error||'Desktop sign-in failed — signed in locally'); }
    setAccount({name:n,email:e}); openSettings(); };
  const gg=$('#doguest'); if(gg) gg.onclick=()=>{ setAccount({name:'Guest',guest:true}); openSettings(); };
  const so=$('#signout'); if(so) so.onclick=()=>{ setAccount(null); toast('Signed out'); openSettings(); };
  $('#view').querySelectorAll('#favver .favchip').forEach(ch=>ch.onclick=()=>{ let f=favVersions(); const v=ch.dataset.v;
    const i=f.indexOf(v); if(i>=0)f.splice(i,1); else f.push(v); try{localStorage.setItem('yb_fav_versions',JSON.stringify(f));}catch(e){} ch.classList.toggle('on'); });
  wirePackRows();
}
function normUrl(u){ u=(u||'').trim(); if(!u) return ''; if(!/^https?:\/\//.test(u)) u='http://'+u; return u.replace(/\/+$/,''); }
async function pingDesktop(u){ u=normUrl(u); try{ const r=await fetch(u+'/api/status',{cache:'no-store'}); return r.ok; }
  catch(e){ try{ const r2=await fetch(u+'/',{mode:'no-cors'}); return true; }catch(e2){ return false; } } }
async function desktopLogin(u,user,pw){ u=normUrl(u);
  try{ const r=await fetch(u+'/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pw})});
    const d=await r.json().catch(()=>({})); if(d&&d.ok!==false){ try{localStorage.setItem('yb_desk_token',d.token||d.session||'');}catch(e){} return {ok:true}; }
    // try signup if login failed
    const r2=await fetch(u+'/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pw,email:user.indexOf('@')>0?user:''})});
    const d2=await r2.json().catch(()=>({})); if(d2&&d2.ok!==false) return {ok:true};
    return {ok:false,error:(d2&&d2.error)||'sign-in failed'};
  }catch(e){ return {ok:false,error:'Could not reach the desktop — check the address & Wi-Fi'}; } }
function getAccount(){ try{ return JSON.parse(localStorage.getItem('yb_account')||'null'); }catch(e){ return null; } }
function setAccount(a){ try{ if(a) localStorage.setItem('yb_account',JSON.stringify(a)); else localStorage.removeItem('yb_account'); }catch(e){} }
async function renderPackRow(p){
  const key= p.id==='versions'?'ver:':'ws:';
  const ks=await YBPacks.storedKeys().catch(()=>[]);
  const got=ks.filter(k=>String(k).indexOf(key)===0).length;
  const total=(p.files&&p.files.length)|| (p.id==='versions'?66:66);
  const state= got>=total? 'Installed' : (got>0? got+' / '+total+' parts' : 'Not installed');
  const btn = got>=total? '<button class="packbtn done" data-pk="'+p.id+'">✓ Installed</button>'
    : '<button class="packbtn" data-pk="'+p.id+'">⬇ Download'+(p.size?(' · '+fmtMB(p.size)):'')+'</button>';
  return '<div class="packrow" id="pack-'+p.id+'"><div class="packmeta"><div class="packname">'+esc(p.name)+'</div>'+
    '<div class="packdesc">'+esc(p.desc||'')+'</div><div class="packstate" id="pkstate-'+p.id+'">'+state+'</div>'+
    '<div class="packbar" id="pkbar-'+p.id+'"><span></span></div></div>'+btn+'</div>';
}
function wirePackRows(){ $('#view').querySelectorAll('.packbtn:not(.done)').forEach(b=>b.onclick=()=>downloadPack(b.dataset.pk)); }
async function downloadPack(id){
  const bar=$('#pkbar-'+id), state=$('#pkstate-'+id), btn=$('#view').querySelector('.packbtn[data-pk="'+id+'"]');
  if(btn) btn.disabled=true;
  // download per-book files for every KJV book
  const abbrs=KJV.books.map(b=>b.a);
  let done=0;
  try{
    for(const ab of abbrs){
      state && (state.textContent='Downloading '+ab+' ('+(done+1)+'/'+abbrs.length+')…');
      const onProg=(f)=>{ if(bar){ const overall=(done+f)/abbrs.length; bar.firstChild.style.width=Math.round(overall*100)+'%'; } };
      if(id==='versions') await YBPacks.ensureBookVersions(ab,onProg);
      else await YBPacks.ensureBookWords(ab,onProg);
      done++;
    }
    if(id==='wordstudy') await YBPacks.ensureStrongs(()=>{});
    state && (state.textContent='Installed'); if(bar) bar.firstChild.style.width='100%';
    if(btn){ btn.textContent='✓ Installed'; btn.classList.add('done'); btn.disabled=false; }
    toast('✓ '+(id==='versions'?'All versions':'Word study')+' installed — works offline now');
  }catch(e){
    state && (state.textContent='Download failed — tap to retry'); if(btn) btn.disabled=false;
    toast('Download needs internet — some parts may be missing');
  }
}
function applyContentUpdate(){ toast('Fetching the latest study content…');
  // pull refreshed content data files from the manifest base and reload
  const files=[['commandments.js','YB_CMDS'],['repentance.js','YB_REPENT'],['news.js','YB_NEWS']];
  Promise.all(files.map(([f])=>fetch(YBPacks.base().replace(/packs\/$/,'code/'+ '../data/'+f)).then(r=>r.ok?r.text():null).catch(()=>null)))
    .then(()=>{ try{localStorage.removeItem('yb_update_avail');}catch(e){} toast('Updated — restart the app to see the latest'); });
}

/* ---------- self-cam overlay (TikTok streaming) — front / back / both ---------- */
let _camStream=null,_camStream2=null;
function toggleCam(){ const cam=$('#cam');
  if(cam.classList.contains('on')){ stopCam(); return; }
  // popup: Front / Back / Both
  document.querySelectorAll('#cammenu').forEach(x=>x.remove());
  const m=document.createElement('div'); m.id='cammenu';
  m.innerHTML='<button data-f="user">🤳 Front camera</button><button data-f="environment">📷 Back camera</button><button data-f="both">🎬 Both</button>';
  document.body.appendChild(m);
  const r=$('#cambtn').getBoundingClientRect(); m.style.top=(r.bottom+6)+'px'; m.style.right=(window.innerWidth-r.right)+'px';
  m.querySelectorAll('button').forEach(bt=>bt.onclick=()=>{ m.remove(); startCam(bt.dataset.f); });
  setTimeout(()=>{ const off=e=>{ if(!m.contains(e.target)&&e.target!==$('#cambtn')){ m.remove(); document.removeEventListener('click',off);} }; document.addEventListener('click',off); },0);
}
async function startCam(mode){ const btn=$('#cambtn');
  try{
    if(mode==='both'||mode==='user'){
      _camStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});
      $('#camvid').srcObject=_camStream; $('#cam').classList.add('on');
    }
    if(mode==='both'||mode==='environment'){
      _camStream2=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'},audio:false});
      $('#camvid2').srcObject=_camStream2; $('#cam2').classList.add('on');
      $('#cam2').style.left='auto'; $('#cam2').style.right='16px';   // start the back cam on the other side
    }
    btn.classList.add('on');
  }catch(e){ toast('Camera unavailable — allow camera access'); }
}
function stopCamWin(id){ const s=id==='cam'?_camStream:_camStream2; if(s)s.getTracks().forEach(t=>t.stop());
  if(id==='cam')_camStream=null; else _camStream2=null; $('#'+id).classList.remove('on','both');
  if(!$('#cam').classList.contains('on')&&!$('#cam2').classList.contains('on')) $('#cambtn').classList.remove('on'); }
function stopCam(){ stopCamWin('cam'); stopCamWin('cam2'); document.querySelectorAll('#cammenu').forEach(x=>x.remove()); }
/* each cam window: drag (1 finger) + pinch-resize (2 fingers), independently */
function initCamWin(cam){ let sx,sy,ox,oy,drag=false, pinch=false, startDist=0, startW=0;
  const dist=t=>Math.hypot(t[0].clientX-t[1].clientX, t[0].clientY-t[1].clientY);
  cam.addEventListener('touchstart',e=>{
    if(e.target.closest('.camctl')) return;
    if(e.touches.length===2){ pinch=true; drag=false; startDist=dist(e.touches); startW=cam.offsetWidth; }
    else{ drag=true; pinch=false; const p=e.touches[0]; sx=p.clientX; sy=p.clientY;
      const r=cam.getBoundingClientRect(); ox=r.left; oy=r.top; cam.style.bottom='auto'; cam.style.right='auto'; }
  },{passive:true});
  cam.addEventListener('touchmove',e=>{
    if(pinch&&e.touches.length===2){ const w=Math.max(90,Math.min(window.innerWidth*0.95, startW*dist(e.touches)/startDist));
      cam.style.width=w+'px'; cam.style.height=w+'px'; e.preventDefault(); return; }
    if(drag){ const p=e.touches[0]; let x=ox+(p.clientX-sx), y=oy+(p.clientY-sy);
      x=Math.max(2,Math.min(window.innerWidth-cam.offsetWidth-2,x));
      y=Math.max(52,Math.min(window.innerHeight-cam.offsetHeight-2,y));
      cam.style.left=x+'px'; cam.style.top=y+'px'; e.preventDefault(); }
  },{passive:false});
  cam.addEventListener('touchend',()=>{drag=false;pinch=false;});
  // mouse fallback (desktop preview)
  let md=false;
  cam.addEventListener('mousedown',e=>{ if(e.target.closest('.camctl'))return; md=true; const r=cam.getBoundingClientRect(); ox=r.left;oy=r.top;sx=e.clientX;sy=e.clientY;cam.style.bottom='auto';cam.style.right='auto';});
  window.addEventListener('mousemove',e=>{ if(!md)return; cam.style.left=Math.max(2,ox+(e.clientX-sx))+'px'; cam.style.top=Math.max(52,oy+(e.clientY-sy))+'px';});
  window.addEventListener('mouseup',()=>md=false);
}
/* border colour cycle: 8 spectrum + pink + white + holographic-rainbow */
const CAMCOLORS=['#e0563b','#e8912e','#e7c94e','#5fd39a','#59b8ff','#6a7be8','#c07ad9','#ff7ac6','#ffffff','holo'];
const _camColorIdx={cam:6,cam2:6};
function cycleCamColor(id){ const cam=$('#'+id); _camColorIdx[id]=(_camColorIdx[id]+1)%CAMCOLORS.length; const c=CAMCOLORS[_camColorIdx[id]];
  cam.classList.toggle('holoborder', c==='holo'); if(c!=='holo') cam.style.borderColor=c; }
function cycleCamForm(id){ const cam=$('#'+id); const forms=['round','land','port']; const cur=forms.find(f=>cam.classList.contains('cf-'+f))||'round';
  const nxt=forms[(forms.indexOf(cur)+1)%forms.length]; forms.forEach(f=>cam.classList.remove('cf-'+f)); cam.classList.add('cf-'+nxt); }
function initCamDrag(){ initCamWin($('#cam')); initCamWin($('#cam2'));
  document.querySelectorAll('.camclose').forEach(b=>b.onclick=e=>{e.stopPropagation();stopCamWin(b.dataset.cam);});
  document.querySelectorAll('.camcolor').forEach(b=>b.onclick=e=>{e.stopPropagation();cycleCamColor(b.dataset.cam);});
  document.querySelectorAll('.camform').forEach(b=>b.onclick=e=>{e.stopPropagation();cycleCamForm(b.dataset.cam);});
  document.querySelectorAll('.cammirror').forEach(b=>b.onclick=e=>{e.stopPropagation();$('#'+b.dataset.cam).classList.toggle('mirror');});
  document.querySelectorAll('.camgreen').forEach(b=>b.onclick=e=>{e.stopPropagation();$('#'+b.dataset.cam).classList.toggle('green');}); }

/* ---------- boot ---------- */
window.addEventListener('DOMContentLoaded',()=>{
  if(newsUnseen()){ const n=document.querySelector('.tab[data-tab="news"]'); if(n){ const d=document.createElement('span'); d.className='dot'; d.id='newsdot'; n.appendChild(d); } }
  document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>nav(b.dataset.tab==='repent'?'repentance':b.dataset.tab));
  $('#cambtn').onclick=toggleCam;
  $('#leftmenubtn').onclick=()=>openDrawer('left');
  $('#rightmenubtn').onclick=()=>openDrawer('right');
  $('#scrim').onclick=closeDrawers;
  $('#tavbtn').onclick=askTaviel;
  $('#settingsbtn').onclick=openSettings;
  initCamDrag();
  window.__goHome=function(){ const o=document.querySelector('#scoverlay'); if(o){o.remove();return;} const s=$('#scrim'); if(s&&!s.hidden){closeDrawers();return;} nav('home'); };
  nav('home');
  setTimeout(()=>checkUpdates(true),1500);   // quiet update check on launch
});
