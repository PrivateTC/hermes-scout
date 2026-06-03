# -*- coding: utf-8 -*-
# Hermès Scout — deterministický builder reportu.
# Vstup:  hermes_scan_data.json  = [{"model","title","eur","market","url","country","priv"}...]
# Stav:   hermes_seen.json        = [url,...] (pro označení NOVÝCH)
# Výstup: hermes-dostupne-kabelky.html  + vytiskne souhrn pro ClickUp.
import json, html, re, datetime, os
HERE=os.path.dirname(os.path.abspath(__file__))
def P(f): return os.path.join(HERE,f)
RESALE={"kelly 25":700000,"kelly 28":680000,"kelly 32":520000,"kelly 35":480000,"kelly 20":560000,
 "birkin 25":650000,"birkin 30":640000,"birkin 35":520000,"birkin 40":470000,"kelly":560000,"birkin":600000}
EURCZK=25.0; REPAIR=40000; MIN_M=80000; TGT_M=150000
EU_C={"Francie","Německo","Itálie","Belgie","Nizozemsko","Španělsko","Polsko","Irsko","Rakousko","Portugalsko","Lucembursko"}
MKC={"Vestiaire":"#6b3fc0","eBay.de":"#1f6fd6","Leboncoin":"#e8642a","Kleinanzeigen":"#178a7a","eBay":"#1f6fd6"}
def resale(s):
    s=s.lower()
    for k in sorted(RESALE,key=len,reverse=True):
        if k in s: return RESALE[k]
    return None
def isEU(c): return any(x in (c or "") for x in EU_C)
def cz(n): return "{:,}".format(int(n)).replace(","," ") if n is not None else "—"
data=json.load(open(P("hermes_scan_data.json"),encoding="utf-8"))
try: seen=set(json.load(open(P("hermes_seen.json"),encoding="utf-8")))
except Exception: seen=set()
items=[]
for d in data:
    eur=d["eur"]; p=round(eur*EURCZK); r=resale(d["title"]) or resale(d["model"])
    margin=r-p-REPAIR if r else None
    tgt=(r-REPAIR-TGT_M) if r else None
    rec=max(min(tgt,round(p*0.9)),round(p*0.6)) if tgt is not None else None
    ceil=(r-REPAIR-MIN_M) if r else None
    flag,cls=("KOUPIT","buy") if (margin and margin>=TGT_M) else (("ZVÁŽIT","mid") if (margin and margin>=MIN_M) else ("DRAHÉ","no"))
    items.append(dict(d,p=p,resale=r,margin=margin,rec=rec,rec_eur=round(rec/EURCZK) if rec else None,
        ceil=ceil,flag=flag,cls=cls,eu=isEU(d.get("country","")),new=d["url"] not in seen))
kelly=sorted([x for x in items if x["model"]=="kelly"],key=lambda x:x["eur"])
birk =sorted([x for x in items if x["model"]=="birkin"],key=lambda x:x["eur"])
def mkt(m): c=MKC.get(m,"#555"); return f'<span class="mkt" style="background:{c}1a;color:{c}">{m}</span>'
def seller(x): return '<span class="sel priv">soukromý ✓</span>' if x.get("priv") else '<span class="sel mark">market</span>'
def reg(x): return f'<span class="reg {"reu" if x["eu"] else "rww"}">{"EU ✓" if x["eu"] else (x.get("country","?")+" · clo")}</span>'
def newb(x): return '<span class="newb">NOVÉ</span>' if x["new"] else ''
def topcard(x,i):
    return f"""<div class="tc {x['cls']}"><div class="rank">#{i}</div><div class="tc-b">
<div class="tc-price">{x['eur']:,} €<small>{cz(x['p'])} Kč</small></div>
<div class="tc-title"><a href="{x['url']}" target="_blank">{html.escape(x['title'])}</a> {newb(x)}</div>
<div class="tc-tags">{mkt(x['market'])} {reg(x)} {seller(x)}</div>
<div class="tc-off">Nabídni: <b>{(x['rec_eur'] or 0):,} €</b> · marže ~{cz(x['margin'])} Kč</div>
<a class="tc-link" href="{x['url']}" target="_blank">otevřít ↗</a></div></div>"""
def row(x):
    return f"""<tr class="{x['cls']}" data-model="{x['model']}" data-reg="{'eu' if x['eu'] else 'xeu'}" data-new="{1 if x['new'] else 0}"><td>{mkt(x['market'])}</td>
<td class="title"><a href="{x['url']}" target="_blank">{html.escape(x['title'])}</a> {newb(x)}<div>{reg(x)} {seller(x)}</div></td>
<td class="price">{x['eur']:,} €<i>{cz(x['p'])} Kč</i></td><td class="r">{cz(x['resale'])} Kč</td>
<td class="r mg">{cz(x['margin'])} Kč</td><td class="r off">{(x['rec_eur'] or 0):,} €<i>{cz(x['rec'])} Kč</i></td>
<td class="r">{cz(x['ceil'])} Kč</td><td><span class="badge {x['cls']}">{x['flag']}</span></td><td><a class="go" href="{x['url']}" target="_blank">↗</a></td></tr>"""
TH="<thead><tr><th>Market</th><th>Inzerát</th><th class='price'>Cena</th><th class='r'>Přibl. prodej</th><th class='r'>Marže</th><th class='r'>Nabídka</th><th class='r'>Strop</th><th>Hodn.</th><th></th></tr></thead>"
def tbl(r): return f"<table>{TH}<tbody>{''.join(row(x) for x in r)}</tbody></table>"
ke=[x for x in kelly if x["eu"]]; kx=[x for x in kelly if not x["eu"]]
be=[x for x in birk if x["eu"]]; bx=[x for x in birk if not x["eu"]]
today=datetime.date.today().strftime("%-d. %-m. %Y")
n_eu=len([x for x in items if x["eu"]]); n_new=len([x for x in items if x["new"]])
markets=", ".join(sorted(set(x["market"] for x in items)))
ALLM=[("Vestiaire","EU marketplace"),("eBay.de","EU/global"),("Leboncoin","FR soukrome"),("Kleinanzeigen","DE soukrome"),("Buyee","JP proxy"),("eBay.fr/it/es","EU duplicita"),("Vinted","EU - padelky")]
try: _ms={m["name"]:m for m in json.load(open(P("hermes_markets.json")))}
except Exception: _ms={}
_cnt={}
for x in items: _cnt[x["market"]]=_cnt.get(x["market"],0)+1
def _cov():
    cells=[]
    for nm,desc in ALLM:
        info=_ms.get(nm); c=_cnt.get(nm,0)
        if info and info.get("status")=="blocked": st,clz="✗ blokovano","cov-no"
        elif c>0 or (info and info.get("status")=="ok"): st,clz=("✓ funguje · %d kusu"%c),"cov-ok"
        elif info and info.get("status")=="skipped": st,clz=("⏸ "+info.get("note","odlozeno")),"cov-sk"
        else: st,clz="— nenacteno","cov-sk"
        cells.append('<div class="cov %s"><b>%s</b><span>%s</span><i>%s</i></div>'%(clz,nm,st,desc))
    return '<div class="covgrid">'+"".join(cells)+'</div>'
coverage_html=_cov()
CSS="""*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#1d2330;font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}.wrap{max-width:1240px;margin:0 auto;padding:30px 20px 70px}h1{font-size:25px;margin:0 0 3px}.sub{color:#6b7280;margin:0 0 20px}h2{font-size:21px;margin:36px 0 6px;padding-bottom:8px;border-bottom:2px solid #1d2330}h3{font-size:14px;margin:18px 0 9px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em}.cards{display:flex;gap:12px;flex-wrap:wrap}.kpi{background:#fff;border:1px solid #e7e9ef;border-radius:14px;padding:13px 18px;min-width:120px}.kpi b{display:block;font-size:22px}.kpi span{color:#6b7280;font-size:12px}.topgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}.tc{position:relative;background:#fff;border:1px solid #e7e9ef;border-left:4px solid #18914e;border-radius:13px;padding:14px 15px 12px}.tc.mid{border-left-color:#bf7d12}.tc.no{border-left-color:#cf3b32}.rank{position:absolute;top:-9px;left:-9px;background:#1d2330;color:#fff;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800}.tc-price{font-size:26px;font-weight:800;line-height:1}.tc-price small{font-size:12px;font-weight:500;color:#6b7280;margin-left:6px}.tc-title{font-weight:600;font-size:14px;margin:6px 0}.tc-title a{color:#1d2330;text-decoration:none}.tc-tags{margin:5px 0}.tc-off{font-size:12.5px;color:#6b7280;margin:7px 0 4px}.tc-off b{color:#18914e}.tc-link{font-size:12px;color:#b08d3f;text-decoration:none}table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e7e9ef;border-radius:14px;overflow:hidden;margin-bottom:6px}th,td{padding:9px 11px;border-bottom:1px solid #e7e9ef;text-align:left;vertical-align:middle}th{font-size:11px;text-transform:uppercase;color:#6b7280;background:#fbfbfd}td.r,th.r,td.price,th.price{text-align:right;white-space:nowrap}td.price{font-size:19px;font-weight:800}td.price i,td.r i{display:block;font-style:normal;font-weight:400;color:#6b7280;font-size:11px}.title a{color:#1d2330;text-decoration:none;font-weight:600}.off{color:#18914e;font-weight:700}.mg{font-weight:600}.mkt{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11.5px;font-weight:700}.reg{display:inline-block;padding:1px 7px;border-radius:20px;font-size:10.5px;font-weight:600}.reg.reu{background:#e8f7ef;color:#18914e}.reg.rww{background:#fbf2e0;color:#bf7d12}.sel{display:inline-block;padding:1px 7px;border-radius:20px;font-size:10.5px;font-weight:600}.sel.priv{background:#e8f7ef;color:#18914e}.sel.mark{background:#eef0f4;color:#6b7280}.newb{display:inline-block;padding:1px 7px;border-radius:20px;font-size:10px;font-weight:800;background:#ffe1a8;color:#7a5200}.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:12px;font-weight:700}.badge.buy{background:#e8f7ef;color:#18914e}.badge.mid{background:#fbf2e0;color:#bf7d12}.badge.no{background:#fbe9e8;color:#cf3b32}.go{color:#b08d3f;text-decoration:none}.euband{background:linear-gradient(90deg,#e8f7ef,#fff);border-left:4px solid #18914e;border-radius:8px;padding:6px 12px;font-weight:600;color:#18914e;margin:6px 0 10px}.note{background:#fff;border:1px solid #e7e9ef;border-left:3px solid #b08d3f;border-radius:12px;padding:15px 20px;margin-top:16px;font-size:13px;color:#3a414f}.note b{color:#1d2330}.covgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:8px;margin:14px 0 4px}.cov{border:1px solid #e7e9ef;border-radius:10px;padding:9px 12px;background:#fff}.cov b{display:block;font-size:13px}.cov span{font-size:12px;font-weight:700}.cov i{display:block;font-size:10.5px;color:#6b7280;font-style:normal}.cov-ok span{color:#18914e}.cov-no span{color:#cf3b32}.cov-sk span{color:#6b7280}.cov-ok{border-left:3px solid #18914e}.cov-no{border-left:3px solid #cf3b32}.cov-sk{border-left:3px solid #cbd0d8}.fbar{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 12px}.fbtn{border:1px solid #d7dae2;background:#fff;color:#1d2330;border-radius:20px;padding:7px 14px;font-size:13px;font-weight:600;cursor:pointer}.fbtn:hover{border-color:#b08d3f}.fbtn.on{background:#1d2330;color:#fff;border-color:#1d2330}.fbtn.fnew.on{background:#7a5200;border-color:#7a5200}"""
HTML=f"""<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Hermès Scout {today}</title><style>{CSS}</style></head><body><div class="wrap">
<h1>Hermès Scout — dostupné kabelky & TOP nabídky</h1>
<p class="sub">{markets} · {today} · cena vzestupně, EU navrch · <b>{n_new} nových</b> proti minulému běhu</p>
<div class="cards"><div class="kpi"><b>{len(items)}</b><span>kabelek</span></div><div class="kpi"><b style="color:#18914e">{n_eu}</b><span>EU (bez cla)</span></div><div class="kpi"><b style="color:#7a5200">{n_new}</b><span>nových</span></div><div class="kpi"><b>40k Kč</b><span>kalk. renovace</span></div></div>
<h3>Pokrytí marketů</h3>{coverage_html}
<h2>⭐ TOP 10 KELLY</h2><div class="topgrid">{''.join(topcard(x,i+1) for i,x in enumerate(kelly[:10]))}</div>
<h2>⭐ TOP 10 BIRKIN</h2><div class="topgrid">{''.join(topcard(x,i+1) for i,x in enumerate(birk[:10]))}</div>
<h2>📋 Všechny kabelky — filtruj</h2>
<div class="fbar">
<button class="fbtn on" id="b_all" onclick="filt('all')">Vše ({len(items)})</button>
<button class="fbtn" id="b_keu" onclick="filt('keu')">👜 Kelly EU ({len(ke)})</button>
<button class="fbtn" id="b_beu" onclick="filt('beu')">👜 Birkin EU ({len(be)})</button>
<button class="fbtn" id="b_kjp" onclick="filt('kjp')">🌏 Kelly Japan ({len(kx)})</button>
<button class="fbtn" id="b_bjp" onclick="filt('bjp')">🌏 Birkin Japan ({len(bx)})</button>
<button class="fbtn fnew" id="b_new" onclick="filt('new')">🆕 Nové ({n_new})</button>
</div>
<table id="tbl">{TH}<tbody>{''.join(row(x) for x in sorted(items,key=lambda z:(z['model'],z['eur'])))}</tbody></table>
<script>
function filt(m){{document.querySelectorAll('#tbl tbody tr').forEach(function(tr){{var md=tr.dataset.model,rg=tr.dataset.reg,nw=tr.dataset.new,sh=true;
if(m=='keu')sh=(md=='kelly'&&rg=='eu');else if(m=='beu')sh=(md=='birkin'&&rg=='eu');
else if(m=='kjp')sh=(md=='kelly'&&rg=='xeu');else if(m=='bjp')sh=(md=='birkin'&&rg=='xeu');
else if(m=='new')sh=(nw=='1');tr.style.display=sh?'':'none';}});
document.querySelectorAll('.fbtn').forEach(function(b){{b.classList.remove('on');}});document.getElementById('b_'+m).classList.add('on');}}
</script>
<div class="note"><b>Cena</b>=inzerát · <b>Přibl. prodej</b>=odhad po renovaci · <b>Marže</b>=prodej−cena−40k · <b>Nabídka</b>=pro marži ~150k · <b>Strop</b>=max (marže ≥80k). „soukromý ✓"=Leboncoin/Kleinanzeigen bez provize. ⚠️ Levné vintage = ideál na renovaci, ale ověř stav i pravost. Odhady orientační.</div>
</div></body></html>"""
open(P("hermes-dostupne-kabelky.html"),"w",encoding="utf-8").write(HTML)
json.dump(sorted(set(list(seen)+[x["url"] for x in items])),open(P("hermes_seen.json"),"w",encoding="utf-8"),ensure_ascii=False)
print(f"REPORT {today}: {len(items)} kusu, {n_eu} EU, {n_new} novych. Markety: {markets}")
print("TOP 5 KELLY:")
for x in kelly[:5]: print(f"  {x['eur']:,} EUR | {x['title'][:38]} | {x['market']} | {x.get('country','')} | nabidni {(x['rec_eur'] or 0):,} EUR{' | NOVE' if x['new'] else ''}")
print("TOP 5 BIRKIN:")
for x in birk[:5]: print(f"  {x['eur']:,} EUR | {x['title'][:38]} | {x['market']} | {x.get('country','')} | nabidni {(x['rec_eur'] or 0):,} EUR{' | NOVE' if x['new'] else ''}")
