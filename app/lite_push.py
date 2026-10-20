# Brier — team shard -> summary form. No per-player game lines are kept; only aggregates over many games.
import re, json
MIN_N = 15
def num(s):
    if s is None: return None
    if isinstance(s, (int, float)): return s
    s = str(s).strip()
    if s in ('', '--', '-'): return None
    if re.fullmatch(r'[+-]?\d+(\.\d+)?', s): return float(s)
    m = re.match(r'(\d+(\.\d+)?)', s); return float(m.group(1)) if m else None
def num2(s):
    m = re.match(r'\d+(\.\d+)?[-/](\d+(\.\d+)?)', '' if s is None else str(s)); return float(m.group(2)) if m else None
def avg(v): v = [x for x in v if x is not None]; return sum(v)/len(v) if v else None
def rnd(x, k=3): return None if x is None else round(x, k)

def old_m(box):
    pts=reb=ast=tpm=pf=to=0; hT=hF=False
    for p in (box or {}).get('p') or []:
        pts+=p[3] or 0; reb+=p[4] or 0; ast+=p[5] or 0
        if len(p)>7 and p[7] is not None: tpm+=p[7]; hT=True
        if len(p)>12 and p[12] is not None: pf+=p[12]; hF=True
        if len(p)>11 and p[11] is not None: to+=p[11]
    return {'pts':pts,'reb':reb,'ast':ast,'tpm':tpm if hT else None,'pf':pf if hF else None,'to':to if hF else None}

def brows(g, new, labels):
    if not new:
        return [{'ad':p[0],'st':p[1],'min':p[2],'pts':p[3],'reb':p[4],'tpm':p[7] if len(p)>7 else None} for p in ((g.get('box') or {}).get('p') or [])]
    L = labels.get('stats', []); I = lambda k: L.index(k)+2 if k in L else None
    g_ = lambda r,k: (num(r[I(k)]) if I(k) is not None and I(k) < len(r) else None)
    return [{'ad':r[0],'st':r[1],'min':g_(r,'MIN'),'pts':g_(r,'PTS'),'reb':g_(r,'REB'),'tpm':g_(r,'3PT')} for r in ((g.get('box') or {}).get('stats') or [])]
def dnp(g): return (g.get('box') or {}).get('dnp') or []
def grows(g, grp, labels):
    L = labels.get(grp, []); return [{'ad':r[0],'st':r[1],'v':{k:(r[i+2] if i+2 < len(r) else None) for i,k in enumerate(L)}} for r in ((g.get('box') or {}).get(grp) or [])]

def stars_new(games, new, labels):
    szs = sorted({g['sz'] for g in games})[-2:]; P = {}
    for g in games:
        if g['sz'] not in szs: continue
        for r in brows(g, new, labels):
            if r['min'] is None or r['min'] <= 0: continue
            o = P.setdefault(r['ad'], {'gp':0,'pts':0}); o['gp']+=1; o['pts']+=r['pts'] or 0
    L = [{'ad':a,'gp':o['gp'],'ppg':round(10*o['pts']/o['gp'])/10} for a,o in P.items() if o['gp']>=15]
    return sorted(L, key=lambda x:-x['ppg'])[:8]

def avail(games, stars, new, labels):
    rec = games[-10:]; out = {}
    for s in stars:
        seen = sum(1 for g in rec if any(p['ad']==s['ad'] for p in brows(g,new,labels)) or s['ad'] in dnp(g))
        out[s['ad']] = {'seen':seen,'sat':sum(1 for g in rec if s['ad'] in dnp(g)),'n':len(rec)}
    return out

def psplit(games, stars, new, labels):
    out = {}
    for s in stars:
        def row(g): return next((p for p in brows(g,new,labels) if p['ad']==s['ad'] and (p['min'] or 0) > 0), None)
        by = {}; allr = []
        for g in games:
            r = row(g)
            if r: allr.append(r); by.setdefault(g['opp'], []).append(r)
        if not allr: continue
        m = lambda rows,k: avg([x[k] for x in rows])
        e = {}
        for opp, rows in by.items():
            if len(rows) < MIN_N: continue
            o = {'n':len(rows),'pts':[rnd(m(rows,'pts')),rnd(m(allr,'pts'))],'reb':[rnd(m(rows,'reb')),rnd(m(allr,'reb'))]}
            t, tn = m(rows,'tpm'), m(allr,'tpm')
            if t is not None and tn is not None: o['tpm'] = [rnd(t),rnd(tn)]
            e[opp] = o
        out[s['ad']] = e
    return out

def fb_leaders(games, labels, n=5):
    G = games[-n:]
    def acc(grp):
        P = {}
        for g in G:
            for r in grows(g, grp, labels):
                o = P.setdefault(r['ad'], {'ad':r['ad'],'gp':0,'yds':0,'td':0,'int':0,'rec':0,'att':0,'cmp':0,'car':0}); v = r['v']
                o['gp']+=1; o['yds']+=num(v.get('YDS')) or 0; o['td']+=num(v.get('TD')) or 0
                if grp=='passing': o['int']+=num(v.get('INT')) or 0; o['cmp']+=num(v.get('C/ATT')) or 0; o['att']+=num2(v.get('C/ATT')) or 0
                if grp=='receiving': o['rec']+=num(v.get('REC')) or 0
                if grp=='rushing': o['car']+=num(v.get('CAR')) or 0
        if not P: return None
        b = sorted(P.values(), key=lambda x:-x['yds'])[0]; return {k:(round(x,2) if isinstance(x,float) else x) for k,x in b.items()}
    return {'n':len(G),'qb':acc('passing'),'rb':acc('rushing'),'wr':acc('receiving')}

def bats(games, labels):
    L = games[-10:]; sz = L[-1]['sz'] if L else None; S = [g for g in games if g['sz']==sz]; P = {}
    def add(g, key):
        for r in grows(g,'batting',labels):
            o = P.setdefault(r['ad'], {'ad':r['ad'],'ab10':0,'h10':0,'abS':0,'hS':0,'hrS':0,'kS':0,'gp10':0}); v = r['v']
            o['ab10' if key=='L' else 'abS'] += num(v.get('AB')) or 0; o['h10' if key=='L' else 'hS'] += num(v.get('H')) or 0
            if key=='S': o['hrS'] += num(v.get('HR')) or 0; o['kS'] += num(v.get('K')) or 0
            else: o['gp10'] += 1
    for g in L: add(g,'L')
    for g in S: add(g,'S')
    B = sorted([p for p in P.values() if p['ab10']>=15], key=lambda x:-x['ab10'])[:5]
    return [{**p,'avg10':rnd(p['h10']/p['ab10'] if p['ab10'] else 0,6),'avgS':rnd(p['hS']/p['abS'] if p['abS'] else 0,6)} for p in B]

def lite_team(d, spor, idx, new):
    """d: team file (mutated). idx: index.json (labels; old-schema stars come from idx team entry)."""
    games = d['games']; labels = idx.get('labels') or {}
    if d.get('lite'): return d
    S = {}
    if spor == 'basketball':
        stars = stars_new(games,new,labels) if new else (idx.get('_stars') or [])
        if new: d['stars'] = stars
        S['avail'] = avail(games,stars,new,labels); S['psplit'] = psplit(games,stars,new,labels)
    elif spor == 'football': S['leaders'] = fb_leaders(games,labels)
    elif spor == 'baseball': S['bats'] = bats(games,labels)
    for g in games:
        if spor=='basketball' and not new:
            g['m'] = old_m(g.get('box')); g['om'] = old_m(g.get('opp_box'))
        g.pop('box',None); g.pop('opp_box',None)
    S['asof'] = games[-1]['t'] if games else None
    d['sum'] = S; d['lite'] = 1
    return d

# ================= Colab sürücüsü =================
import os, glob, time, base64, requests
from google.colab import drive, userdata
drive.mount('/content/drive')
KOK = '/content/drive/MyDrive/brier/'; GIRDI = KOK + 'terminal/'; CIKTI = KOK + 'terminal_lite/'
REPO = 'bturkyil/brier-veri'; BRANCH = 'main'; TOKEN = userdata.get('github_token')
PUSH = False                      # önce False ile çalıştır (yalnızca Drive'a yazar, boyutları gösterir); sonra True
LIGS = [('nba','basketball'),('wnba','basketball'),('nfl','football'),('ncaaf','football'),('mlb','baseball')]
H = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/vnd.github+json'}

def gh_put(path, data, msg):
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    for i in range(4):
        r = requests.get(url, headers=H, params={'ref': BRANCH}, timeout=60); sha = r.json().get('sha') if r.status_code == 200 else None
        body = {'message': msg, 'content': base64.b64encode(data).decode(), 'branch': BRANCH}
        if sha: body['sha'] = sha
        r = requests.put(url, headers=H, json=body, timeout=180)
        if r.status_code in (200, 201): return True
        time.sleep(3 * (i + 1))
    print('   HATA', path, r.status_code, r.text[:120]); return False

tot_in = tot_out = n_ok = 0
for lig, spor in LIGS:
    ip = GIRDI + lig + '/index.json'
    if not os.path.exists(ip): print('yok:', lig); continue
    idx = json.load(open(ip)); new = bool(idx.get('spor'))
    stars_by = {t['slug']: (t.get('stars') or []) for t in idx.get('teams', [])}
    os.makedirs(CIKTI + lig + '/teams', exist_ok=True)
    for f in sorted(glob.glob(GIRDI + lig + '/teams/*.json')):
        slug = os.path.basename(f)[:-5]; d = json.load(open(f))
        idx['_stars'] = stars_by.get(slug, [])
        d = lite_team(d, spor, idx, new)
        assert not any('box' in g or 'opp_box' in g for g in d['games']), slug
        raw = json.dumps(d, separators=(',', ':'), ensure_ascii=False).encode()
        open(CIKTI + lig + '/teams/' + slug + '.json', 'wb').write(raw)
        tot_in += os.path.getsize(f); tot_out += len(raw)
        if PUSH:
            if gh_put(f'terminal/{lig}/teams/{slug}.json', raw, f'{lig} {slug}: summaries'): n_ok += 1
            time.sleep(0.25)
    print(f'{lig}: tamam')
print(f'ham {tot_in/1e6:.1f} MB -> özet {tot_out/1e6:.1f} MB' + (f' · push {n_ok} dosya' if PUSH else ' · (PUSH=False: GitHub\'a gönderilmedi)'))
