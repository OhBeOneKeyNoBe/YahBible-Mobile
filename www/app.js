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
  // studio: the middle buttons can be switched off in Settings for a clean streaming screen
  const cta=appSettings().homebtns===0?'':'<div class="cta">'+
      '<button class="homebtn" data-go="commandments"><span class="hi">📜</span><span>The Ten Commandments<span class="hs">study each as a question, in seven dimensions</span></span></button>'+
      '<button class="homebtn" data-go="repentance"><span class="hi">🕊</span><span>Repentance<span class="hs">turn toward the Father, and turn early</span></span></button>'+
      '<button class="homebtn" data-go="news"><span class="hi">✨</span><span>What\'s New<span class="hs">v'+esc(NEWS.version||'')+'</span></span></button>'+
    '</div>';
  setView('<div class="screen home">'+
    '<div class="heb" style="font:700 22px \'Cormorant Garamond\',serif">א &nbsp; ת</div>'+
    '<div class="big"><span class="yb">YahBible</span></div>'+
    '<div class="quote" id="homeq"></div><div class="qref" id="homeqr"></div>'+
    cta+'</div>');
  $('#view').querySelectorAll('.homebtn').forEach(b=>b.onclick=()=>nav(b.dataset.go));
  rotQuote(); clearInterval(_qTimer);
  _qTimer=setInterval(rotQuote, Math.max(5,+appSettings().quotesecs||7)*1000); }
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
  if(appSettings().olc==='off'){ const e=$('#ilbtn'); if(e)e.style.display='none'; }   // eye set to English-only
  $('#verbtn').onclick=()=>toggleChapterVersions(b,ch);
  initSwipe($('#rdbody'),go);
  _rd={bi:bi,ch:ch}; _ilOn=false; _verOn=false;
  colorOriginals(b,ch);   // highlight which words have an original (desktop-style), if the pack is here
  watchReadThrough(bi,ch);   // profile progress: read-through marks the chapter
  watchContinuous(bi);       // continuous scroll (if enabled): bottom auto-loads the next chapter
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
  const rb=$('#rdbody'); if(rb) rb.classList.toggle('hebonly', appSettings().olc==='heb');   // OLC: pure Hebrew
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
/* version code -> language / display name (data/verlang.js, from the desktop versions DB) */
function verLang(c){ const m=(window.YB_VERLANG||{})[c]; return m?m.l:'Other'; }
function verName(c){ const m=(window.YB_VERLANG||{})[c]; return m?m.n:c; }
function allLangs(){ const s=new Set(['English']); Object.values(window.YB_VERLANG||{}).forEach(m=>s.add(m.l||'Other')); return [...s].sort((a,b)=>a==='English'?-1:b==='English'?1:a.localeCompare(b)); }
/* the comparison list: filtered by the chosen languages (English always on), minus the
   eye-hidden versions, in the user's chosen order */
function orderedVisibleVersions(codes){ const s=appSettings();
  let list=codes.filter(c=>verLang(c)==='English'||s.langs.indexOf(verLang(c))>=0);
  list=list.filter(c=>s.hidden.indexOf(c)<0);
  const inx=c=>{ const i=s.verorder.indexOf(c); return i<0?999:i; };
  return list.sort((a,b)=>inx(a)-inx(b)||a.localeCompare(b)); }
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
  // menu buttons stay visible everywhere
  closeDrawers();
  if(tab==='home') showHome();
  else if(tab==='bible') openBible();
  else if(tab==='commandments') showCommandments();
  else if(tab==='repentance'||tab==='repent') openRepentance();
  else if(tab==='realizeus') showRealizeUS();
  else if(tab==='news') openNews(); }
/* embed RealizeUS in the app view (News lives in the right menu now) */
function showRealizeUS(){ clearInterval(_qTimer);
  setView('<div class="screen webscreen"><iframe class="webembed" src="https://realizeus.org" '+
    'sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe>'+
    '<div class="weberr" id="weberr">If RealizeUS doesn’t appear, it may block embedding — '+
    '<a href="https://realizeus.org" target="_blank" rel="noopener">open it in your browser →</a></div></div>');
}

/* ================= DRAWERS (left = sources, right = verse study) — mirrors desktop ================= */
const DESK_KEY='yb_desktop_url';
function deskUrl(){ try{ return localStorage.getItem(DESK_KEY)||''; }catch(e){ return ''; } }
function closeDrawers(){ ['#leftdrawer','#rightdrawer','#scrim'].forEach(s=>{const e=$(s);if(e)e.hidden=true;});
  document.body.classList.remove('seethru'); }
function openDrawer(side){ const d=$(side==='left'?'#leftdrawer':'#rightdrawer'); const other=$(side==='left'?'#rightdrawer':'#leftdrawer');
  if(other)other.hidden=true; $('#scrim').hidden=false;
  // menu transparency reveals the FISH, not the page: the main view steps aside while a menu is open
  document.body.classList.toggle('seethru', (+appSettings().menutrans||0)>0);
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
/* which source pack ids belong to which desktop group */
const SRC_GROUPS={
  bible:['ethiopian_apocrypha','redletter'],
  gnostic:['gnostic_bible','nag_hammadi','pistis_sophia','second_temple','dss','christian'],
  questionable:['quran','mandaean','talmud','targum','midrash','mishnah','tosefta','kabbalah','josephus','torah','yahweh_tsidkenu_full']
};
const SRC_LABEL={ethiopian_apocrypha:'Ethiopian Apocrypha',redletter:'Red Letter Words',gnostic_bible:'The Gnostic Bible',
  nag_hammadi:'The Nag Hammadi Library',pistis_sophia:'Pistis Sophia',second_temple:'Second Temple & Apocrypha',dss:'Dead Sea Scrolls',
  christian:'Christian Writings',quran:'Quran',mandaean:'Mandaean Scriptures',talmud:'The Talmud',targum:'Targums',midrash:'Midrash',
  mishnah:'Mishnah',tosefta:'Tosefta',kabbalah:'Kabbalah',josephus:'Josephus',torah:'Torah (Hebrew)',yahweh_tsidkenu_full:'Yahweh Tsidkenu'};
async function srcItemHtml(id){ const got=window.YBPacks && await YBPacks.have('src:'+id).catch(()=>false);
  return '<button class="srcline'+(got?'':' dl')+'" data-src="'+esc(id)+'"><span class="si">'+(got?'📖':'⬇')+'</span>'+esc(SRC_LABEL[id]||id)+'</button>'; }
/* every non-Bible source is the SAME kind of accordion as the Torah: source -> books -> chapters */
function srcAccHtml(id){ return '<div class="srcacc srcnest" data-srcacc="'+esc(id)+'">'+
  '<button class="accbtn"><span class="si">⬇</span>'+esc(SRC_LABEL[id]||id)+' <span class="acccar">▸</span></button>'+
  '<div class="accbody sbody"></div></div>'; }
async function buildSources(){ const d=$('#leftdrawer');
  d.innerHTML='<div class="drawhdr"><span class="dt holo-gold">Holy Bible</span><button class="drawx" id="ldx">✕</button></div>'+
    '<button class="accbtn lmlogosrow" id="lmlogos"><span><span class="lmyhwh">יהוה</span> The Logos</span></button>'+
    '<div class="srcgroup">'+
      '<div class="srcacc bookgrp" data-grp="torah"><button class="accbtn">The Torah <span class="acccar">▸</span></button><div class="accbody bglist"></div></div>'+
      '<div class="srcacc bookgrp" data-grp="ot"><button class="accbtn">Old Testament <span class="acccar">▸</span></button><div class="accbody bglist"></div></div>'+
      '<div class="srcacc bookgrp" data-grp="nt"><button class="accbtn">New Testament <span class="acccar">▸</span></button><div class="accbody bglist"></div></div>'+
      srcAccHtml('ethiopian_apocrypha')+
      srcAccHtml('redletter')+
    '</div>'+
    '<div class="srcacc" id="acc_gn"><button class="accbtn">Gnostic Scriptures <span class="acccar">▸</span></button>'+
      '<div class="accbody"><button class="srcline gnmap" data-map="1"><span class="si">🗺</span>Gnostic Map (2D/3D)</button>'+
      '<button class="srcline gnmap" data-lineage="1"><span class="si">✶</span>Gnostic Lineage</button>'+
      SRC_GROUPS.gnostic.map(srcAccHtml).join('')+'</div></div>'+
    '<div class="srcacc" id="acc_q"><button class="accbtn">Questionable Sources <span class="acccar">▸</span></button>'+
      '<div class="accbody">'+SRC_GROUPS.questionable.map(srcAccHtml).join('')+'</div></div>'+
    '<div class="lmfoot">'+
      '<button class="srcline" id="lprofile"><span class="si">👤</span>Profile</button>'+
      '<button class="srcline" id="lsettings"><span class="si">⚙️</span>Settings</button>'+
    '</div>';
  $('#ldx',d).onclick=closeDrawers;
  $('#lprofile',d).onclick=()=>{closeDrawers();openProfile();};
  $('#lsettings',d).onclick=()=>{closeDrawers();openSettings();};
  const ll=$('#lmlogos',d); if(ll) ll.onclick=()=>openLogos();
  // Bible groups: click a group -> books expand inline; click a book -> chapter NUMBERS expand
  // inline; click a number -> jump straight to that chapter (never taking over the main area).
  d.querySelectorAll('.bookgrp>.accbtn').forEach(a=>a.onclick=()=>{ const acc=a.parentElement; acc.classList.toggle('open'); fillBookGroup(acc); });
  // every other source unfolds the same way: books, then chapters, inline in the menu
  d.querySelectorAll('.srcnest>.accbtn').forEach(a=>a.onclick=()=>{ const acc=a.parentElement; acc.classList.toggle('open'); fillSourceAcc(acc); });
  d.querySelectorAll('.gnmap').forEach(b=>b.onclick=()=>{ if(b.dataset.lineage) openGnosticLineage(); else openGnosticMap(); });
  d.querySelectorAll('.srcacc:not(.bookgrp):not(.srcnest)>.accbtn').forEach(a=>a.onclick=()=>a.parentElement.classList.toggle('open'));
  // mark installed sources with the book icon
  d.querySelectorAll('.srcnest').forEach(async n=>{ if(window.YBPacks && await YBPacks.have('src:'+n.dataset.srcacc).catch(()=>false)){ const si=n.querySelector('.si'); if(si)si.textContent='📖'; } });
}
/* fill a source accordion: download if needed, then books -> chapter numbers, inline */
async function fillSourceAcc(acc){ const id=acc.dataset.srcacc, body=acc.querySelector('.sbody');
  if(!body||body.dataset.done) return;
  body.innerHTML='<div class="srcnote">loading…</div>';
  let data=_srcCache[id];
  try{ if(!data){ data=await YBPacks.ensureSource(id); _srcCache[id]=data; } }
  catch(e){ body.innerHTML='<div class="srcnote">needs internet to download — tap again to retry</div>'; return; }
  body.dataset.done='1';
  const si=acc.querySelector('.si'); if(si)si.textContent='📖';
  const books=Object.keys(data||{});
  body.innerHTML=books.map((bk,i)=>'<div class="bookacc" data-sb="'+i+'"><button class="bkbtn">'+esc(bk)+' <span class="acccar">▸</span></button><div class="chwrap"></div></div>').join('')||'<div class="srcnote">no books</div>';
  body.querySelectorAll('.bookacc').forEach(ba=>{ const bk=books[+ba.dataset.sb];
    ba.querySelector('.bkbtn').onclick=()=>{
      const groups=srcChapters(data[bk]||[]);
      if(groups.length<=1){ closeDrawers(); openSourceBook(id,bk); return; }   // one chapter: open it
      ba.classList.toggle('open'); const w=ba.querySelector('.chwrap'); if(w.childElementCount) return;
      w.innerHTML=groups.map(g=>'<button class="chnum" data-ch="'+esc(g.ch)+'">'+esc(g.ch)+'</button>').join('');
      w.querySelectorAll('.chnum').forEach(cb=>cb.onclick=()=>{ closeDrawers(); openSourceBook(id,bk,cb.dataset.ch); }); }; });
}
/* Left-menu accordions: a Bible group expands to its books; a book expands to its chapter numbers. */
function fillBookGroup(acc){ const body=acc.querySelector('.bglist'); if(!body||body.childElementCount) return;
  const kind=acc.dataset.grp; const idxs=[];
  KJV.books.forEach((b,i)=>{ if(kind==='torah'){ if(i<5) idxs.push(i); } else if(b.t===(kind==='ot'?'OT':'NT')) idxs.push(i); });
  body.innerHTML=idxs.map(i=>'<div class="bookacc" data-bi="'+i+'"><button class="bkbtn">'+esc(KJV.books[i].n)+' <span class="acccar">▸</span></button><div class="chwrap"></div></div>').join('');
  body.querySelectorAll('.bkbtn').forEach(btn=>btn.onclick=()=>{ const ba=btn.parentElement; ba.classList.toggle('open'); fillChapters(ba); }); }
function fillChapters(ba){ const wrap=ba.querySelector('.chwrap'); if(!wrap||wrap.childElementCount) return;
  const bi=+ba.dataset.bi, b=KJV.books[bi]; if(!b) return;
  wrap.innerHTML=b.ch.map((_,k)=>'<button class="chnum" data-ch="'+(k+1)+'">'+(k+1)+'</button>').join('');
  wrap.querySelectorAll('.chnum').forEach(c=>c.onclick=()=>{ closeDrawers(); openReader(bi,+c.dataset.ch); }); }
/* ---------- the Gnostic Map (cosmology, 2D/3D) + the Gnostic Lineage — installed, offline ---------- */
function loadGnosticData(){ return new Promise((res,rej)=>{ if(window.GNOSTIC_MAP){res();return;}
  const s=document.createElement('script'); s.src='data/gnostic.js'; s.onload=()=>res();
  s.onerror=()=>{ // older APK without the bundled data: fetch it from the pack host
    const r=document.createElement('script'); r.src='https://huggingface.co/OhBeOneKeyNoBe/YahBible-Mobile/resolve/main/www/data/gnostic.js';
    r.onload=()=>res(); r.onerror=()=>rej(new Error('no data')); document.head.appendChild(r); };
  document.head.appendChild(s); }); }
function openGnosticMap(){ closeDrawers(); clearInterval(_qTimer);
  setView('<div class="screen mapscreen"><button class="backbtn" id="gmback">◀ back</button>'+
    '<div class="gmaphead"><h2 class="gmapttl">Gnostic Map</h2>'+
    '<div class="gmapsub">The flat world the Demiurge molded — the disc, the dome, the portals of the sun, the ten heavens and the four hollow places, from 1–3 Enoch. The giant beings stand hidden: tap a gold marker in the 3D view to reveal one at its true scale.</div></div>'+
    '<iframe id="cosmosframe" class="cosmosframe" src="cosmos.html" title="Gnostic Map"></iframe></div>');
  $('#gmback').onclick=()=>nav('bible'); }
function openGnosticLineage(){ closeDrawers(); clearInterval(_qTimer);
  setView('<div class="screen"><button class="backbtn" id="glback">◀ back</button>'+
    '<div class="gmaphead"><h2 class="gmapttl">Gnostic Lineage</h2>'+
    '<div class="gmapsub">The chain of emanation from the Monad down to Adam &amp; Eve — and the angelic hierarchy beside it. Tap any being to read it.</div></div>'+
    '<div id="gdcard"></div><div id="lineageBody"><div class="srcnote">unfolding the lineage…</div></div></div>');
  $('#glback').onclick=()=>nav('bible');
  loadGnosticData().then(renderLineageMobile).catch(()=>{ const b=$('#lineageBody'); if(b)b.innerHTML='<div class="srcnote">could not load the lineage data</div>'; }); }
function renderLineageMobile(){ const d=window.GNOSTIC_MAP, body=$('#lineageBody'); if(!d||!body) return;
  const byTier={}; d.nodes.forEach(n=>{(byTier[n.tier]=byTier[n.tier]||[]).push(n);});
  const tiers=Object.keys(byTier).map(Number).sort((a,b)=>a-b);
  const anyAng=d.nodes.some(n=>n.col==='angelic');
  const btn=n=>'<button class="gnode '+n.side+(n.first_deficiency?' demiurge':'')+(n.col==='angelic'?' angelic':'')+'" data-id="'+esc(n.id)+'">'+
    '<span class="gnname">'+esc(n.name)+'</span><span class="gnaka">'+esc(n.aka||'')+'</span>'+
    ((n.members&&n.members.length)?'<span class="gnmore">▸ '+n.members.length+' within</span>':'')+'</button>';
  let h='<div class="gmap">';
  if(anyAng) h+='<div class="gcolhead"><span class="gche">The Emanation<small>Monad → the Lineage</small></span></div>';
  tiers.forEach((t,i)=>{ const nodes=byTier[t], eman=nodes.filter(n=>n.col!=='angelic');
    if(nodes.some(n=>n.first_deficiency)) h+='<div class="gdivide"><span>▲ The Fullness — here Sophia brings forth the Demiurge, apart from her consort — The Deficiency ▼</span></div>';
    else if(i>0&&eman.length) h+='<div class="gconn"></div>';
    if(eman.length) h+='<div class="grow">'+eman.map(btn).join('')+'</div>'; });
  if(anyAng){ h+='<div class="gcolhead" style="margin-top:26px"><span class="gche">The Angelic Hierarchy<small>1–3 Enoch &amp; the Hekhalot — each bows to the one above</small></span></div>';
    tiers.forEach(t=>{ const ang=byTier[t].filter(n=>n.col==='angelic');
      if(ang.length) h+='<div class="grow">'+ang.map(btn).join('')+'</div>'; }); }
  h+='<div class="gsearchwrap"><input id="gsearch" class="gsearch" type="text" placeholder="search every being in the lineage…" autocomplete="off"><div id="gsresults"></div></div>';
  h+='<div id="bibleLineage"></div></div>';
  body.innerHTML=h;
  const map={}; d.nodes.forEach(n=>map[n.id]=n);
  body.querySelectorAll('.gnode').forEach(el=>el.onclick=()=>{
    body.querySelectorAll('.gnode.sel').forEach(x=>x.classList.remove('sel')); el.classList.add('sel');
    const n=map[el.dataset.id]; showGnosticNodeMobile(n);
    if(n.members&&n.members.length) toggleMembersMobile(n,el); });
  wireGnosticSearchMobile(map);
  renderBloodlineMobile();
}
function showGnosticNodeMobile(n){ const card=$('#gdcard'); if(!card||!n) return;
  const f=(lbl,txt)=>txt?('<div class="gfield"><b>'+lbl+'</b><p>'+esc(txt)+'</p></div>'):'';
  card.innerHTML='<div class="gdetail"><h3 class="gdname holo-gold">'+esc(n.name)+'</h3>'+
    '<div class="gdaka">'+esc(n.aka||'')+'</div>'+
    f('Definition',n.definition)+f('Appearance',n.appearance)+f('Nature',n.nature)+
    ((n.citations&&n.citations.length)?'<div class="gfield"><b>Where it is written</b><div class="gcites">'+n.citations.map(c=>'<span class="gcite">'+esc(typeof c==='string'?c:(c.cite||c.ref||c.book||''))+'</span>').join('')+'</div></div>':'')+
    '</div>';
  card.scrollIntoView({behavior:'smooth',block:'nearest'}); }
function toggleMembersMobile(n,el){ const row=el.parentElement; let box=row.querySelector('.gmembers[data-of="'+n.id+'"]');
  if(box){ box.remove(); return; }
  row.querySelectorAll('.gmembers').forEach(x=>x.remove());
  box=document.createElement('div'); box.className='gmembers'; box.dataset.of=n.id;
  box.innerHTML=(n.members||[]).map((m,i)=>'<button class="gmcard" data-mi="'+i+'"><span class="gmname">'+esc(m.name)+'</span>'+
    (m.roster?'<span class="gmaka">'+esc(m.roster)+'</span>':'')+(m.place?'<span class="gmcite">'+esc(m.place)+'</span>':'')+'</button>').join('');
  el.insertAdjacentElement('afterend',box);
  box.querySelectorAll('.gmcard').forEach(b=>b.onclick=e=>{ e.stopPropagation();
    box.querySelectorAll('.gmcard.sel').forEach(x=>x.classList.remove('sel')); b.classList.add('sel');
    showGnosticNodeMobile(n.members[+b.dataset.mi]); }); }
function wireGnosticSearchMobile(map){ const inp=$('#gsearch'), out=$('#gsresults'); if(!inp||!out) return;
  const flat=[]; Object.values(map).forEach(n=>{ flat.push({e:n,grp:n.col==='angelic'?'angelic hierarchy':'emanation'});
    (n.members||[]).forEach(m=>flat.push({e:m,grp:'within '+n.name})); });
  inp.oninput=()=>{ const q=inp.value.trim().toLowerCase(); if(!q){out.innerHTML='';return;}
    const hits=flat.filter(x=>((x.e.name||'')+' '+(x.e.aka||'')).toLowerCase().includes(q)).slice(0,12);
    out.innerHTML=hits.length?hits.map((x,i)=>'<button class="gsrow" data-i="'+i+'"><span class="gsname">'+esc(x.e.name)+'</span><span class="gsgrp">'+esc(x.grp)+'</span></button>').join(''):'<div class="srcnote">no being answers to that name</div>';
    out.querySelectorAll('.gsrow').forEach(b=>b.onclick=()=>showGnosticNodeMobile(hits[+b.dataset.i].e)); }; }
function renderBloodlineMobile(){ const t=window.BIBLE_LINEAGE, box=$('#bibleLineage'); if(!t||!box) return;
  const P={}; const flat=(node)=>{ if(!node)return; P[node.id]=node; (node.kids||[]).forEach(flat); };
  t.spine.forEach(s=>P[s.id]=s); Object.values(t.branches||{}).forEach(a=>a.forEach(flat)); (t.families||[]).forEach(flat);
  const tree=node=>{ const kids=node.kids||[];
    const chip='<button class="blbranch'+(kids.length?' haskids':'')+'" data-id="'+esc(node.id)+'">'+esc(node.name)+(kids.length?'<span class="blkids">+'+kids.length+'</span>':'')+'</button>';
    return kids.length?('<li>'+chip+'<ul class="blsub">'+kids.map(tree).join('')+'</ul></li>'):('<li>'+chip+'</li>'); };
  let h='<div class="blhead"><h3 class="gmapttl" style="font-size:22px">The bloodline continues</h3>'+
    '<div class="gmapsub">Adam to Joseph’s father — '+t.spine.length+' generations from the Bible name catalog. '+t.connected+' souls join Adam’s tree; tap a name carrying <b>+N</b> to open its descendants.</div></div><div class="blspine">';
  t.spine.forEach((s,i)=>{ const br=(t.branches||{})[s.id]||[];
    h+='<div class="blrow"><button class="blnode" data-id="'+esc(s.id)+'"><span class="blgen">'+(s.gen||'·')+'</span><span class="bltext"><span class="blname">'+esc(s.name)+'</span>'+(s.meaning?'<span class="blmean">'+esc(s.meaning)+'</span>':'')+'</span></button>'+
      (br.length?('<ul class="blbranches">'+br.map(tree).join('')+'</ul>'):'')+'</div>';
    if(i<t.spine.length-1)h+='<div class="blconn"></div>'; });
  h+='</div>';
  const fam=t.families||[];
  if(fam.length) h+='<div class="blfamhead">Families beside the main line <span class="blkids">'+fam.length+'</span></div><ul class="blfamilies">'+fam.map(tree).join('')+'</ul>';
  box.innerHTML=h;
  box.querySelectorAll('.blnode,.blbranch').forEach(el=>el.onclick=e=>{ e.stopPropagation();
    box.querySelectorAll('.sel').forEach(x=>x.classList.remove('sel')); el.classList.add('sel');
    if(el.classList.contains('haskids')){ const sub=el.parentElement.querySelector(':scope > .blsub'); if(sub)sub.classList.toggle('open'); }
    const p=P[el.dataset.id]; if(p) showBiblePersonMobile(p); }); }
function showBiblePersonMobile(p){ const card=$('#gdcard'); if(!card||!p) return;
  const dl=[];
  if(p.gen)dl.push(['generation','#'+p.gen+' from Adam']);
  if(p.father)dl.push(['father',(p.father||'').replace('BIBLE:','').replace(/\(.*\)/,'')]);
  if(p.mother)dl.push(['mother',(p.mother||'').replace('BIBLE:','').replace(/\(.*\)/,'')]);
  if(p.age_beget!=null)dl.push(['age at begetting',p.age_beget+' years']);
  if(p.age_death!=null)dl.push(['age at death',p.age_death+' years']);
  if(p.nchildren)dl.push(['children named',''+p.nchildren]);
  const rows=dl.map(kv=>'<div class="blfld"><span class="blk">'+esc(kv[0])+'</span><span class="blv">'+esc(kv[1])+'</span></div>').join('');
  card.innerHTML='<div class="gdetail"><h3 class="gdname holo-gold">'+esc(p.name)+'</h3>'+
    '<div class="gdaka">'+esc(p.disambig||(p.stub?'named in the text as a parent, without a fuller record':''))+'</div>'+
    (p.bio?'<div class="gfield"><b>Who they are</b><p>'+esc(p.bio)+'</p></div>':'')+
    (p.meaning?'<div class="gfield"><b>Meaning of the name</b><p>'+esc(p.meaning)+'</p></div>':'')+
    (rows?'<div class="gfield"><b>In the record</b><div class="blflds">'+rows+'</div></div>':'')+
    (p.ref?'<div class="gfield"><b>Where it is written</b><div class="gcites"><span class="gcite">KJV · '+esc(p.ref)+'</span></div></div>':'')+'</div>';
  card.scrollIntoView({behavior:'smooth',block:'nearest'}); }
/* The Logos — the revelation of the Name (YHWH), 1:1 with desktop */
function openLogos(){ closeDrawers(); clearInterval(_qTimer);
  setView('<div class="screen study logospage"><button class="backbtn" id="lgback">◀ back</button>'+
    '<div class="logoshead"><div class="logosyhwh holo-gold">יהוה</div>'+
    '<div class="logossub">The Name · The Word · The Logos · The Truth — Yahweh Tsidkenu’s revelation of the Word</div></div>'+
    '<div class="cmdsec"><div class="cmdeye">The Name is Breath</div><h3>The Name is Breath</h3>'+
      '<p><span class="heb">יהוה</span> (YHWH) is the ineffable, unpronounceable Name. It is the sound of <b>breathing</b>: breathed aloud — without the tongue or lips perverting the breath — it sounds like <i>YHWH</i>; with the mouth closed it sounds like the <b>ocean</b>.</p>'+
      '<p>This is the holy Word, the holy Name, and “The Truth” that Christ spoke of. Anytime Christ, the New Testament, or the Old Testament speak of <b>the Word</b>, <b>the Logos</b>, <b>the Knowledge</b>, or <b>the Truth</b>, they mean <span class="heb">יהוה</span> specifically.</p>'+
      '<div class="cscr">“I have declared thy name, and will declare it… I have kept them in thy word.”<span class="cscrref">'+linkifyScripture("John 17:26")+' · thy word = thy Logos, thy Name</span></div>'+
      '<p>The vowel points placed under the letters are a <b>modern pronunciation guide</b> laid upon the unpronounceable Name — not its true sound.</p></div>'+
    '<div class="cmdsec cmddefine"><div class="cmdeye">Its opposite</div><h3>The Illusion of “Jehovah”</h3>'+
      '<p><b>Yah / Jah</b> means <i>father</i>. <b>Hovah</b> (<span class="heb">הוה</span>) means <i>destruction, chaos</i> — a real Hebrew word. So “Yah-Hovah” is heard by a Hebrew as a <b>curse upon the father</b> — father-destruction, father-chaos.</p>'+
      '<p>To curse a thing is not to bless it; it cannot be the name of the one true God. Remove the <b>Yod</b> and <span class="heb">הוה</span> is literally <i>hovah</i> — destruction. The Yod in front means the Name is <b>not a spoken word</b>: the Yod is silent. Without the Yod — without God — there is only destruction.</p>'+
      '<p>The belief that “Jehovah” or “Yahovah” is God’s proper name is <b>worldly illogic</b>, not the heavenly logic of God.</p>'+
      '<p>Everywhere the English says <b>“Lord,” “the Lord,”</b> or <b>“LORD,”</b> the Hebrew is usually <span class="heb">יהוה</span> (or Adonai <span class="heb">אֲדֹנָי</span>) — never Jehovah.</p></div>'+
    '<div class="cmdsec cmdkeep"><div class="cmdeye">How to read it</div><h3>Gnostic Symbolic Branching</h3>'+
      '<p>To read the Name as the Word, the Logos, the Knowledge, and the Truth — and to follow that thread wherever Scripture speaks of them — is <b>Gnostic Symbolic Branching</b>: reading by the true words, teachings, and sayings of Yeshua the Christ. This is how the Bible is to be understood, according to Yahweh Tsidkenu. <b>Question everything claimed; seek the highest truth.</b></p></div>'+
    '<button class="cmdback" id="lgback2">◀ back</button></div>');
  $('#view').querySelectorAll('#lgback,#lgback2').forEach(b=>b.onclick=()=>nav('home'));
  wireScref($('#view'));
}
function openBookGroup(kind){ let list;
  if(kind==='torah') list=KJV.books.slice(0,5);
  else if(kind==='ot') list=KJV.books.filter(b=>b.t==='OT');
  else list=KJV.books.filter(b=>b.t==='NT');
  setView('<div class="screen"><div class="listhdr">'+(kind==='torah'?'The Torah':kind==='ot'?'Old Testament':'New Testament')+'</div>'+
    '<div class="bookgrid">'+list.map(bk=>{const i=KJV.books.indexOf(bk);return '<button class="bookcell" data-bi="'+i+'">'+esc(bk.n)+'</button>';}).join('')+'</div></div>');
  $('#view').querySelectorAll('.bookcell').forEach(c=>c.onclick=()=>openBook(+c.dataset.bi)); }
async function downloadEverything(){ toast('Downloading everything — this may take a while…');
  try{ const list=await YBPacks.sourcesIndex();
    for(const s of (list||[])){ try{ await YBPacks.ensureSource(s.id); }catch(e){} }
    // versions + word study per book
    for(const bk of KJV.books){ try{ await YBPacks.ensureBookVersions(bk.a); }catch(e){} try{ await YBPacks.ensureBookWords(bk.a); }catch(e){} }
    try{ await YBPacks.ensureStrongs(); }catch(e){}
    toast('✓ Everything downloaded — works fully offline now');
  }catch(e){ toast('Download needs internet — some parts may be missing'); }
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
    '<div class="srchdr"><div class="srctitle holo-gold">'+esc(SRC_LABEL[id]||id.replace(/_/g,' '))+'</div>'+
      '<div class="srcsub">'+books.length+(books.length===1?' book':' books')+' · tap a book to read</div></div>'+
    '<div class="srcindex">'+books.map((bk,i)=>{ const n=(data[bk]||[]).length;
      return '<button class="srcbook" data-b="'+i+'"><span class="sbn">'+esc(bk)+'</span><span class="sbc">'+n+'</span></button>'; }).join('')+
    '</div></div>');
  $('#srcback').onclick=()=>{nav('bible');};
  $('#view').querySelectorAll('.srcbook').forEach(r=>r.onclick=()=>openSourceBook(id,books[+r.dataset.b]));
}
/* organize a source book's units into chapters by their ref ("3:14" -> chapter 3) */
function srcChapters(units){ const groups=[]; let cur=null;
  (units||[]).forEach(u=>{ const ref=String(u[0]||''); const m=ref.match(/(\d+)\s*[:.·]\s*\d+/);
    const ch=m?m[1]:((ref.match(/^\s*(\d+)\s*$/)||[])[1]||'');
    if(!cur||cur.ch!==ch){ cur={ch:ch,rows:[]}; groups.push(cur); } cur.rows.push(u); });
  return groups; }
function openSourceBook(id,book,chapter){ const data=_srcCache[id]||{}; const units=data[book]||[];
  const groups=srcChapters(units);
  const multi=groups.length>1;
  const body=groups.map(g=>{ const head=(multi&&g.ch)?'<div class="rchap" id="sch'+esc(g.ch)+'">Chapter '+esc(g.ch)+'</div>':'';
    return head+g.rows.map(u=>{ const ref=String(u[0]||''); const vn=(ref.match(/[:.·]\s*(\d+)\s*$/)||[])[1]||ref;
      return '<p class="rv"><span class="rvn">'+esc(vn)+'</span>'+esc(u[1]||'')+'</p>'; }).join(''); }).join('');
  setView('<div class="screen reader"><div class="rdbar"><button class="backbtn" id="sbk">◀ '+esc(SRC_LABEL[id]||id.replace(/_/g,' '))+'</button>'+
    '<div class="rdttl">'+esc(book)+'</div><div></div></div>'+
    '<div class="rdbody"><div class="srcbookttl holo-gold">'+esc(book)+'</div>'+(body||'<div class="srcnote">no text</div>')+'</div></div>');
  $('#sbk').onclick=()=>openSource(id);
  if(chapter){ const el=document.getElementById('sch'+chapter); if(el) setTimeout(()=>el.scrollIntoView({block:'start'}),80); }
}
/* the right-menu nav (desktop-style): Settings, News (א-ת), Repentance (dove), Ten Commandments */
function rightNavHtml(){ const pulse=newsUnseen()?' pulse':'';
  return '<div class="rmnav">'+
    '<button class="rmitem'+pulse+'" data-go="news"><span class="rmi rmat">א&#8202;ת</span>News &amp; Updates'+(newsUnseen()?'<span class="newsdot"></span>':'')+'</button>'+
    '</div>'; }
/* Repentance + the Ten Commandments, desktop-style: holographic numbers, white text */
function rightDevotionHtml(){
  return '<button class="rmitem" data-go="repentance" style="margin-top:14px"><span class="rmi">🕊</span>Repentance</button>'+
    '<div class="cxlbl" style="margin-top:12px">The Ten Commandments</div>'+
    '<div class="tclist">'+CMDS.map(t=>'<button class="tcrow" data-ci="'+t.n+'">'+
      '<span class="tcn">'+t.n+'</span><span class="tct">'+esc(t.cmd)+'</span></button>').join('')+'</div>'; }
function wireRightNav(scope){ scope.querySelectorAll('.rmitem[data-go]').forEach(b=>b.onclick=()=>{ closeDrawers();
  const g=b.dataset.go; if(g==='settings')openSettings(); else if(g==='profile')openProfile(); else nav(g); });
  scope.querySelectorAll('.tcrow').forEach(b=>b.onclick=()=>{ closeDrawers(); openCommandment(+b.dataset.ci); }); }
/* RIGHT drawer — nav + verse study */
async function buildStudy(){ const d=$('#rightdrawer');
  if(!_sel){ d.innerHTML='<div class="drawhdr"><span class="dt">Menu</span><button class="drawx" id="rdx">✕</button></div>'+
      rightNavHtml()+
      '<div class="srcnote">Tap a verse in the reader to study it here — its words, versions, and the original Hebrew or Greek.</div>'+
      rightDevotionHtml();
    $('#rdx',d).onclick=closeDrawers; wireRightNav(d); return; }
  const b=KJV.books[_sel.bi], v=_sel.v, txt=(b.ch[_sel.ch-1]||[])[v-1]||'';
  const ref=b.n+' '+_sel.ch+':'+v;
  const words=txt.replace(/[^A-Za-z' -]/g,' ').split(/\s+/).filter(w=>w.length>1)
    .map(w=>'<button class="wchip" data-w="'+esc(w)+'">'+esc(w)+'</button>').join('');
  // which packs are installed?
  const haveVer=window.YBPacks && await YBPacks.have('ver:'+b.a).catch(()=>false);
  const haveWs =window.YBPacks && await YBPacks.have('ws:'+b.a).catch(()=>false);
  d.innerHTML='<div class="drawhdr"><span class="dt">Menu &amp; Verse Study</span><button class="drawx" id="rdx">✕</button></div>'+
    rightNavHtml()+
    '<div class="vsref holo-gold">'+esc(ref)+'</div>'+
    '<div class="vstext">'+esc(txt)+'</div>'+
    '<div class="vstabs"><button class="vstab'+(haveVer?'':' locked')+'" data-x="versions">Compare versions</button>'+
      '<button class="vstab'+(haveWs?'':' locked')+'" data-x="orig">Original language</button>'+
      '<button class="vstab'+(haveWs?'':' locked')+'" data-x="inter">Interlinear</button></div>'+
    '<div id="vspanel"></div>'+
    '<div class="cxlbl">Words — tap for study</div><div class="wchips">'+words+'</div>'+
    (haveVer&&haveWs?'':'<div class="connectcard"><div class="cct">📦 Get more, offline</div><p>Download the versions &amp; word‑study packs to compare 120+ translations and see the Hebrew/Greek here — no connection needed.</p><button class="connectbtn" id="rconnect">Open Downloads</button></div>')+
    rightDevotionHtml();
  $('#rdx',d).onclick=closeDrawers;
  const rc=$('#rconnect',d); if(rc) rc.onclick=()=>connectPrompt();
  d.querySelectorAll('.vstab').forEach(bt=>bt.onclick=()=>{ if(bt.classList.contains('locked')){connectPrompt();return;} showVsPanel(bt.dataset.x,b,_sel.ch,v); });
  d.querySelectorAll('.wchip').forEach(bt=>bt.onclick=()=>{ if(haveWs) showWordPack(bt.dataset.w,b,_sel.ch,v); else connectPrompt(); });
  wireRightNav(d);
}
async function showVsPanel(kind,b,ch,v){ const el=$('#vspanel'); if(!el) return; el.innerHTML='<div class="srcnote">loading…</div>';
  try{
    if(kind==='versions'){
      const data=await YBPacks.ensureBookVersions(b.a);
      const codes=orderedVisibleVersions(Object.keys(data||{}));
      const rows=codes.map(vc=>{ const t=(((data[vc]||{})[ch]||{})[v])||''; if(!t) return '';
        return '<div class="vrow"><span class="vcode" title="'+esc(verName(vc))+'">'+esc(vc)+'</span><span class="vtxt">'+esc(t)+'</span></div>'; }).filter(Boolean).join('');
      el.innerHTML='<div class="cxlbl">Across '+codes.length+' versions (your languages, order &amp; eyes — Settings)</div><div class="vlist">'+(rows||'<div class="srcnote">no data for this verse</div>')+'</div>';
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
function markContentUpdate(v){ try{ localStorage.setItem('yb_update_avail',v); }catch(e){} }
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
      '<button id="signout" class="miniupd" style="margin-left:auto">Sign out</button></div>'+
      (acct.unverified?'<p class="setnote">⚠ Not yet on the Zion’iel Network — this name isn’t claimed. Connect to your desktop and sign in again to register it.</p>':'')+'</div>'
    : '<div class="cmdsec cmdlogin"><div class="cmdeye">Account</div><h3>Sign in or create an account</h3>'+
      '<p class="setnote">Your account (the Zion’iel Network) keeps your notes, bookmarks &amp; reading progress across your phone and desktop.</p>'+
      '<input id="lg_name" class="setinput" placeholder="Name or username" style="margin-bottom:8px">'+
      '<input id="lg_email" class="setinput" placeholder="Email (optional)" style="margin-bottom:8px">'+
      '<input id="lg_pw" class="setinput" type="password" placeholder="Password" style="margin-bottom:10px">'+
      '<div class="setrow"><button id="dosignin" class="connectbtn" style="width:auto;padding:10px 16px">Sign in</button>'+
      '<button id="doguest" class="miniupd">Continue as guest</button></div></div>';
  const a=appSettings();
  const OPEN=window._setOpen=(window._setOpen||{eye:false,appear:true});
  const sec=(id,ttl,inner)=>'<div class="srcacc setsec'+(OPEN[id]?' open':'')+'" data-sec="'+id+'">'+
    '<button class="accbtn">'+ttl+' <span class="acccar">▸</span></button><div class="accbody">'+inner+'</div></div>';
  const chip=(cls,on,data,label,title)=>'<button class="favchip '+cls+(on?' on':'')+'" '+data+(title?' title="'+esc(title)+'"':'')+'>'+label+'</button>';
  /* 👁 eye settings — OLC + the version-comparison picker (desktop parity) */
  const favs=favVersions();
  const olcSeg='<div class="camblbl">👁 Original Language — what the chapter eye shows</div><div class="setrow" style="flex-wrap:wrap;gap:8px">'+
    [['heb','Pure Hebrew'],['both','Hebrew + English'],['off','English only']].map(m=>chip('s_olc',a.olc===m[0],'data-m="'+m[0]+'"',m[1])).join('')+'</div>';
  const byl={}; Object.keys(window.YB_VERLANG||{}).forEach(c=>{ const l=verLang(c); (byl[l]=byl[l]||[]).push(c); });
  const vlcLangs=['English'].concat(a.langs.filter(l=>l!=='English')).filter(l=>byl[l]);
  const vlcPick='<div class="camblbl" style="margin-top:12px">🌳 Version comparison — stacks under each verse (up to 7)</div>'+
    vlcLangs.map(l=>'<div class="langgrp">'+esc(l)+'</div><div class="favver">'+byl[l].sort().map(c=>
      chip('vlcv',favs.indexOf(c)>=0,'data-v="'+esc(c)+'"',esc(c),verName(c))).join('')+'</div>').join('')+
    '<p class="setnote">'+favs.length+'/7 selected · more languages under 🌐 below</p>';
  /* 🌐 languages + version order & eyes */
  const langChips='<div class="camblbl">Comparison languages (English always on)</div><div class="favver">'+
    allLangs().map(l=>chip('s_lang'+(l==='English'?' lock':''),l==='English'||a.langs.indexOf(l)>=0,'data-l="'+esc(l)+'"',esc(l))).join('')+'</div>';
  const ordCodes=(function(){ let list=Object.keys(window.YB_VERLANG||{}).filter(c=>verLang(c)==='English'||a.langs.indexOf(verLang(c))>=0);
    const inx=c=>{ const i=a.verorder.indexOf(c); return i<0?999:i; };
    return list.sort((x,y)=>inx(x)-inx(y)||x.localeCompare(y)); })();
  const ordList='<div class="camblbl" style="margin-top:12px">Version order &amp; eyes (the compare list)</div>'+
    '<p class="setnote">The 👁 hides a version from comparisons; ↑ ↓ set the order they stack in.</p>'+
    '<div id="vorder">'+ordCodes.map(c=>'<div class="vorow" data-v="'+esc(c)+'">'+
      '<button class="voeye'+(a.hidden.indexOf(c)>=0?' off':'')+'" title="show / hide">👁</button>'+
      '<span class="voname"><b>'+esc(c)+'</b> '+esc(verName(c))+'</span>'+
      '<button class="vomv" data-d="-1">↑</button><button class="vomv" data-d="1">↓</button></div>').join('')+'</div>';
  setView('<div class="screen study"><button class="backbtn" data-back="bible">◀ back</button>'+
    '<div class="cmdno">App</div><h2 class="cmdttl">Settings</h2>'+
    acctCard+
    (upd&&upd>APP_CONTENT_VER?'<div class="updbanner">✨ New study content available (v'+esc(upd)+'). <button id="applyupd" class="miniupd">Update now</button></div>':'')+
    sec('eye','👁 Eye settings', olcSeg+vlcPick)+
    sec('appear','🎨 Appearance &amp; theme',
      '<div class="camblbl">Theme</div><div class="setrow" style="flex-wrap:wrap;gap:8px">'+
      [['parchment','Parchment'],['sepia','Sepia'],['night','Night']].map(t=>chip('s_theme',a.theme===t[0],'data-t="'+t[0]+'"',t[1])).join('')+'</div>'+
      '<div class="setctl"><label>Reader text size</label><input type="range" id="s_reader" min="14" max="26" value="'+a.reader+'"></div>'+
      '<div class="setctl"><label>Hebrew / original text size</label><input type="range" id="s_heb" min="16" max="40" value="'+a.hebsize+'"></div>'+
      '<div class="setctl"><label>Accent hue</label><input type="range" id="s_hue" min="0" max="360" value="'+a.hue+'"></div>'+
      '<div class="setrow"><label class="setnote" style="margin:0">Auto-randomize hue</label><select id="s_hrandsel" class="setinput" style="width:auto">'+
        [[0,'Off'],[15,'Every 15s'],[30,'Every 30s'],[60,'Every minute'],[300,'Every 5 min']].map(o=>'<option value="'+o[0]+'"'+(+a.huerand===o[0]?' selected':'')+'>'+o[1]+'</option>').join('')+'</select></div>'+
      '<div class="setrow"><label class="setnote" style="margin:0">Christ-quote change interval (seconds)</label>'+
      '<input type="number" id="s_qsecs" class="setinput" style="width:80px" min="5" max="3600" step="5" value="'+a.quotesecs+'"></div>')+
    sec('bgfish','🐟 Background &amp; the fish',
      '<div class="setrow"><button class="favchip'+(a.showbg?' on':'')+'" id="s_showbg">🐟 Holy-fish background</button></div>'+
      '<div class="setctl"><label>Background &amp; fish visibility</label><input type="range" id="s_fish" min="0" max="70" value="'+a.fishvis+'"></div>'+
      '<div class="setctl"><label>Content transparency (reveal the fish)</label><input type="range" id="s_centerop" min="20" max="100" value="'+a.centerop+'"></div>'+
      '<div class="setctl"><label>Menu transparency (reveal the fish)</label><input type="range" id="s_menutrans" min="0" max="100" value="'+a.menutrans+'"></div>'+
      '<p class="setnote">With menu transparency on, an open menu reveals the fish behind it — never the page you were reading.</p>')+
    sec('reading','📖 Reading',
      '<div class="setrow"><button class="favchip'+(+a.contscroll?' on':'')+'" id="s_cont">📜 Continuous scroll (auto-load next chapter)</button></div>')+
    sec('langs','🌐 Languages &amp; version order', langChips+ordList)+
    sec('studio','🎥 Studio', (function(){ const colnames=['Red','Orange','Yellow','Green','Blue','Indigo','Violet','Pink','White','🌈 Holographic'];
      const block=(id,label)=>{ const p=camPrefs(id); return '<div class="camblock"><div class="camblbl">'+label+'</div><div class="setrow" style="flex-wrap:wrap;gap:8px">'+
        '<button class="favchip cam_color" data-cam="'+id+'">Border: '+colnames[p.color%10]+'</button>'+
        '<button class="favchip cam_form" data-cam="'+id+'">Shape: '+({round:'Round',land:'Landscape',port:'Portrait'}[p.form])+'</button>'+
        '<button class="favchip cam_mirror'+(p.mirror?' on':'')+'" data-cam="'+id+'">🪞 Mirror</button>'+
        '<button class="favchip cam_green'+(p.green?' on':'')+'" data-cam="'+id+'">🟩 Green-screen</button></div></div>'; };
      const bgRow='<div class="camblock"><div class="camblbl">🖼 Stream background</div>'+
        '<p class="setnote">Replaces the swimming fish behind the app while you stream — the header, verse and buttons stay visible. Pick one, or upload your own from your gallery.</p>'+
        '<div class="setrow" style="flex-wrap:wrap;gap:8px">'+
        '<button class="bgthumb fish bg_pick'+(a.studiobg===''?' on':'')+'" data-bg="" title="Holy fish">🐟</button>'+
        STUDIO_BGS.map(b=>'<button class="bgthumb bg_pick'+(a.studiobg===b[0]?' on':'')+'" data-bg="'+b[0]+'" title="'+b[1]+'" style="background-image:url(\''+b[0]+'\')"></button>').join('')+
        '<button class="bgthumb up'+(a.studiobg==='custom'?' on':'')+'" id="bg_upload" title="Upload your own">⬆</button>'+
        '<input type="file" id="bg_file" accept="image/*" style="display:none"></div></div>';
      const homeRow='<div class="setrow" style="margin-top:8px"><button class="favchip'+(a.homebtns===0?'':' on')+'" id="s_homebtns">🏠 Home-screen buttons</button>'+
        '<span class="setnote" style="margin:0">turn off for a clean screen while streaming</span></div>';
      return '<p class="setnote">The 🎥 button opens/closes the cameras. Front and back cameras have independent settings — they apply live.</p>'+
        block('cam','🤳 Front camera')+block('cam2','📷 Back camera')+bgRow+homeRow; })())+
    sec('packs','📦 Downloads &amp; packs',
      '<button class="connectbtn" id="dlall" style="margin:2px 0 10px">⬇ Download everything (offline)</button>'+
      '<p class="setnote">These download once and then work offline. Big packs (like all 120+ versions) can be a couple of gigabytes — about the size of one mobile game.</p>'+rows.join(''))+
    sec('sync','🖥️ Desktop &amp; GitHub sync',
      '<p class="setnote">Enter your PC’s <b>network address</b> (not localhost) &mdash; e.g. <b>http://192.168.1.20:41537</b>. Your phone and PC must be on the same Wi‑Fi, and the desktop must have <b>Network / LAN mode</b> turned on. <b>127.0.0.1 will not work</b> from a phone.</p>'+
      '<div class="setrow"><input id="deskurl" class="setinput" placeholder="http://192.168.x.x:41537" value="'+esc(deskUrl())+'"><button id="savedesk" class="connectbtn" style="width:auto;padding:9px 14px">Test &amp; save</button></div>'+
      '<button id="openfull" class="connectbtn" style="margin-top:10px">🖥️ Open the full desktop app (1:1) →</button>'+
      (function(){ if(!isMaster()) return '';   // master-only tooling — hidden for everyone else
        const g=ghCfg(); return '<div class="camblbl" style="margin-top:16px">☁️ GitHub vault (works anywhere, no Wi-Fi pairing)</div>'+
      '<p class="setnote">A <b>private</b> repo carries your profile, settings &amp; reading progress between desktop and phone. Your token is stored only on this device — passwords are never synced. Use a fine-grained token limited to the one repo (Contents: read &amp; write).</p>'+
      '<input id="ghrepo" class="setinput" placeholder="owner/repo" value="'+esc(g.repo)+'" style="margin-bottom:8px">'+
      '<input id="ghtok" class="setinput" type="password" placeholder="GitHub token (github_pat_… or ghp_…)" value="'+esc(g.token)+'" style="margin-bottom:8px">'+
      '<input id="ghpass" class="setinput" type="password" placeholder="Vault passphrase (encrypts everything end-to-end)" value="'+esc(g.pass)+'" style="margin-bottom:10px">'+
      '<div class="setrow"><button id="ghpull" class="connectbtn" style="width:auto;padding:9px 14px">⬇ Load from GitHub</button>'+
      '<button id="ghpush" class="connectbtn" style="width:auto;padding:9px 14px">⬆ Save to GitHub</button></div>'; })())+
    '<div class="cmdsec"><div class="cmdeye" id="verline">Version</div><p class="setnote">'+
      (function(){ const bv=window.__bundledVer||0; let ov=0; try{ ov=parseInt(localStorage.getItem('yb_ota_ver')||'0',10)||0; }catch(e){}
        const run=ov>bv?ov:bv;
        return '<b>App build '+(run||'unknown')+'</b>'+(ov>bv?' (self-updated over APK '+bv+')':'')+' · Study content v'+APP_CONTENT_VER; })()+
      ' · <button id="chkupd" class="miniupd">Check for updates</button> · <button id="s_reset" class="miniupd">Reset to defaults</button></p></div>'+
    '<button class="cmdback" id="cmdback">◀ back</button></div>');
  // section accordions remember their open state across re-renders
  $('#view').querySelectorAll('.setsec>.accbtn').forEach(ab=>ab.onclick=()=>{ const p=ab.parentElement;
    p.classList.toggle('open'); OPEN[p.dataset.sec]=p.classList.contains('open'); });
  $('#view').querySelectorAll('.backbtn,#cmdback').forEach(b=>b.onclick=()=>nav('bible'));
  const cu=$('#chkupd'); if(cu) cu.onclick=()=>checkUpdates(false).then(()=>openSettings());
  const au=$('#applyupd'); if(au) au.onclick=()=>applyContentUpdate();
  const sd=$('#savedesk'); if(sd) sd.onclick=async()=>{ const u=$('#deskurl').value.trim(); try{localStorage.setItem(DESK_KEY,u);}catch(e){}
    if(u){ toast('Testing connection…'); const ok=await pingDesktop(u); toast(ok?'✓ Connected to your desktop':'✗ Could not reach it — see the note below'); } };
  const of=$('#openfull'); if(of) of.onclick=async()=>{ const u=normUrl(deskUrl()); if(!u){ toast('Enter your desktop address first'); return; }
    toast('Opening the full app…'); const ok=await pingDesktop(u); if(ok){ showDesktop(u); } else { toast('✗ Desktop not reachable — check Wi-Fi & the address'); } };
  const _ghSave=()=>{ const c=ghCfg(); c.repo=($('#ghrepo')?$('#ghrepo').value.trim():c.repo)||c.repo;
    c.token=$('#ghtok')?$('#ghtok').value.trim():c.token;
    c.pass=$('#ghpass')?$('#ghpass').value.trim():c.pass; setGhCfg(c); };
  const gp=$('#ghpull'); if(gp) gp.onclick=async()=>{ _ghSave(); if(!ghCfg().token){ toast('Paste your GitHub token first'); return; }
    gp.disabled=true; toast('Loading from GitHub…'); await ghPull(false); gp.disabled=false; };
  const gq=$('#ghpush'); if(gq) gq.onclick=async()=>{ _ghSave(); if(!ghCfg().token){ toast('Paste your GitHub token first'); return; }
    gq.disabled=true; toast('Saving to GitHub…'); await ghPush(); gq.disabled=false; };
  const si=$('#dosignin'); if(si) si.onclick=async()=>{ const n=$('#lg_name').value.trim(), e=$('#lg_email').value.trim(), pw=$('#lg_pw').value;
    if(!n&&!e){ toast('Enter a name or email'); return; }
    const u=deskUrl();
    // one identity across devices: the Zion'iel Network node is the registry — it decides
    // whether the name/email is free, taken, or yours (sign-in with the right password)
    if(u && await pingDesktop(u)){
      toast('Checking the Zion’iel Network…');
      const r=await desktopLogin(u,n||e,pw,e);
      if(r.ok){ setAccount({name:n||e,email:e,desktop:u,synced:true}); toast('✓ Signed in & synced across your devices'); openSettings(); return; }
      const msg=(r.error||'').toLowerCase();
      if(msg.indexOf('taken')>=0||msg.indexOf('in use')>=0||msg.indexOf('wrong')>=0||msg.indexOf('password')>=0){
        toast('✗ '+(r.error||'sign-in failed')); return; }   // conflict: never shadow a taken identity locally
      toast(r.error||'Network error — signed in on this device only');
      setAccount({name:n,email:e,unverified:true}); openSettings(); return;
    }
    // node unreachable: local account, clearly marked unverified until the network can check it
    setAccount({name:n,email:e,unverified:true});
    toast('Signed in on this device — the name will be claimed on the Zion’iel Network when your desktop is reachable');
    openSettings(); };
  const gg=$('#doguest'); if(gg) gg.onclick=()=>{ setAccount({name:'Guest',guest:true}); openSettings(); };
  const so=$('#signout'); if(so) so.onclick=()=>{ setAccount(null); toast('Signed out'); openSettings(); };
  const sh=$('#s_hue'); if(sh) sh.oninput=()=>setAppSetting('hue',+sh.value);
  const sf=$('#s_fish'); if(sf) sf.oninput=()=>setAppSetting('fishvis',+sf.value);
  const sr=$('#s_reader'); if(sr) sr.oninput=()=>setAppSetting('reader',+sr.value);
  const shb=$('#s_heb'); if(shb) shb.oninput=()=>setAppSetting('hebsize',+shb.value);
  const sco=$('#s_centerop'); if(sco) sco.oninput=()=>setAppSetting('centerop',+sco.value);
  const smt=$('#s_menutrans'); if(smt) smt.oninput=()=>setAppSetting('menutrans',+smt.value);
  const shr=$('#s_hrandsel'); if(shr) shr.onchange=()=>setAppSetting('huerand',+shr.value);
  const sqs=$('#s_qsecs'); if(sqs) sqs.onchange=()=>setAppSetting('quotesecs',Math.max(5,+sqs.value||7));
  const sbg=$('#s_showbg'); if(sbg) sbg.onclick=()=>{ setAppSetting('showbg', appSettings().showbg?0:1); sbg.classList.toggle('on'); };
  const sct=$('#s_cont'); if(sct) sct.onclick=()=>{ setAppSetting('contscroll', +appSettings().contscroll?0:1); sct.classList.toggle('on'); };
  const srs=$('#s_reset'); if(srs) srs.onclick=()=>{ try{localStorage.removeItem('yb_app_settings');}catch(e){} applyAppSettings(); toast('Settings reset'); openSettings(); };
  // hidden master unlock: 7 taps on the Version label toggles the vault tooling
  const vl=$('#verline'); if(vl){ let taps=0,t0=0; vl.onclick=()=>{ const now=Date.now();
    if(now-t0>2500) taps=0; t0=now; taps++;
    if(taps>=7){ taps=0; const on=(function(){try{return localStorage.getItem('yb_master')==='1';}catch(e){return false;}})();
      try{ localStorage.setItem('yb_master', on?'0':'1'); }catch(e){}
      toast(on?'Master tools hidden':'👑 Master tools revealed'); openSettings(); } }; }
  $('#view').querySelectorAll('.s_theme').forEach(bt=>bt.onclick=()=>{ setAppSetting('theme',bt.dataset.t);
    $('#view').querySelectorAll('.s_theme.on').forEach(x=>x.classList.remove('on')); bt.classList.add('on'); });
  $('#view').querySelectorAll('.s_olc').forEach(bt=>bt.onclick=()=>{ setAppSetting('olc',bt.dataset.m);
    $('#view').querySelectorAll('.s_olc.on').forEach(x=>x.classList.remove('on')); bt.classList.add('on'); });
  $('#view').querySelectorAll('.s_lang').forEach(bt=>bt.onclick=()=>{ const l=bt.dataset.l; if(l==='English') return;
    const s=appSettings(); const i=s.langs.indexOf(l); if(i>=0)s.langs.splice(i,1); else s.langs.push(l);
    setAppSetting('langs',s.langs); openSettings(); });
  $('#view').querySelectorAll('.vlcv').forEach(bt=>bt.onclick=()=>{ let f=favVersions(); const v=bt.dataset.v;
    const i=f.indexOf(v); if(i>=0)f.splice(i,1); else { if(f.length>=7){ toast('Up to 7 versions in the stack'); return; } f.push(v); }
    try{localStorage.setItem('yb_fav_versions',JSON.stringify(f));}catch(e){} bt.classList.toggle('on'); });
  $('#view').querySelectorAll('.voeye').forEach(bt=>bt.onclick=()=>{ const c=bt.parentElement.dataset.v; const s=appSettings();
    const i=s.hidden.indexOf(c); if(i>=0)s.hidden.splice(i,1); else s.hidden.push(c);
    setAppSetting('hidden',s.hidden); bt.classList.toggle('off'); });
  $('#view').querySelectorAll('.vomv').forEach(bt=>bt.onclick=()=>{ const row=bt.parentElement, c=row.dataset.v, d=+bt.dataset.d;
    const box=$('#vorder'); const rowsEls=[...box.querySelectorAll('.vorow')]; const i=rowsEls.indexOf(row); const j=i+d;
    if(j<0||j>=rowsEls.length) return;
    if(d<0) box.insertBefore(row,rowsEls[j]); else box.insertBefore(rowsEls[j],row);
    setAppSetting('verorder',[...box.querySelectorAll('.vorow')].map(r=>r.dataset.v)); });
  $('#view').querySelectorAll('.cam_color').forEach(bt=>bt.onclick=()=>{ const id=bt.dataset.cam; const p=camPrefs(id); p.color=(p.color+1)%CAMCOLORS.length; setCamPrefs(id,p); openSettings(); });
  $('#view').querySelectorAll('.cam_form').forEach(bt=>bt.onclick=()=>{ const id=bt.dataset.cam; const p=camPrefs(id); const o=['round','land','port']; p.form=o[(o.indexOf(p.form)+1)%3]; setCamPrefs(id,p); openSettings(); });
  $('#view').querySelectorAll('.cam_mirror').forEach(bt=>bt.onclick=()=>{ const id=bt.dataset.cam; const p=camPrefs(id); p.mirror=!p.mirror; setCamPrefs(id,p); bt.classList.toggle('on'); });
  $('#view').querySelectorAll('.cam_green').forEach(bt=>bt.onclick=()=>{ const id=bt.dataset.cam; const p=camPrefs(id); p.green=!p.green; setCamPrefs(id,p); bt.classList.toggle('on'); });
  $('#view').querySelectorAll('.bg_pick').forEach(bt=>bt.onclick=()=>{ setAppSetting('studiobg',bt.dataset.bg);
    $('#view').querySelectorAll('.bgthumb.on').forEach(x=>x.classList.remove('on')); bt.classList.add('on'); });
  const bu=$('#bg_upload'), bf=$('#bg_file');
  if(bu&&bf){ bu.onclick=()=>bf.click(); bf.onchange=()=>{ if(bf.files&&bf.files[0]) uploadStudioBg(bf.files[0]); }; }
  const hb=$('#s_homebtns'); if(hb) hb.onclick=()=>{ const a=appSettings(); setAppSetting('homebtns', a.homebtns===0?1:0); hb.classList.toggle('on'); };
  const dla=$('#dlall'); if(dla) dla.onclick=()=>downloadEverything();
  wirePackRows();
}
/* ---------- reading progress: a chapter counts as read once opened and scrolled through ---------- */
function readProg(){ try{ return JSON.parse(localStorage.getItem('yb_read')||'{}'); }catch(e){ return {}; } }
function markRead(bi,ch){ const b=KJV.books[bi]; if(!b) return; const p=readProg();
  (p[b.a]=p[b.a]||{})[ch]=1; try{ localStorage.setItem('yb_read',JSON.stringify(p)); }catch(e){} }
let _readWatchFn=null;
function watchReadThrough(bi,ch){ const v=$('#view'); if(!v) return;
  if(_readWatchFn){ v.removeEventListener('scroll',_readWatchFn); _readWatchFn=null; }
  const done=()=>{ markRead(bi,ch); if(_readWatchFn){ v.removeEventListener('scroll',_readWatchFn); _readWatchFn=null; } };
  setTimeout(()=>{ if(!_rd||_rd.bi!==bi||_rd.ch!==ch) return;      // navigated away already
    if(v.scrollHeight<=v.clientHeight+40){ done(); return; }        // fits on one screen = read on open
    _readWatchFn=()=>{ if(v.scrollTop+v.clientHeight>=v.scrollHeight-60) done(); };
    v.addEventListener('scroll',_readWatchFn,{passive:true}); },400); }
/* continuous scroll (desktop parity): reaching the bottom auto-loads the next chapter in place */
let _contFn=null,_contBusy=false;
function watchContinuous(bi){ const v=$('#view'); if(!v) return;
  if(_contFn){ v.removeEventListener('scroll',_contFn); _contFn=null; }
  if(!+appSettings().contscroll) return;
  _contFn=()=>{ if(_contBusy) return;
    if(v.scrollTop+v.clientHeight>=v.scrollHeight-140) appendNextChapter(bi); };
  v.addEventListener('scroll',_contFn,{passive:true}); }
function appendNextChapter(bi){ const b=KJV.books[bi]; if(!b||!_rd||_rd.bi!==bi) return;
  const nch=_rd.ch+1; if(nch>b.ch.length) return;
  _contBusy=true;
  markRead(bi,_rd.ch);                                  // the current chapter was scrolled through
  const verses=b.ch[nch-1]||[];
  const rb=$('#rdbody'); if(!rb){ _contBusy=false; return; }
  const wrap=document.createElement('div');
  wrap.innerHTML='<div class="rchap">'+esc(b.n)+' '+nch+'</div>'+
    verses.map((tx,i)=>'<p class="rv" id="rvc'+nch+'_'+(i+1)+'"><span class="rvn">'+(i+1)+'</span>'+wordize(tx,i+1)+'</p>').join('');
  rb.appendChild(wrap);
  wrap.querySelectorAll('.rvn').forEach(n=>n.onclick=e=>{ e.stopPropagation();
    selectVerse(bi,nch,+n.parentElement.id.split('_')[1]); });
  wrap.querySelectorAll('.rw').forEach(w=>w.onclick=e=>{ e.stopPropagation(); tapWord(b,nch,+w.dataset.v,w.textContent,w); });
  _rd.ch=nch; const t=document.querySelector('#view .rdttl'); if(t)t.textContent=b.n+' '+nch;
  watchReadThrough(bi,nch);
  setTimeout(()=>{ _contBusy=false; },300); }
function progressStats(){ const p=readProg(); const g={torah:[0,0],ot:[0,0],nt:[0,0],all:[0,0]};
  KJV.books.forEach((b,i)=>{ const read=Object.keys(p[b.a]||{}).length, tot=b.ch.length;
    const grp=i<5?'torah':(b.t==='OT'?'ot':'nt');
    g[grp][0]+=Math.min(read,tot); g[grp][1]+=tot; g.all[0]+=Math.min(read,tot); g.all[1]+=tot; });
  return g; }
/* ---------- profile: picture, name, bio, progress, and the sync status ---------- */
function profileData(){ try{ return JSON.parse(localStorage.getItem('yb_profile')||'{}'); }catch(e){ return {}; } }
function setProfileData(p){ try{ localStorage.setItem('yb_profile',JSON.stringify(p)); }catch(e){} }
function openProfile(){ closeDrawers(); clearInterval(_qTimer);
  const acct=getAccount(), prof=profileData(), g=progressStats();
  let av=''; try{ av=localStorage.getItem('yb_avatar')||''; }catch(e){}
  const bar=(lbl,d)=>{ const pc=d[1]?Math.round(d[0]/d[1]*100):0;
    return '<div class="pgrow"><span class="pglbl">'+lbl+'</span><div class="pgbar"><span style="width:'+pc+'%"></span></div>'+
      '<span class="pgpc">'+pc+'%<small>'+d[0]+'/'+d[1]+'</small></span></div>'; };
  setView('<div class="screen study"><button class="backbtn" data-back="home">◀ back</button>'+
    '<div class="cmdno">You</div><h2 class="cmdttl">Profile</h2>'+
    '<div class="cmdsec"><div class="profhead">'+
      '<button class="profav" id="profav" title="Tap to change your picture">'+
        (av?'<img src="'+av+'" alt="">':'<span>'+esc(((acct&&(acct.name||acct.email))||'Y')[0].toUpperCase())+'</span>')+'</button>'+
      '<input type="file" id="avfile" accept="image/*" style="display:none">'+
      '<div class="profwho"><div class="acctname">'+esc((acct&&(acct.name||acct.email))||'Guest')+'</div>'+
        '<div class="acctsub">'+esc((acct&&acct.email)||'on this device')+'</div></div></div>'+
      '<textarea id="profbio" class="setinput" rows="2" placeholder="A line about you…" style="margin-top:10px;resize:none">'+esc(prof.bio||'')+'</textarea></div>'+
    '<div class="cmdsec"><div class="cmdeye">Reading progress</div><h3>How much of the Word you\'ve read</h3>'+
      '<p class="setnote">A chapter counts once you\'ve opened it and read it through to the end.</p>'+
      bar('The Torah',g.torah)+bar('Old Testament',g.ot)+bar('New Testament',g.nt)+bar('The whole Bible',g.all)+'</div>'+
    '<div class="cmdsec"><div class="cmdeye">The Zion\'iel Network</div><h3>Sync</h3><div id="syncstate">'+
      '<div class="syncrow"><span class="syncdot on"></span>This phone — your notes, progress &amp; profile live here</div>'+
      '<div class="syncrow" id="syncdesk"><span class="syncdot"></span>Desktop — checking…</div></div>'+
      (acct?'':'<p class="setnote">Sign in (Settings → Account) to carry your progress across devices.</p>')+'</div>'+
    '<button class="cmdback" id="pfback">◀ back</button></div>');
  $('#view').querySelectorAll('.backbtn,#pfback').forEach(b=>b.onclick=()=>nav('home'));
  const bio=$('#profbio'); if(bio) bio.onchange=()=>{ const p=profileData(); p.bio=bio.value.slice(0,300); setProfileData(p); toast('✓ Saved'); };
  const pa=$('#profav'), af=$('#avfile');
  if(pa&&af){ pa.onclick=()=>af.click(); af.onchange=()=>{ const f=af.files&&af.files[0]; if(!f) return;
    const rd=new FileReader(); rd.onload=()=>{ const img=new Image(); img.onload=()=>{
      const c=document.createElement('canvas'); const M=256, sc=Math.max(M/img.width,M/img.height);
      c.width=M; c.height=M; const w=img.width*sc,h=img.height*sc;
      c.getContext('2d').drawImage(img,(M-w)/2,(M-h)/2,w,h);
      const durl=c.toDataURL('image/jpeg',.85);
      try{ localStorage.setItem('yb_avatar',durl); }catch(e){ toast('Picture too large to store'); return; }
      openProfile(); }; img.src=rd.result; }; rd.readAsDataURL(f); }; }
  // the desktop half of the two-way indicator
  (async()=>{ const row=$('#syncdesk'); if(!row) return; const u=normUrl(deskUrl());
    if(!u){ row.innerHTML='<span class="syncdot"></span>Desktop — not set up (Settings → Sync)'; return; }
    const ok=await pingDesktop(u);
    row.innerHTML= ok
      ? '<span class="syncdot on"></span>Desktop at '+esc(u.replace(/^https?:\/\//,''))+' — <b>sync established</b>'
      : '<span class="syncdot off"></span>Desktop at '+esc(u.replace(/^https?:\/\//,''))+' — not reachable right now'; })();
}
/* ---------- GitHub sync: a PRIVATE repo carries profile/settings/progress across devices.
   The token is entered on THIS device and stored only here — never bundled, never uploaded.
   Credentials (passwords) are NEVER written to the repo. ---------- */
function ghCfg(){ try{ return Object.assign({repo:'OhBeOneKeyNoBe/YahBible-Sync',token:'',pass:''}, JSON.parse(localStorage.getItem('yb_gh')||'{}')); }catch(e){ return {repo:'OhBeOneKeyNoBe/YahBible-Sync',token:'',pass:''}; } }
/* vault end-to-end encryption (AES-256-GCM, PBKDF2 200k) — same scheme as the desktop, so
   even a leaked repo + token yields only ciphertext. The passphrase lives on this device. */
function _buf2b64(b){ let s=''; new Uint8Array(b).forEach(x=>s+=String.fromCharCode(x)); return btoa(s); }
function _b642buf(s){ return Uint8Array.from(atob(s),c=>c.charCodeAt(0)); }
async function _vaultKey(pass,salt){ const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pass),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt:salt,iterations:200000,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['encrypt','decrypt']); }
async function vaultEncrypt(obj){ const p=ghCfg().pass; if(!p) return obj;
  const salt=crypto.getRandomValues(new Uint8Array(16)), iv=crypto.getRandomValues(new Uint8Array(12));
  const key=await _vaultKey(p,salt);
  const ct=await crypto.subtle.encrypt({name:'AES-GCM',iv:iv,additionalData:new TextEncoder().encode('yahbible-vault')},key,new TextEncoder().encode(JSON.stringify(obj)));
  return {enc:1,kind:obj.kind||'yahbible-sync',salt:_buf2b64(salt),iv:_buf2b64(iv),ct:_buf2b64(ct)}; }
async function vaultDecrypt(obj){ if(!obj||!obj.enc) return obj;
  const p=ghCfg().pass; if(!p) throw new Error('the vault is encrypted — enter the vault passphrase');
  const key=await _vaultKey(p,_b642buf(obj.salt));
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:_b642buf(obj.iv),additionalData:new TextEncoder().encode('yahbible-vault')},key,_b642buf(obj.ct))
    .catch(()=>{ throw new Error('wrong vault passphrase'); });
  return JSON.parse(new TextDecoder().decode(pt)); }
/* the vault is MASTER-ONLY tooling: shown for the creator's identity, or on a device that
   already carries a token, or after the hidden unlock (7 taps on the Version line) */
const MASTER_IDS=['yahwehtsidkenu','@yahwehtsidkenu','virtuousdeity@proton.me','virtuousdeity@gmail.com',"elan'iel",'elaniel'];
function isMaster(){ try{ if(localStorage.getItem('yb_master')==='1') return true; }catch(e){}
  if(ghCfg().token) return true;
  const a=getAccount(); if(!a) return false;
  const ids=[(a.name||''),(a.email||'')].map(s=>s.toLowerCase().trim());
  return MASTER_IDS.some(m=>ids.indexOf(m)>=0); }
function setGhCfg(c){ try{ localStorage.setItem('yb_gh',JSON.stringify(c)); }catch(e){} }
function ghFile(){ const a=getAccount(); const u=((a&&(a.name||a.email))||'default').toLowerCase().replace(/[^a-z0-9_.-]/g,'_'); return 'sync/'+u+'.json'; }
async function ghReq(method,body){ const c=ghCfg(); if(!c.token) throw new Error('no token');
  const url='https://api.github.com/repos/'+c.repo+'/contents/'+ghFile();
  const r=await fetch(url,{method:method,headers:{'Authorization':'Bearer '+c.token,'Accept':'application/vnd.github+json'},
    body:body?JSON.stringify(body):undefined});
  if(r.status===404) return null;
  if(!r.ok){ let msg=''; try{ msg=(await r.json()).message||''; }catch(e){}
    // say WHY, in plain words, instead of a bare status number
    if(r.status===401) msg='bad or expired token — paste it again';
    else if(r.status===403&&/rate limit/i.test(msg)) msg='GitHub rate limit — wait a minute';
    else if(r.status===403) msg=(msg||'forbidden')+' — the token needs Contents: Read & write on '+c.repo;
    throw new Error('GitHub '+r.status+(msg?(': '+msg):'')); }
  return r.json(); }
function _b64e(s){ return btoa(unescape(encodeURIComponent(s))); }
function _b64d(s){ return decodeURIComponent(escape(atob((s||'').replace(/\n/g,'')))); }
/* mobile yb_read {Gen:{3:1}} <-> canonical desktop refs ["Genesis|3"] */
function progToRefs(){ const p=readProg(), out=[];
  KJV.books.forEach(b=>{ Object.keys(p[b.a]||{}).forEach(ch=>out.push(b.n+'|'+ch)); });
  let extra=[]; try{ extra=JSON.parse(localStorage.getItem('yb_read_extra')||'[]'); }catch(e){}
  return out.concat(extra); }
function refsToProg(refs){ const byName={}; KJV.books.forEach(b=>byName[b.n]=b.a);
  const p=readProg(); const extra=new Set(); let known=0;
  (refs||[]).forEach(r=>{ const i=r.indexOf('|'); if(i<0) return;
    const bk=r.slice(0,i), rest=r.slice(i+1);
    if(byName[bk]&&/^\d+$/.test(rest)){ (p[byName[bk]]=p[byName[bk]]||{})[rest]=1; known++; }
    else extra.add(r); });   // apocrypha/desktop-only refs: preserved for round-trip
  try{ localStorage.setItem('yb_read',JSON.stringify(p)); localStorage.setItem('yb_read_extra',JSON.stringify([...extra])); }catch(e){}
  return known; }
async function ghPull(quiet){
  try{
    const f=await ghReq('GET'); if(!f){ if(!quiet) toast('Nothing in the vault yet — Save first'); return false; }
    let d=JSON.parse(_b64d(f.content)); d=await vaultDecrypt(d);
    if(!d||d.kind!=='yahbible-sync') throw new Error('bad file');
    if(d.profile){ const pr=profileData();
      if(d.profile.bio!=null) pr.bio=d.profile.bio; setProfileData(pr);
      if(d.profile.avatar){ try{ localStorage.setItem('yb_avatar',d.profile.avatar); }catch(e){} }
      const a=getAccount(); if(d.profile.name&&(!a||!a.name)) setAccount(Object.assign(a||{},{name:d.profile.name})); }
    if(d.settings){ try{ const cur=appSettings(); localStorage.setItem('yb_app_settings',JSON.stringify(Object.assign(cur,d.settings))); }catch(e){} applyAppSettings(); }
    if(d.favs&&d.favs.length){ try{ localStorage.setItem('yb_fav_versions',JSON.stringify(d.favs)); }catch(e){} }
    const n=refsToProg(d.progress);
    if(!quiet) toast('✓ Loaded from GitHub — '+n+' chapters of progress');
    return true;
  }catch(e){ if(!quiet) toast('GitHub load failed: '+(e.message||'')); return false; }
}
async function ghPush(){
  try{
    const f=await ghReq('GET');                       // merge over what's there — never clobber
    let base={}; if(f){ try{ base=JSON.parse(_b64d(f.content))||{}; }catch(e){ base={}; } }
    base=await vaultDecrypt(base);                    // throws on wrong passphrase — never clobber blind
    const a=getAccount(), pr=profileData();
    let av=''; try{ av=localStorage.getItem('yb_avatar')||''; }catch(e){}
    base.kind='yahbible-sync'; base.ts=Date.now();
    base.profile=Object.assign(base.profile||{},{name:(a&&(a.name||a.email))||'',bio:pr.bio||''});
    if(av) base.profile.avatar=av;
    base.settings=appSettings();
    base.favs=favVersions();
    base.progress=[...new Set((base.progress||[]).concat(progToRefs()))];
    const body={message:'YahBible mobile sync',content:_b64e(JSON.stringify(await vaultEncrypt(base)))};
    if(f&&f.sha) body.sha=f.sha;
    await ghReq('PUT',body);
    toast('✓ Saved to GitHub ('+base.progress.length+' progress refs)');
    return true;
  }catch(e){ toast('GitHub save failed: '+(e.message||'')); return false; }
}
function normUrl(u){ u=(u||'').trim(); if(!u) return ''; if(!/^https?:\/\//.test(u)) u='http://'+u; return u.replace(/\/+$/,''); }
async function pingDesktop(u){ u=normUrl(u); let ok=false;
  try{ const r=await fetch(u+'/api/status',{cache:'no-store'}); ok=r.ok; }
  catch(e){ try{ await fetch(u+'/',{mode:'no-cors'}); ok=true; }catch(e2){ ok=false; } }
  if(ok){ // tell the desktop this phone is here, so ITS sync light turns on too
    const a=getAccount(); const nm=(a&&(a.name||a.email))||'YahBible mobile';
    try{ fetch(u+'/api/mobile_ping?name='+encodeURIComponent(nm),{cache:'no-store'}).catch(()=>{}); }catch(e){} }
  return ok; }
async function desktopLogin(u,user,pw,email){ u=normUrl(u);
  try{ const r=await fetch(u+'/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pw})});
    const d=await r.json().catch(()=>({})); if(d&&d.ok!==false){ try{localStorage.setItem('yb_desk_token',d.token||d.session||'');}catch(e){} return {ok:true}; }
    // try signup if login failed — the EMAIL travels too, so the registry can enforce it
    const r2=await fetch(u+'/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pw,email:(email||'')||(user.indexOf('@')>0?user:'')})});
    const d2=await r2.json().catch(()=>({})); if(d2&&d2.ok!==false) return {ok:true};
    let err=(d2&&d2.error)||'sign-in failed';
    if(/taken/i.test(err)) err='That name exists on the Zion’iel Network — wrong password? (or pick another name)';
    return {ok:false,error:err};
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
    btn.classList.add('on'); applyCamPrefs();
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
function initCamDrag(){ initCamWin($('#cam')); initCamWin($('#cam2')); }
/* camera prefs live in Settings (not on the video). They persist + apply to both windows. */
/* per-camera prefs: {cam:{...}, cam2:{...}} so front and back are independent */
function _camAll(){ try{ return JSON.parse(localStorage.getItem('yb_cam_prefs')||'{}'); }catch(e){ return {}; } }
function camPrefs(id){ id=id||'cam'; const all=_camAll();
  const dflt=(id==='cam')?{color:6,form:'round',mirror:false,green:false}:{color:4,form:'round',mirror:true,green:false};
  return Object.assign(dflt, all[id]||{}); }
/* app appearance settings (parity with desktop: accent hue, background/fish visibility, reader size, hue randomize) */
function appSettings(){ const d={hue:270,fishvis:22,reader:17,huerand:0,studiobg:'',homebtns:1,
    theme:'night',hebsize:19,quotesecs:7,menutrans:0,centerop:100,showbg:1,contscroll:0,olc:'both',
    langs:['English'],verorder:[],hidden:[]};
  try{ const s=Object.assign(d, JSON.parse(localStorage.getItem('yb_app_settings')||'{}'));
    if(!Array.isArray(s.langs)||!s.langs.length)s.langs=['English'];
    if(!Array.isArray(s.verorder))s.verorder=[]; if(!Array.isArray(s.hidden))s.hidden=[];
    return s; }catch(e){ return d; } }
let _hueTimer=null;
function applyAppSettings(){ const s=appSettings(); const r=document.documentElement;
  r.style.setProperty('--hue', s.hue);
  // theme (desktop parity): night is the base; parchment/sepia swap the whole palette
  if(s.theme&&s.theme!=='night') document.body.dataset.theme=s.theme; else delete document.body.dataset.theme;
  // fishvis (0..70 in the slider) maps to --bgvis (0..~2.3): the whole school + flowers scale together
  const fbg=$('#fishbg'); if(fbg){ fbg.style.setProperty('--bgvis', (s.fishvis/30).toFixed(3));
    fbg.style.display = s.showbg?'':'none'; }
  applyStudioBg(s);
  r.style.setProperty('--reader', s.reader+'px');
  r.style.setProperty('--hebsize', s.hebsize+'px');
  r.style.setProperty('--menuop', (1-(+s.menutrans||0)/100).toFixed(3));
  r.style.setProperty('--veil', ((100-(+s.centerop||100))/100).toFixed(3));
  clearInterval(_hueTimer);
  if(+s.huerand>0){ _hueTimer=setInterval(()=>{ const cur=appSettings(); cur.hue=(cur.hue+37)%360; try{localStorage.setItem('yb_app_settings',JSON.stringify(cur));}catch(e){} document.documentElement.style.setProperty('--hue',cur.hue); }, +s.huerand*1000); } }
function setAppSetting(k,v){ const s=appSettings(); s[k]=v; try{localStorage.setItem('yb_app_settings',JSON.stringify(s));}catch(e){} applyAppSettings(); }
/* studio stream background: '' = the holy-fish school; a preset path; or 'custom' (stored in IndexedDB) */
async function applyStudioBg(s){ const fbg=$('#fishbg'); if(!fbg) return;
  let url='';
  if(s.studiobg==='custom'){ try{ url=await YBPacks.idbGet('studio:bg')||''; }catch(e){ url=''; } }
  else if(s.studiobg) url=s.studiobg;
  if(url){ fbg.classList.add('studio'); fbg.style.backgroundImage='url("'+url+'")'; }
  else { fbg.classList.remove('studio'); fbg.style.backgroundImage=''; } }
const STUDIO_BGS=[['assets/studio/golden-dawn.jpg','Golden Dawn'],['assets/studio/deep-waters.jpg','Deep Waters'],
  ['assets/studio/starry-heavens.jpg','Starry Heavens'],['assets/studio/royal-violet.jpg','Royal Violet']];
function uploadStudioBg(file){ const rd=new FileReader();
  rd.onload=()=>{ const img=new Image();
    img.onload=()=>{ const M=1440, sc=Math.min(1, M/Math.max(img.width,img.height));
      const c=document.createElement('canvas'); c.width=Math.round(img.width*sc); c.height=Math.round(img.height*sc);
      c.getContext('2d').drawImage(img,0,0,c.width,c.height);
      const durl=c.toDataURL('image/jpeg',.82);
      YBPacks.idbPut('studio:bg',durl).then(()=>{ setAppSetting('studiobg','custom'); toast('✓ Stream background set'); openSettings(); })
        .catch(()=>toast('Could not store the image')); };
    img.onerror=()=>toast('Could not read that image'); img.src=rd.result; };
  rd.onerror=()=>toast('Could not read that file'); rd.readAsDataURL(file); }
function setCamPrefs(id,p){ const all=_camAll(); all[id]=p; try{ localStorage.setItem('yb_cam_prefs',JSON.stringify(all)); }catch(e){} applyCamPrefs(); }
function applyCamPrefs(){ ['cam','cam2'].forEach(id=>{ const c=$('#'+id); if(!c)return; const p=camPrefs(id);
  const col=CAMCOLORS[p.color%CAMCOLORS.length]; c.classList.toggle('holoborder',col==='holo'); if(col!=='holo')c.style.borderColor=col;
  ['round','land','port'].forEach(f=>c.classList.toggle('cf-'+f, f===p.form));
  c.classList.toggle('mirror',!!p.mirror); c.classList.toggle('green',!!p.green); }); }

/* ---------- holy-fish background: a school of swimming fish + Flower-of-Life seeds (1:1 desktop) ---------- */
function flowerSVG(size,opacity){const round=v=>(Math.round(v*100)/100).toFixed(2);
  const R=size/6,C=size/2,st=Math.min(opacity*1.25,1),cs=[[C,C]];
  for(let i=0;i<6;i++){const a=i*60*Math.PI/180;cs.push([C+R*Math.cos(a),C+R*Math.sin(a)]);}
  for(let i=0;i<6;i++){const a=i*60*Math.PI/180;cs.push([C+R*2*Math.cos(a),C+R*2*Math.sin(a)]);
    const o=(i*60+30)*Math.PI/180;cs.push([C+R*Math.sqrt(3)*Math.cos(o),C+R*Math.sqrt(3)*Math.sin(o)]);}
  const gid='g'+Math.floor(size*1000%99999);
  let s='<svg width="'+size+'" height="'+size+'" viewBox="0 0 '+size+' '+size+'"><defs><linearGradient id="'+gid+'" x1="0" y1="0" x2="1" y2="1">'+
    '<stop offset="0%" stop-color="hsl(0 95% 65%)" stop-opacity="'+st+'"/><stop offset="16%" stop-color="hsl(25 100% 60%)" stop-opacity="'+st+'"/>'+
    '<stop offset="33%" stop-color="hsl(45 100% 65%)" stop-opacity="'+st+'"/><stop offset="50%" stop-color="hsl(140 80% 50%)" stop-opacity="'+st+'"/>'+
    '<stop offset="66%" stop-color="hsl(210 100% 60%)" stop-opacity="'+st+'"/><stop offset="83%" stop-color="hsl(260 90% 65%)" stop-opacity="'+st+'"/>'+
    '<stop offset="100%" stop-color="hsl(280 95% 70%)" stop-opacity="'+st+'"/></linearGradient></defs>';
  for(const c of cs)s+='<circle cx="'+round(c[0])+'" cy="'+round(c[1])+'" r="'+round(R)+'" fill="none" stroke="url(#'+gid+')" stroke-width="1.5"/>';
  return s+'</svg>';}
function buildBg(){ const fl=$('#flowers'), fw=$('#fishes'); if(!fl||!fw||fl.childElementCount) return;
  const flowers=[[80,10,15,45,0,.08,30,20,25],[150,60,5,60,1,.10,-25,35,30],[50,80,40,35,0,.06,20,-15,20],
    [200,20,55,80,1,.12,-35,25,40],[60,70,75,40,0,.07,25,-20,22],[120,5,85,55,1,.09,-20,30,28],
    [90,45,30,50,0,.08,30,-25,35],[70,85,60,42,1,.07,-15,20,18]];
  flowers.forEach(f=>{const sz=f[0],x=f[1],y=f[2],dur=f[3],rev=f[4],op=f[5],dx=f[6],dy=f[7],dd=f[8];
    const w=document.createElement('div'); w.className='flower';
    w.style.cssText='left:'+x+'%;top:'+y+'%;--dx:'+dx+'px;--dy:'+dy+'px;animation:drift '+dd+'s ease-in-out infinite alternate';
    const inner=document.createElement('div'); inner.innerHTML=flowerSVG(sz,op);
    inner.firstChild.style.animation='rotslow '+dur+'s linear infinite'+(rev?' reverse':'');
    w.appendChild(inner); fl.appendChild(w);});
  const fish=[[12,8],[18,22],[24,35],[32,48],[40,58],[52,68],[65,78],[14,82],[20,88],[28,72],[16,92],[22,65]];
  fish.forEach((f,i)=>{const sz=f[0],y=f[1],dir=i%2?1:-1,speed=15+((i*7)%30);
    const d=document.createElement('div'); d.className='fish';
    d.style.cssText='width:'+sz+'px;top:'+y+'%;animation:'+(dir>0?'swimR':'swimL')+' '+speed+'s linear infinite;animation-delay:-'+((i*3)%speed)+'s';
    d.innerHTML='<img src="assets/holy-fish.png" alt="">'; fw.appendChild(d);});
}
/* ---------- boot ---------- */
window.addEventListener('DOMContentLoaded',()=>{
  buildBg();
  if(newsUnseen()){ const n=document.querySelector('.tab[data-tab="news"]'); if(n){ const d=document.createElement('span'); d.className='dot'; d.id='newsdot'; n.appendChild(d); } }
  document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>nav(b.dataset.tab==='repent'?'repentance':b.dataset.tab));
  $('#cambtn').onclick=toggleCam;
  $('#leftmenubtn').onclick=()=>openDrawer('left');
  $('#rightmenubtn').onclick=()=>openDrawer('right');
  $('#scrim').onclick=closeDrawers;
  $('#tavbtn').onclick=askTaviel;
  /* settings opened from the right menu */
  initCamDrag();
  const cf=$('#camfab'); if(cf) cf.onclick=toggleCam;
  const dx=$('#deskexit'); if(dx) dx.onclick=exitDesktop;
  window.__goHome=function(){ const o=document.querySelector('#scoverlay'); if(o){o.remove();return;} const s=$('#scrim'); if(s&&!s.hidden){closeDrawers();return;} const df=$('#deskframe'); if(df&&!df.hidden){exitDesktop();return;} nav('home'); };
  applyAppSettings();                         // accent hue, background visibility, reader size
  if(ghCfg().token) setTimeout(()=>ghPull(true),2500);   // quiet vault pull on launch
  nav('home');
  setTimeout(()=>checkUpdates(true),1500);   // quiet update check on launch
  autoLoadDesktop();                          // become the FULL 1:1 app when the desktop is reachable
});
/* When the desktop PC is reachable, load the real desktop app in a full-screen frame (1:1),
   keeping the camera / studio overlays floating on top. Falls back to the offline app otherwise. */
async function autoLoadDesktop(){
  const u=normUrl(deskUrl()); if(!u) return;   // no desktop set -> stay on the offline app
  const ok=await pingDesktop(u); if(!ok) return;
  showDesktop(u);
}
function showDesktop(u){ u=normUrl(u||deskUrl()); if(!u) return;
  const df=$('#deskframe'); if(!df) return;
  df.src=u+'/'; df.hidden=false;
  $('#view').style.display='none'; const tb=$('#tabbar'); if(tb)tb.style.display='none'; const top=$('#topbar'); if(top)top.style.display='none';
  const dx=$('#deskexit'); if(dx)dx.hidden=false;
  try{ window.__tab='desktop'; }catch(e){}
}
function exitDesktop(){ const df=$('#deskframe'); if(df){df.hidden=true; df.src='about:blank';}
  $('#view').style.display=''; const tb=$('#tabbar'); if(tb)tb.style.display=''; const top=$('#topbar'); if(top)top.style.display='';
  $('#deskexit').hidden=true; nav('home'); }
