const translations = {
 ar:{back:'العودة للرئيسية',kicker:'REFOUND • مجتمع الجامعة',storyTitle:'مع بعض، <span>نرجّع اللي ضاع.</span>',storyDesc:'منصة طلابية للإبلاغ عن المفقودات والموجودات.',highlightTitle:'مطابقة ذكية',highlightDesc:'هنضيف المطابقة باستخدام NLP في مرحلة قادمة.',fullName:'الاسم بالكامل',emailLabel:'البريد الجامعي',passwordLabel:'كلمة المرور',confirmLabel:'تأكيد كلمة المرور',show:'إظهار',hide:'إخفاء',remember:'تذكرني',forgot:'نسيت كلمة المرور؟',agreement:'أوافق على استخدام الخدمة بمسؤولية وإدخال بيانات صحيحة.',privacy:'الحسابات بتتخزن محليًا في SQLite وكلمات المرور بتتخزن بشكل مُجزّأ (Hash).',login:{cardTitle:'أهلًا برجوعك!',cardDesc:'سجّل دخولك لحسابك.',submit:'تسجيل الدخول',bottomText:'معندكش حساب؟',bottomLink:'إنشاء حساب'},register:{cardTitle:'إنشاء حساب جديد',cardDesc:'انضم لـ ReFound بحساب جامعي.',submit:'إنشاء الحساب',bottomText:'عندك حساب؟',bottomLink:'تسجيل الدخول'},mismatch:'كلمتا المرور غير متطابقتين.',invalid:'راجع البيانات المطلوبة. كلمة المرور من 8 إلى 128 حرفًا.',recover:'استعادة كلمة المرور مش متاحة لسه. متشاركش كلمة المرور مع حد.',unknown:'حصل خطأ. حاول مرة تانية.'},
 en:{back:'Back to home',kicker:'REFOUND • UNIVERSITY COMMUNITY',storyTitle:'Together, we <span>find what matters.</span>',storyDesc:'A campus space for lost and found items.',highlightTitle:'Smart matching',highlightDesc:'NLP matching will be added in a later phase.',fullName:'Full name',emailLabel:'University email',passwordLabel:'Password',confirmLabel:'Confirm password',show:'Show',hide:'Hide',remember:'Remember me',forgot:'Forgot password?',agreement:'I agree to use the service responsibly and provide accurate information.',privacy:'Accounts are stored locally in SQLite. Passwords are stored as secure hashes.',login:{cardTitle:'Welcome back!',cardDesc:'Log in to your account.',submit:'Log in',bottomText:'New to ReFound?',bottomLink:'Create account'},register:{cardTitle:'Create an account',cardDesc:'Join ReFound with your campus account.',submit:'Create account',bottomText:'Already have an account?',bottomLink:'Log in'},mismatch:'Passwords do not match.',invalid:'Check the required fields. Password must be 8–128 characters.',recover:'Password recovery is not available yet. Never share your password.',unknown:'Something went wrong. Try again.'}
};
const page=document.body.dataset.page;
let lang=localStorage.getItem('refound_lang')==='en'?'en':'ar';
const $=id=>document.getElementById(id);
function translate(){const t=translations[lang];document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';document.querySelectorAll('[data-auth]').forEach(el=>{const key=el.dataset.auth;const value=t[key]??t[page][key];if(value!==undefined)el.innerHTML=value});$('authLangText').textContent=lang==='ar'?'EN':'عربي';document.querySelectorAll('.toggle-pass').forEach(btn=>btn.textContent=t[$(btn.dataset.target).type==='password'?'show':'hide']);}
$('authLang').addEventListener('click',()=>{lang=lang==='ar'?'en':'ar';localStorage.setItem('refound_lang',lang);translate()});
document.querySelectorAll('.toggle-pass').forEach(btn=>btn.addEventListener('click',()=>{const field=$(btn.dataset.target);field.type=field.type==='password'?'text':'password';btn.textContent=translations[lang][field.type==='password'?'show':'hide']}));
function status(message,isError=true){const box=$('authStatus');box.hidden=false;box.textContent=message;box.style.borderColor=isError?'#e3a8a8':'#9ddbd3';}
$('authForm').addEventListener('submit',async e=>{
 e.preventDefault();$('authStatus').hidden=true;const form=e.currentTarget;
 if(!form.checkValidity()){form.reportValidity();status(translations[lang].invalid);return}
 const password=$('password').value;
 if(page==='register'&&password!==$('confirmPassword').value){status(translations[lang].mismatch);return}
 const payload={email:$('email').value.trim(),password};
 if(page==='register')Object.assign(payload,{fullName:$('fullName').value.trim(),confirmPassword:$('confirmPassword').value,agreement:$('agreement').checked});
 else payload.remember=$('remember').checked;
 const button=form.querySelector('[type="submit"]');button.disabled=true;
 try{const response=await fetch('/api/'+page,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok){status(result.message||translations[lang].unknown);return}window.location.href='dashboard.html';}
 catch(err){status(translations[lang].unknown+' — Start the Flask server first.');}
 finally{button.disabled=false}
});
if($('forgotLink'))$('forgotLink').addEventListener('click',e=>{e.preventDefault();status(translations[lang].recover)});
translate();
