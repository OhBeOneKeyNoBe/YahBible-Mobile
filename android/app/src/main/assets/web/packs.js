/* YahBible Mobile — updates & downloadable packs (all-web-layer, no native code).
   - self-update: checks a remote manifest and can refresh bundled study content
   - downloadable packs: the 120+ versions (per-book) and the offline word-study pack
   - storage: IndexedDB (survives app restarts), with progress + size reporting     */
"use strict";
(function(){
  // where the packs live (Hugging Face raw resolve). Overridable via localStorage yb_pack_base.
  const DEFAULT_BASE = "https://huggingface.co/OhBeOneKeyNoBe/YahBible-Mobile/resolve/main/packs/";
  function base(){ try{ return localStorage.getItem('yb_pack_base') || DEFAULT_BASE; }catch(e){ return DEFAULT_BASE; } }

  // ---- IndexedDB (a tiny key/value store) ----
  let _db=null;
  function db(){ if(_db) return Promise.resolve(_db);
    return new Promise((res,rej)=>{ const r=indexedDB.open('yahbible',1);
      r.onupgradeneeded=()=>{ const d=r.result; if(!d.objectStoreNames.contains('packs')) d.createObjectStore('packs'); };
      r.onsuccess=()=>{ _db=r.result; res(_db); }; r.onerror=()=>rej(r.error); }); }
  function idbGet(k){ return db().then(d=>new Promise((res,rej)=>{ const t=d.transaction('packs','readonly').objectStore('packs').get(k);
      t.onsuccess=()=>res(t.result); t.onerror=()=>rej(t.error); })); }
  function idbPut(k,v){ return db().then(d=>new Promise((res,rej)=>{ const t=d.transaction('packs','readwrite').objectStore('packs').put(v,k);
      t.onsuccess=()=>res(true); t.onerror=()=>rej(t.error); })); }
  function idbDel(k){ return db().then(d=>new Promise((res,rej)=>{ const t=d.transaction('packs','readwrite').objectStore('packs').delete(k);
      t.onsuccess=()=>res(true); t.onerror=()=>rej(t.error); })); }
  function idbKeys(){ return db().then(d=>new Promise((res,rej)=>{ const t=d.transaction('packs','readonly').objectStore('packs').getAllKeys();
      t.onsuccess=()=>res(t.result||[]); t.onerror=()=>rej(t.error); })); }

  // ---- gzip decode (browser DecompressionStream, with a no-op fallback for plain json) ----
  async function ungzip(buf){
    try{ if(typeof DecompressionStream!=='undefined'){
        const ds=new DecompressionStream('gzip');
        const stream=new Response(buf).body.pipeThrough(ds);
        return await new Response(stream).text();
      } }catch(e){}
    return new TextDecoder().decode(buf);   // already-plain
  }

  // ---- networked download with progress ----
  async function fetchProgress(url,onProg){
    const r=await fetch(url,{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const total=+(r.headers.get('content-length')||0);
    if(!r.body||!r.body.getReader){ const b=await r.arrayBuffer(); if(onProg)onProg(1,total,total); return new Uint8Array(b); }
    const reader=r.body.getReader(); const chunks=[]; let got=0;
    for(;;){ const {done,value}=await reader.read(); if(done) break; chunks.push(value); got+=value.length;
      if(onProg) onProg(total?got/total:0, got, total); }
    const out=new Uint8Array(got); let o=0; for(const c of chunks){ out.set(c,o); o+=c.length; }
    return out;
  }

  async function getManifest(){
    try{ const u=base()+'manifest.json?ts='+Date.now();
      const r=await fetch(u,{cache:'no-store'}); if(!r.ok) throw 0; return await r.json();
    }catch(e){ return null; } }

  // download a whole pack file into IndexedDB (stored decompressed as text under key)
  async function downloadFile(remoteName, storeKey, onProg){
    const buf=await fetchProgress(base()+remoteName, onProg);
    const text=/\.gz($|\?)/.test(remoteName)? await ungzip(buf) : new TextDecoder().decode(buf);
    await idbPut(storeKey, text);
    return text.length;
  }

  // parsed-cache so we don't re-parse big JSON every lookup
  const _mem={};
  async function loadJSON(storeKey){ if(_mem[storeKey]!==undefined) return _mem[storeKey];
    const t=await idbGet(storeKey); if(t==null){ _mem[storeKey]=null; return null; }
    try{ _mem[storeKey]=JSON.parse(t); }catch(e){ _mem[storeKey]=null; } return _mem[storeKey]; }

  async function have(storeKey){ const t=await idbGet(storeKey); return t!=null; }
  async function storedKeys(){ return await idbKeys(); }
  async function removePrefix(prefix){ const ks=await idbKeys();
    for(const k of ks){ if(String(k).indexOf(prefix)===0){ await idbDel(k); delete _mem[k]; } } }

  // ---- versions pack: per-book file "versions/<ABBR>.json.gz" -> {verCode:{ch:{v:text}}} ----
  async function ensureBookVersions(abbr, onProg){
    const key='ver:'+abbr;
    if(await have(key)) return await loadJSON(key);
    await downloadFile('versions/'+abbr+'.json.gz', key, onProg);
    _mem[key]=undefined; return await loadJSON(key);
  }
  // ---- word-study pack: per-book "wordstudy/<ABBR>.json.gz" + global "wordstudy/strongs.json.gz" ----
  async function ensureBookWords(abbr, onProg){
    const key='ws:'+abbr;
    if(await have(key)) return await loadJSON(key);
    await downloadFile('wordstudy/'+abbr+'.json.gz', key, onProg);
    _mem[key]=undefined; return await loadJSON(key);
  }
  async function ensureStrongs(onProg){
    const key='ws:strongs';
    if(await have(key)) return await loadJSON(key);
    await downloadFile('wordstudy/strongs.json.gz', key, onProg);
    _mem[key]=undefined; return await loadJSON(key);
  }

  // ---- extra sources pack: "sources/<id>.json.gz" -> {book:[[ref,text],...]} ----
  async function ensureSource(id, onProg){
    const key='src:'+id;
    if(await have(key)) return await loadJSON(key);
    await downloadFile('sources/'+id+'.json.gz', key, onProg);
    _mem[key]=undefined; return await loadJSON(key);
  }
  async function sourcesIndex(){
    try{ const r=await fetch(base()+'sources/_index.json?ts='+Date.now(),{cache:'no-store'}); if(r.ok) return (await r.json()).sources||[]; }catch(e){}
    return [];
  }
  window.YBPacks={ getManifest, fetchProgress, downloadFile, loadJSON, have, storedKeys,
    idbGet, idbPut, idbDel, removePrefix, ensureBookVersions, ensureBookWords, ensureStrongs,
    ensureSource, sourcesIndex, base };
})();
