fetch('/api/me').then(r=>r.ok?r.json():null).then(data=>{if(data?.ok){document.getElementById('loginBtn').hidden=true;document.getElementById('dashboardLink').hidden=false}}).catch(()=>{});
