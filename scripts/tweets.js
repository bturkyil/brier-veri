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
const TW_URL=23;  // Twitter her linki 23 karakter sayar

const strip=(s)=>String(s).replace(/<[^>]+>/g,'').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim();
const hashtag=(name)=>'#'+String(name).replace(/[^A-Za-z0-9 ]/g,'').split(' ').slice(-2).map(w=>w[0].toUpperCase()+w.slice(1)).join('').replace(/^(.{0,3})$/,'$1');
const nick=(name)=>{ const p=String(name).split(' '); return p.length>2&&/^(Red|White|Blue|Trail|Crimson|Golden|Fighting|Mean|Green|Scarlet|Yellow|Black|Tar|Horned|Ragin|Demon|Blue|Nittany)$/.test(p[p.length-2])?p.slice(-2).join(' '):p[p.length-1]; };
const len=(s)=>s.replace(/https?:\/\/\S+/g,'x'.repeat(TW_URL)).length;

async function runLig(lig,ymd,feed){
  const html=fs.readFileSync(path.join(ROOT,'terminal','index.html'),'utf8');
  const js=html.split('<script>')[1].split('</script>')[0];
  const els={}; const el=(id)=>els[id]||(els[id]={innerHTML:'',textContent:'',value:'',selectedIndex:0,offsetTop:0,addEventListener(){},querySelectorAll(){return [];},dataset:{}});
  const ctx={console:{log(){},error(){},warn(){}},URLSearchParams,URL,Date,Math,JSON,Promise,Object,Array,String,Number,Set,Intl,parseFloat,isNaN,setTimeout,
    location:{search:`?lig=${lig}`,href:`${SITE}?lig=${lig}`},history:{replaceState(){}},navigator:{clipboard:{writeText(){}}},window:{scrollTo(){}},
    document:{getElementById:el,querySelectorAll(){return [];},title:''},
    fetch:async(u)=>{ if(u.startsWith(HOST))return {ok:true,json:async()=>feed};
      const p=u.startsWith('../')?path.join(ROOT,u.slice(3)):path.join(ROOT,'terminal',u);
      if(!fs.existsSync(p))return {ok:false,json:async()=>null};
      return {ok:true,json:async()=>JSON.parse(fs.readFileSync(p,'utf8'))}; } };
  vm.createContext(ctx); vm.runInContext(js+'\n;globalThis.__tonight=()=>TONIGHT;',ctx);   // let ile tanimli listeye erisim
  await new Promise(r=>setTimeout(r,800));   // boot + loadTonight + rozetler
  const out=[];
  for(const m of (ctx.__tonight()||[])){
    if(m.day!==ymd)continue;
    try{ await ctx.openRecord(m.h,m.a,m.t,m.p,m); }catch(e){ continue; }
    const det=els.detail.innerHTML;
    const says=(det.match(/<div class="tgol says"[\s\S]*?<div class="tf">/)||[''])[0];
    const lines=[...says.matchAll(/<div>([\s\S]*?)<\/div>/g)].map(x=>strip(x[1])).filter(Boolean);
    const h=ctx.findTeam(m.h), a=ctx.findTeam(m.a); if(!h||!a||!lines.length)continue;
    const link=`${SITE}?lig=${lig}&h=${encodeURIComponent(h.ad)}&a=${encodeURIComponent(a.ad)}`;
    const badges=(m.badges||[]).map(b=>strip(b.txt));
    const when=new Date(m.t).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'})+' ET';
    out.push({lig,h:h.ad,a:a.ad,hn:nick(h.ad),an:nick(a.ad),when,lines,badges,link,market:m.p&&m.p.h!=null?Math.round(m.p.h*100):null});
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
  return opts.slice(0,3);
}
(async()=>{
  const ymd=process.argv[2]||new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'});
  let feed=null;
  try{ const r=await fetch(HOST+'/bugun.json'); feed=await r.json(); }catch(e){ console.error('feed unreachable:',e.message); process.exit(0); }
  const all=[];
  for(const lig of LIGS){ try{ all.push(...await runLig(lig,ymd,feed)); }catch(e){ console.error(lig,e.message); } }
  const leans=all.filter(g=>g.badges.some(b=>/record leans/.test(b)));
  let md=`# Brier — ${ymd}\n\n${all.length} games on the slate. ${leans.length} where the record leans against the market.\n\nEach block is a ready tweet; pick one per game, or none. Every number comes from the match page behind the link.\n\n`;
  if(leans.length){ md+=`## Record vs market\n\n`; for(const g of leans)md+=`- ${g.hn} v ${g.an} (${TAG[g.lig]}): ${g.badges.filter(b=>/record leans/.test(b)).join(', ')} — ${g.link}\n`; md+='\n'; }
  for(const lig of LIGS){ const G=all.filter(g=>g.lig===lig); if(!G.length)continue; md+=`## ${TAG[lig].slice(1)}\n\n`;
    for(const g of G){ md+=`### ${g.h} — ${g.a} · ${g.when}${g.market!=null?` · market ${g.market}/${100-g.market}`:''}${g.badges.length?` · ${g.badges.join(' · ')}`:''}\n\n`;
      compose(g).forEach((t,i)=>{ md+=`**Option ${i+1}** (${len(t)} chars)\n\n\`\`\`\n${t}\n\`\`\`\n\n`; }); } }
  if(!all.length)md+='_No games found in the feed for this date._\n';
  fs.mkdirSync(path.join(ROOT,'tweets'),{recursive:true});
  fs.writeFileSync(path.join(ROOT,'tweets',`${ymd}.md`),md);
  console.log(`tweets/${ymd}.md — ${all.length} games, ${leans.length} record-vs-market`);
})();
