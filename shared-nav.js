/* Shared navigation: one source of truth across ReFound pages. */
(()=>{
 const current=location.pathname.split('/').pop()||'index.html';
 const lang=()=>localStorage.getItem('refound_lang')==='en'?'en':'ar';
 const l=(ar,en)=>lang()==='ar'?ar:en;
 const links=[['index.html','الرئيسية','Home'],['dashboard.html','لوحة التحكم','Dashboard'],['reports.html','البلاغات','Reports'],['report.html','إضافة بلاغ','Add Report'],['matches.html','المطابقة الذكية','Smart Matches'],['claims.html','الرسائل والطلبات','Messages'],['notifications.html','الإشعارات','Notifications']];
 const bar=document.createElement('div');bar.id='rfTopbar';
 bar.innerHTML=`<div class="rf-nav-inner"><a class="rf-brand" href="index.html" aria-label="ReFound home"><img src="assets/refound-logo.png" alt="ReFound original logo"></a><button class="rf-action rf-menu" id="rfMenu" type="button" aria-expanded="false">☰</button><nav class="rf-links" id="rfLinks" aria-label="Main navigation"></nav><div class="rf-actions"><button type="button" class="rf-action" id="rfLanguage" aria-label="Change language">AR / EN</button><div class="rf-profile" id="rfProfile" hidden><span class="rf-avatar" id="rfAvatar">S</span><span class="rf-user"><strong id="rfName"></strong><small id="rfEmail"></small></span></div><a class="rf-action" href="login.html" id="rfAuth"></a></div></div>`;
 document.body.prepend(bar);
 const nav=bar.querySelector('#rfLinks'),auth=bar.querySelector('#rfAuth');
 let isAdmin=false,hasUser=false;
 function redraw(){nav.replaceChildren();const all=isAdmin?[...links,['admin.html','الإدارة','Admin']]:links;for(const [href,ar,en] of all){const a=document.createElement('a');a.href=href;a.textContent=l(ar,en);if(href===current)a.setAttribute('aria-current','page');nav.append(a)}auth.textContent=hasUser?l('خروج','Logout'):l('دخول','Login');document.documentElement.dir=lang()==='ar'?'rtl':'ltr';document.documentElement.lang=lang();}
 bar.querySelector('#rfMenu').onclick=()=>{const on=bar.classList.toggle('rf-open');bar.querySelector('#rfMenu').setAttribute('aria-expanded',String(on))};
 bar.querySelector('#rfLanguage').onclick=()=>{
  // Delegate to each legacy page's own language controller to keep page translations in sync.
  const previous=lang();
  const original=Array.from(document.querySelectorAll('#langBtn,#authLang,#language')).find(e=>!bar.contains(e));
  if(original) original.click();
  else localStorage.setItem('refound_lang',lang()==='ar'?'en':'ar');
  // Some older pages use a different storage key; always normalize it.
  const wanted=previous==='ar'?'en':'ar';
  // If legacy handler did not update the stored value, toggle it here.
  if(lang()===previous) localStorage.setItem('refound_lang',wanted);
  redraw();
 };

 async function profile(){try{const r=await fetch('/api/me',{credentials:'same-origin'});if(!r.ok)throw new Error('guest');const data=await r.json();const user=data.user||data;hasUser=true;isAdmin=Boolean(user.is_admin||user.role==='admin');bar.querySelector('#rfProfile').hidden=false;bar.querySelector('#rfName').textContent=user.full_name||user.name||'Student';bar.querySelector('#rfEmail').textContent=user.email||'';bar.querySelector('#rfAvatar').textContent=(user.full_name||user.name||'S').trim()[0].toUpperCase();auth.href='#';auth.onclick=async e=>{e.preventDefault();try{await fetch('/api/logout',{method:'POST',credentials:'same-origin'})}catch(_){}location.href='login.html'};}catch(e){hasUser=false;bar.querySelector('#rfProfile').hidden=true}redraw()}
 redraw();profile();
})();
