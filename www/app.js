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
    if(b.t==='belief') return '<div class="beliefbox"><span class="bblbl">Believe</span>'+linkifyScripture(b.text||'')+'</div>';
    if(b.t==='prayer') return '<div class="prayerbox">&ldquo;'+linkifyScripture(b.text||'')+'&rdquo;'+(b.ref?'<span class="cscrref">'+linkifyScripture(b.ref)+'</span>':'')+'</div>';
    if(b.t==='refline') return '<div class="refline"><span class="rlt">'+esc(b.text||'')+'</span>'+(b.ref?'<span class="scref" data-ref="'+esc(b.ref)+'">'+linkifyScripture(b.ref)+'</span>':'')+'</div>';
    return '<p>'+linkifyScripture(b.text||'')+'</p>';
  }).join(''); }

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
      : '<p>'+linkifyScripture(b.text||'')+'</p>').join('');
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
  const body=verses.map((tx,i)=>'<p class="rv'+(verse===i+1?' hl':'')+'" id="rv'+(i+1)+'"><span class="rvn">'+(i+1)+'</span>'+esc(tx)+'</p>').join('');
  const prev=ch>1, next=ch<b.ch.length;
  setView('<div class="screen reader"><div class="rdbar"><button class="backbtn" id="rdbooks">📚 '+esc(b.a)+'</button>'+
    '<div class="rdttl">'+esc(b.n)+' '+ch+'</div>'+
    '<div class="rdnav"><button id="rdprev"'+(prev?'':' disabled')+'>‹</button><button id="rdnext"'+(next?'':' disabled')+'>›</button></div></div>'+
    '<div class="rdbody">'+body+'</div>'+
    '<div class="rdfoot">'+(prev?'<button class="rdmore" id="rdprev2">‹ '+esc(b.n)+' '+(ch-1)+'</button>':'<span></span>')+
      (next?'<button class="rdmore" id="rdnext2">'+esc(b.n)+' '+(ch+1)+' ›</button>':'<span></span>')+'</div></div>');
  $('#rdbooks').onclick=()=>openBook(bi);
  const go=d=>openReader(bi,ch+d);
  ['#rdprev','#rdprev2'].forEach(s=>{const e=$(s);if(e&&prev)e.onclick=()=>go(-1);});
  ['#rdnext','#rdnext2'].forEach(s=>{const e=$(s);if(e&&next)e.onclick=()=>go(1);});
  if(verse){ const el=$('#rv'+verse); if(el) setTimeout(()=>el.scrollIntoView({block:'center'}),60); }
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
  if(tab==='home') showHome();
  else if(tab==='bible') openBible();
  else if(tab==='commandments') showCommandments();
  else if(tab==='repentance'||tab==='repent') openRepentance();
  else if(tab==='news') openNews(); }

/* ---------- self-cam overlay (TikTok streaming) ---------- */
let _camStream=null;
async function toggleCam(){ const cam=$('#cam'), btn=$('#cambtn');
  if(cam.classList.contains('on')){ stopCam(); return; }
  try{
    _camStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});
    $('#camvid').srcObject=_camStream; cam.classList.add('on'); btn.classList.add('on');
  }catch(e){ toast('Camera unavailable — allow camera to use the self-cam'); }
}
function stopCam(){ const cam=$('#cam'), btn=$('#cambtn');
  if(_camStream){ _camStream.getTracks().forEach(t=>t.stop()); _camStream=null; }
  cam.classList.remove('on'); btn.classList.remove('on'); }
function initCamDrag(){ const cam=$('#cam'); let sx,sy,ox,oy,drag=false;
  const start=e=>{ const p=e.touches?e.touches[0]:e; drag=true; sx=p.clientX; sy=p.clientY;
    const r=cam.getBoundingClientRect(); ox=r.left; oy=r.top; cam.style.bottom='auto'; cam.style.right='auto'; };
  const move=e=>{ if(!drag) return; const p=e.touches?e.touches[0]:e;
    let x=ox+(p.clientX-sx), y=oy+(p.clientY-sy);
    x=Math.max(4,Math.min(window.innerWidth-cam.offsetWidth-4,x));
    y=Math.max(56,Math.min(window.innerHeight-cam.offsetHeight-4,y));
    cam.style.left=x+'px'; cam.style.top=y+'px'; e.preventDefault(); };
  const end=()=>drag=false;
  cam.addEventListener('mousedown',start); cam.addEventListener('touchstart',start,{passive:true});
  window.addEventListener('mousemove',move); window.addEventListener('touchmove',move,{passive:false});
  window.addEventListener('mouseup',end); window.addEventListener('touchend',end); }

/* ---------- boot ---------- */
window.addEventListener('DOMContentLoaded',()=>{
  if(newsUnseen()){ const n=document.querySelector('.tab[data-tab="news"]'); if(n){ const d=document.createElement('span'); d.className='dot'; d.id='newsdot'; n.appendChild(d); } }
  document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>nav(b.dataset.tab==='repent'?'repentance':b.dataset.tab));
  $('#cambtn').onclick=toggleCam;
  $('#camclose').onclick=stopCam;
  $('#camshape').onclick=()=>$('#cam').classList.toggle('green');
  initCamDrag();
  window.__goHome=function(){ const o=document.querySelector('#scoverlay'); if(o){o.remove();return;} nav('home'); };
  nav('home');
});
