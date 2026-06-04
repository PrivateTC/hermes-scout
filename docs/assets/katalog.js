(function(){
var L=window.__L,LOC=window.__LOC;
var RESALE={"kelly 25":700000,"kelly 28":680000,"kelly 32":520000,"kelly 35":480000,"kelly 20":560000,"birkin 25":650000,"birkin 30":640000,"birkin 35":520000,"birkin 40":470000,"kelly":560000,"birkin":600000};
var EURCZK=25,REPAIR=40000,MIN_M=80000,TGT_M=150000;
var EU=["Francie","Německo","Itálie","Belgie","Nizozemsko","Španělsko","Polsko","Irsko","Rakousko","Portugalsko","Lucembursko"];
var MKC={"Vestiaire":"#6b3fc0","eBay.de":"#1f6fd6","Leboncoin":"#e8642a","Kleinanzeigen":"#178a7a","eBay":"#1f6fd6"};
var ALLM=[["Vestiaire",L.c_d0],["eBay.de",L.c_d1],["Leboncoin",L.c_d2],["Kleinanzeigen",L.c_d3],["Buyee",L.c_d4],["eBay.fr/it/es",L.c_d5],["Vinted",L.c_d6]];
var esc=function(s){return (s||"").replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});};
var cz=function(n){return n==null?"—":Math.round(n).toLocaleString(LOC);};
var eu0=function(n){return (n||0).toLocaleString(LOC);};
function resale(s){s=(s||"").toLowerCase();var ks=Object.keys(RESALE).sort(function(a,b){return b.length-a.length;});for(var i=0;i<ks.length;i++)if(s.indexOf(ks[i])>=0)return RESALE[ks[i]];return null;}
function isEU(c){return EU.some(function(x){return (c||"").indexOf(x)>=0;});}
function mkt(m){var c=MKC[m]||"#555";return '<span class="mkt" style="background:'+c+'1a;color:'+c+'">'+m+'</span>';}
function reg(x){return '<span class="reg '+(x.eu?"reu":"rww")+'">'+(x.eu?L.c_eu:esc(x.country||"?")+" · "+L.c_duty)+'</span>';}
function sel(x){return x.priv?'<span class="sel priv">'+L.c_priv+'</span>':'<span class="sel mark">'+L.c_mark+'</span>';}
function newb(x){return x["new"]?'<span class="reg" style="background:#ffe1a8;color:#7a5200">'+L.c_new+'</span>':"";}
function compute(items){return items.map(function(d){var p=Math.round(d.eur*EURCZK);var r=resale(d.title)||resale(d.model);var margin=r!=null?r-p-REPAIR:null;var tgt=r!=null?r-REPAIR-TGT_M:null;var rec=tgt!=null?Math.max(Math.min(tgt,Math.round(p*0.9)),Math.round(p*0.6)):null;var ceil=r!=null?r-REPAIR-MIN_M:null;var flag=L.c_no,cls="no";if(margin&&margin>=TGT_M){flag=L.c_buy;cls="buy";}else if(margin&&margin>=MIN_M){flag=L.c_mid;cls="mid";}return Object.assign({},d,{p:p,resale:r,margin:margin,rec:rec,rec_eur:rec!=null?Math.round(rec/EURCZK):null,ceil:ceil,flag:flag,cls:cls,eu:isEU(d.country)});});}
function topcard(x,i){return '<div class="tc '+x.cls+'"><div class="rank">#'+i+'</div><div class="tc-b">'+
'<div class="tc-price">'+eu0(x.eur)+' €<small>'+cz(x.p)+' Kč</small></div>'+
'<div class="tc-title"><a href="'+x.url+'" target="_blank" rel="noopener">'+esc(x.title)+'</a> '+newb(x)+'</div>'+
'<div class="tc-tags">'+mkt(x.market)+' '+reg(x)+' '+sel(x)+'</div>'+
'<div class="tc-off">'+L.c_offer+' <b>'+eu0(x.rec_eur)+' €</b> · '+L.c_margin+' ~'+cz(x.margin)+' Kč</div>'+
'<a class="tc-link" href="'+x.url+'" target="_blank" rel="noopener">'+L.c_open+'</a></div></div>';}
function row(x){return '<tr class="'+x.cls+'" data-model="'+x.model+'" data-reg="'+(x.eu?"eu":"xeu")+'" data-new="'+(x["new"]?1:0)+'"><td>'+mkt(x.market)+'</td>'+
'<td class="title"><a href="'+x.url+'" target="_blank" rel="noopener">'+esc(x.title)+'</a> '+newb(x)+'<div>'+reg(x)+' '+sel(x)+'</div></td>'+
'<td class="price">'+eu0(x.eur)+' €<i>'+cz(x.p)+' Kč</i></td><td class="r">'+cz(x.resale)+' Kč</td>'+
'<td class="r mg">'+cz(x.margin)+' Kč</td><td class="r off">'+eu0(x.rec_eur)+' €<i>'+cz(x.rec)+' Kč</i></td>'+
'<td class="r">'+cz(x.ceil)+' Kč</td><td><span class="badge '+x.cls+'">'+x.flag+'</span></td><td><a class="go" href="'+x.url+'" target="_blank" rel="noopener">↗</a></td></tr>';}
var TH="<thead><tr><th>"+L.c_th_m+"</th><th>"+L.c_th_l+"</th><th class='price'>"+L.c_th_p+"</th><th class='r'>"+L.c_th_r+"</th><th class='r'>"+L.c_th_mg+"</th><th class='r'>"+L.c_th_o+"</th><th class='r'>"+L.c_th_c+"</th><th>"+L.c_th_h+"</th><th></th></tr></thead>";
function coverage(items,markets){var ms={};(markets||[]).forEach(function(m){ms[m.name]=m;});var cnt={};items.forEach(function(x){cnt[x.market]=(cnt[x.market]||0)+1;});
return '<div class="covgrid">'+ALLM.map(function(a){var nm=a[0],desc=a[1];var info=ms[nm],c=cnt[nm]||0;var st,clz;if(info&&info.status=="blocked"){st=L.c_cov_block;clz="cov-no";}else if(c>0||(info&&info.status=="ok")){st=L.c_cov_ok+" "+c+" "+L.c_cov_pcs;clz="cov-ok";}else if(info&&info.status=="skipped"){st="⏸ "+(info.note||"");clz="cov-sk";}else{st=L.c_cov_none;clz="cov-sk";}return '<div class="cov '+clz+'"><b>'+nm+'</b><span>'+st+'</span><i>'+desc+'</i></div>';}).join("")+'</div>';}
window.filt=function(m){document.querySelectorAll('#tbl tbody tr').forEach(function(tr){var md=tr.dataset.model,rg=tr.dataset.reg,nw=tr.dataset.new;var sh=true;if(m=='keu')sh=(md=='kelly'&&rg=='eu');else if(m=='beu')sh=(md=='birkin'&&rg=='eu');else if(m=='kjp')sh=(md=='kelly'&&rg=='xeu');else if(m=='bjp')sh=(md=='birkin'&&rg=='xeu');else if(m=='new')sh=(nw=='1');tr.style.display=sh?'':'none';});document.querySelectorAll('.fbtn').forEach(function(b){b.classList.remove('on');});document.getElementById('b_'+m).classList.add('on');};
fetch('../../data.json').then(function(r){return r.json();}).then(function(d){
 var items=compute(d.items);
 var kelly=items.filter(function(x){return x.model=='kelly';}).sort(function(a,b){return a.eur-b.eur;});
 var birk=items.filter(function(x){return x.model=='birkin';}).sort(function(a,b){return a.eur-b.eur;});
 var ke=kelly.filter(function(x){return x.eu;}),kx=kelly.filter(function(x){return !x.eu;}),be=birk.filter(function(x){return x.eu;}),bx=birk.filter(function(x){return !x.eu;});
 var n_eu=items.filter(function(x){return x.eu;}).length, n_new=items.filter(function(x){return x["new"];}).length;
 var all=items.slice().sort(function(a,b){return a.model<b.model?-1:a.model>b.model?1:a.eur-b.eur;});
 var h='<h1>'+L.c_h1+'</h1>'+
 '<p class="sub">'+esc((d.markets||[]).filter(function(m){return m.status=='ok';}).map(function(m){return m.name;}).join(", "))+' · '+d.date+' · '+L.c_subtail+'</p>'+
 '<div class="cards"><div class="kpi"><b>'+items.length+'</b><span>'+L.c_kpi1+'</span></div><div class="kpi"><b style="color:#18914e">'+n_eu+'</b><span>'+L.c_kpi2+'</span></div><div class="kpi"><b style="color:#7a5200">'+n_new+'</b><span>'+L.c_kpi3+'</span></div><div class="kpi"><b>40k Kč</b><span>'+L.c_kpi4+'</span></div></div>'+
 '<h3>'+L.c_cov+'</h3>'+coverage(items,d.markets)+
 '<h2>'+L.c_topk+'</h2><div class="topgrid">'+kelly.slice(0,10).map(function(x,i){return topcard(x,i+1);}).join("")+'</div>'+
 '<h2>'+L.c_topb+'</h2><div class="topgrid">'+birk.slice(0,10).map(function(x,i){return topcard(x,i+1);}).join("")+'</div>'+
 '<h2>'+L.c_allh+'</h2>'+
 '<div class="fbar">'+
 '<button class="fbtn on" id="b_all" onclick="filt(\'all\')">'+L.c_fall+' ('+items.length+')</button>'+
 '<button class="fbtn" id="b_keu" onclick="filt(\'keu\')">'+L.c_fkeu+' ('+ke.length+')</button>'+
 '<button class="fbtn" id="b_beu" onclick="filt(\'beu\')">'+L.c_fbeu+' ('+be.length+')</button>'+
 '<button class="fbtn" id="b_kjp" onclick="filt(\'kjp\')">'+L.c_fkjp+' ('+kx.length+')</button>'+
 '<button class="fbtn" id="b_bjp" onclick="filt(\'bjp\')">'+L.c_fbjp+' ('+bx.length+')</button>'+
 '<button class="fbtn fnew" id="b_new" onclick="filt(\'new\')">'+L.c_fnew+' ('+n_new+')</button></div>'+
 '<table id="tbl">'+TH+'<tbody>'+all.map(row).join("")+'</tbody></table>'+
 '<div class="note">'+L.c_note+'</div>';
 document.getElementById('app').innerHTML=h;
}).catch(function(e){document.getElementById('app').innerHTML='<div class="loading">'+L.c_err+e+'</div>';});
})();
