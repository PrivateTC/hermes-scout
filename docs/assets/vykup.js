(function(){
var V=window.__V||{};
var f=document.getElementById('vform');if(!f)return;
var ph=document.getElementById('ph'),upbtn=document.getElementById('upbtn'),thumbs=document.getElementById('thumbs'),sent=document.getElementById('sent'),sb=document.getElementById('vsubmit'),hp=document.getElementById('hp');
var files=[];
upbtn.addEventListener('click',function(){ph.click();});
ph.addEventListener('change',function(){for(var i=0;i<ph.files.length;i++)files.push(ph.files[i]);ph.value='';render();});
function render(){thumbs.innerHTML='';files.forEach(function(fl,idx){var u=URL.createObjectURL(fl);var d=document.createElement('div');d.className='th';d.innerHTML='<img src="'+u+'" alt=""><span class="x" data-i="'+idx+'">×</span>';thumbs.appendChild(d);});}
thumbs.addEventListener('click',function(e){if(e.target.classList.contains('x')){files.splice(parseInt(e.target.getAttribute('data-i'),10),1);render();}});
f.addEventListener('submit',function(e){e.preventDefault();if(hp&&hp.value)return;
var fd=new FormData();['name','contact','model','detail','condition','price'].forEach(function(n){if(f[n])fd.append(n,f[n].value);});
fd.append('lang',document.documentElement.lang||'');fd.append('page',location.href);fd.append('photoCount',files.length);
files.forEach(function(fl,i){fd.append('photo'+(i+1),fl,fl.name||('photo'+(i+1)+'.jpg'));});
sb.disabled=true;sb.textContent=V.sending||'...';
fetch(V.hook,{method:'POST',mode:'no-cors',body:fd}).then(function(){f.style.display='none';if(sent){sent.style.display='block';sent.scrollIntoView({behavior:'smooth',block:'center'});}}).catch(function(){sb.disabled=false;sb.textContent=V.err||V.submit||'!';});
});
})();
