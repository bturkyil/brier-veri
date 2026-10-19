// Brier — gunluk tweet taslaklari.
// terminal/index.html'deki motoru (ayni kartlar, ayni cumleler) Node icinde calistirir,
// bugunun maclari icin "The record says" satirlarini alir, tweets/YYYY-MM-DD.md yazar.
// Kullanim: node scripts/tweets.js [YYYY-MM-DD]   (repo kokunden)
const fs=require('fs'), path=require('path'), vm=require('vm');
const ROOT=process.cwd();
const HOST='https://worker-production-a1ba.up.railway.app';
const SITE='https://brierrecord.com/terminal/';
const LIGS=['nba','wnba','nfl','ncaaf','mlb'];
const TAG={nba:'#NBA',wnba:'#WNBA',nfl:'#NFL',ncaaf:'#CFB',mlb:'#MLB'};
const TW_URL=23;
const FACTS={};   // lig -> {n,bf,bc,lab,sharper}  // Twitter her linki 23 karakter sayar

const strip=(s)=>String(s).replace(/<[^>]+>/g,'').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim();
const hashtag=(name)=>'#'+String(name).replace(/[^A-Za-z0-9 ]/g,'').split(' ').slice(-2).map(w=>w[0].toUpperCase()+w.slice(1)).join('').replace(/^(.{0,3})$/,'$1');
const nick=(name)=>{ const p=String(name).split(' '); return p.length>2&&/^(Red|White|Blue|Trail|Crimson|Golden|Fighting|Mean|Green|Scarlet|Yellow|Black|Tar|Horned|Ragin|Demon|Blue|Nittany)$/.test(p[p.length-2])?p.slice(-2).join(' '):p[p.length-1]; };
const len=(s)=>s.replace(/https?:\/\/\S+/g,'x'.repeat(TW_URL)).length;

async function runLig(lig,ymd,feed){
  const html=fs.readFileSync(path.join(ROOT,'terminal','index.html'),'utf8');
  const js=html.split('<script>')[1].split('</script>')[0];
  const els={}; const el=(id)=>els[id]||(els[id]={innerHTML:'',textContent:'',value:'',selectedIndex:0,offsetTop:0,disabled:false,onclick:null,classList:{add(){},remove(){},toggle(){}},addEventListener(){},querySelectorAll(){return [];},querySelector(){return null;},dataset:{}});
  const ctx={console:{log(){},error(){},warn(){}},URLSearchParams,URL,Date,Math,JSON,Promise,Object,Array,String,Number,Set,Intl,parseFloat,isNaN,setTimeout,
    location:{search:`?lig=${lig}`,href:`${SITE}?lig=${lig}`},history:{replaceState(){}},navigator:{clipboard:{writeText(){}}},window:{scrollTo(){},innerWidth:1200},
    document:{getElementById:el,querySelectorAll(){return [];},querySelector(){return null;},title:''},
    fetch:async(u)=>{ if(u.startsWith(HOST))return {ok:true,json:async()=>feed};
      const p=u.startsWith('../')?path.join(ROOT,u.slice(3)):path.join(ROOT,'terminal',u);
      if(!fs.existsSync(p))return {ok:false,json:async()=>null};
      return {ok:true,json:async()=>JSON.parse(fs.readFileSync(p,'utf8'))}; } };
  vm.createContext(ctx); vm.runInContext(js+'\n;globalThis.__tonight=()=>TONIGHT;',ctx);   // let ile tanimli listeye erisim
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,250)); const T=ctx.__tonight(); if(T&&T.length&&T.every(m=>m.badges&&m.badges.length>=0)&&i>3)break; }   // boot + loadTonight + rozetler
  const T0=ctx.__tonight()||[]; console.error(`[${lig}] feed games: ${T0.length} · days: ${[...new Set(T0.map(m=>m.day))].join(',')} · target ${ymd} · list html: ${(els.list.innerHTML||'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').slice(0,120)}`);
  const out=[];
  for(const m of (ctx.__tonight()||[])){
    if(m.day!==ymd)continue;
    try{ await ctx.openRecord(m.h,m.a,m.t,m.p,m); }catch(e){ console.error('  openRecord failed:',m.h,'-',m.a,e.message); continue; }
    const det=els.detail.innerHTML;
    const says=(det.match(/<div class="tgol says"[\s\S]*?<div class="tf">/)||[''])[0];
    const lines=[...says.matchAll(/<div>([\s\S]*?)<\/div>/g)].map(x=>strip(x[1])).filter(Boolean);
    const h=ctx.findTeam(m.h), a=ctx.findTeam(m.a); if(!h||!a||!lines.length)continue;
    const link=`${SITE}?lig=${lig}&h=${encodeURIComponent(h.ad)}&a=${encodeURIComponent(a.ad)}`;
    const badges=(m.badges||[]).map(b=>strip(b.txt));
    // Line flow: (a) bugunun hareketine ozel cumle, (b) lig duzeyinde Brier gercegi
    let flow=null; const ft=strip(det.split('<div class="tgol"').filter(c=>/<div class="th">Line flow<span/.test(c)).join(' '));
    const fm=ft.match(/The price has moved (\d+) pts toward ([A-Za-z.' ]+?) (since [A-Za-z0-9: ]+ ET|in the last 24 hours|since the open)\. In ([\d,]+) past games with a move that size the side won (\d+)% against (\d+)% implied by the close/);
    if(fm)flow={d:fm[1],team:fm[2].trim(),when:fm[3],n:fm[4],w:fm[5],i:fm[6]};
    if(!FACTS[lig]){ const bm=ft.match(/Close vs (.+?) ([\d,]+) games\s*Brier (\d\.\d+) → (\d\.\d+)/); if(bm)FACTS[lig]={lab:bm[1],n:bm[2],bf:bm[3],bc:bm[4],sharper:/the close is sharper/.test(ft)}; }
    const when=new Date(m.t).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'})+' ET';
    out.push({lig,h:h.ad,a:a.ad,hn:nick(h.ad),an:nick(a.ad),when,lines,badges,link,flow,market:m.p&&m.p.h!=null?Math.round(m.p.h*100):null});
  }
  return out;
}
function compose(g){
  const tags=`${TAG[g.lig]} ${hashtag(g.hn)} ${hashtag(g.an)}`;
  const head=`${g.hn} v ${g.an}, ${g.when}.`;
  const foot=`Not a tip — the record: ${g.link}\n${tags}`;
  const opts=[];
  // 1) tek satir: en guclu bulgu
  for(const l of g.lines){ const t=`${head}\n${l}\n\n${foot}`; if(len(t)<=280)opts.push(t); }
  // 2) iki satir sigarsa
  for(let i=0;i<g.lines.length;i++)for(let j=i+1;j<g.lines.length;j++){ const t=`${head}\n${g.lines[i]}\n${g.lines[j]}\n\n${foot}`; if(len(t)<=280)opts.push(t); }
  // 3) kisaltilmis: ilk cumle ' — ' oncesi
  if(!opts.length){ const l=g.lines[0].split(' — ')[0]; opts.push(`${head}\n${l}.\n\n${foot}`); }
  if(g.flow){   // bugunun fiyat hareketi + gecmis kayit: ayri bir secenek olarak garanti et
    const f=g.flow; const when=f.when.replace(/^since the open$/,'since the open').replace(/^in the last 24 hours$/,'in 24 hours');
    let t=`${head}\nPrice moved ${f.d} pts toward ${f.team} ${when}. Past ${f.n} games with a move that size: won ${f.w}%, close implied ${f.i}%.\n\n${foot}`;
    if(len(t)>280)t=`${g.hn} v ${g.an}: price moved ${f.d} pts toward ${f.team}. Past ${f.n} similar moves: won ${f.w}%, close implied ${f.i}%.\n\n${foot}`;
    if(len(t)<=280){ const o=opts.slice(0,2); o.push(t); return o; }
  }
  return opts.slice(0,3);
}
(async()=>{
  const ymd=process.argv[2]||new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});
  let feed=null;
  try{ const r=await fetch(HOST+'/bugun.json'); feed=await r.json(); }catch(e){ console.error('feed unreachable:',e.message); process.exit(0); }
  console.error('feed keys:',Object.values(feed.ligler||{}).map(x=>`${x.key}:${(x.maclar||[]).length}`).join(' '));
  const all=[];
  for(const lig of LIGS){ try{ all.push(...await runLig(lig,ymd,feed)); }catch(e){ console.error(lig,e.message); } }
  const leans=all.filter(g=>g.badges.some(b=>/record leans/.test(b)));
  let md=`# Brier — ${ymd}\n\n${all.length} games on the slate. ${leans.length} where the record leans against the market.\n\nEach block is a ready tweet; pick one per game, or none. Every number comes from the match page behind the link.\n\n`;
  if(leans.length){ md+=`## Record vs market\n\n`; for(const g of leans)md+=`- ${g.hn} v ${g.an} (${TAG[g.lig]}): ${g.badges.filter(b=>/record leans/.test(b)).join(', ')} — ${g.link}\n`; md+='\n'; }
  const facts=Object.entries(FACTS); if(facts.length){ md+=`## League facts (evergreen)\n\n`;
    for(const [lig,f] of facts){ const t=`${lig.toUpperCase()}: across ${f.n} games the closing price scored ${f.bc} Brier vs ${f.bf} for ${f.lab}. ${f.sharper?'The late money carried information.':'No clear difference between them.'}\n\nNot a tip — the record: ${SITE}?lig=${lig}\n${TAG[lig]}`;
      md+=`**${TAG[lig]}** (${len(t)} chars)\n\n\`\`\`\n${t}\n\`\`\`\n\n`; } }
  for(const lig of LIGS){ const G=all.filter(g=>g.lig===lig); if(!G.length)continue; md+=`## ${TAG[lig].slice(1)}\n\n`;
    for(const g of G){ md+=`### ${g.h} — ${g.a} · ${g.when}${g.market!=null?` · market ${g.market}/${100-g.market}`:''}${g.badges.length?` · ${g.badges.join(' · ')}`:''}\n\n`;
      compose(g).forEach((t,i)=>{ md+=`**Option ${i+1}** (${len(t)} chars)\n\n\`\`\`\n${t}\n\`\`\`\n\n`; }); } }
  if(!all.length)md+='_No games found in the feed for this date._\n';
  fs.mkdirSync(path.join(ROOT,'tweets'),{recursive:true});
  fs.writeFileSync(path.join(ROOT,'tweets',`${ymd}.md`),md);
  console.log(`tweets/${ymd}.md — ${all.length} games, ${leans.length} record-vs-market`);
})();
