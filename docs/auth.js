/* ShowField Auth Module — injected on every page */
(function(){
  const API    = '';
  const TK_KEY = 'showfield_token';
  const US_KEY = 'showfield_user';

  // ── State ──────────────────────────────────────────────────────────────────
  let currentUser  = null;
  let favSet       = new Set();
  let rankingsMap  = {};        // uuid → {rank, notes}
  let syncPending  = false;

  // ── Token helpers ──────────────────────────────────────────────────────────
  function getToken(){ return localStorage.getItem(TK_KEY); }
  function setToken(t){ localStorage.setItem(TK_KEY, t); }
  function clearToken(){ localStorage.removeItem(TK_KEY); localStorage.removeItem(US_KEY); }

  // ── API helper ─────────────────────────────────────────────────────────────
  async function apiFetch(path, opts={}){
    const token = getToken();
    const headers = { 'Content-Type':'application/json', ...(opts.headers||{}) };
    if(token) headers['Authorization'] = 'Bearer '+token;
    const res = await fetch(API+path, { ...opts, headers });
    const data = await res.json().catch(()=>({}));
    if(!res.ok) throw Object.assign(new Error(data.error||'Request failed'), { status: res.status });
    return data;
  }

  // ── Public API (window.SF) ─────────────────────────────────────────────────
  window.SF = {
    getUser(){ return currentUser; },
    isLoggedIn(){ return !!currentUser; },
    getToken,

    // ── Favorites ──────────────────────────────────────────────────────────
    isFav(uuid){ return favSet.has(uuid); },
    async addFav(uuid){
      favSet.add(uuid);
      _updateFavUI(uuid, true);
      if(currentUser){ try{ await apiFetch('/api/favorites', {method:'POST', body:JSON.stringify({player_uuid:uuid})}); }catch(e){} }
    },
    async removeFav(uuid){
      favSet.delete(uuid);
      _updateFavUI(uuid, false);
      if(currentUser){ try{ await apiFetch(`/api/favorites/${uuid}`, {method:'DELETE'}); }catch(e){} }
    },
    async toggleFav(uuid){
      if(favSet.has(uuid)) await window.SF.removeFav(uuid);
      else await window.SF.addFav(uuid);
      return favSet.has(uuid);
    },
    getFavs(){ return [...favSet]; },

    // ── Rankings ──────────────────────────────────────────────────────────
    getRanking(uuid){ return rankingsMap[uuid] || null; },
    getAllRankings(){ return rankingsMap; },
    async setRanking(uuid, rank, notes){
      rankingsMap[uuid] = { rank, notes };
      if(currentUser){ try{ await apiFetch('/api/rankings', {method:'POST', body:JSON.stringify({player_uuid:uuid, rank, notes})}); }catch(e){} }
    },
    async deleteRanking(uuid){
      delete rankingsMap[uuid];
      if(currentUser){ try{ await apiFetch(`/api/rankings/${uuid}`, {method:'DELETE'}); }catch(e){} }
    },

    // ── Teams (for team-builder) ──────────────────────────────────────────
    async getTeams(){
      if(!currentUser) return null;
      try{ const d = await apiFetch('/api/teams'); return d.teams; }catch(e){ return null; }
    },
    async saveTeam(name, lineup){
      if(!currentUser) return null;
      try{ const d = await apiFetch('/api/teams', {method:'POST', body:JSON.stringify({name, lineup})}); return d.team; }catch(e){ return null; }
    },
    async updateTeam(id, name, lineup){
      if(!currentUser) return null;
      try{ const d = await apiFetch(`/api/teams/${id}`, {method:'PUT', body:JSON.stringify({name, lineup})}); return d.team; }catch(e){ return null; }
    },
    async deleteTeam(id){
      if(!currentUser) return;
      try{ await apiFetch(`/api/teams/${id}`, {method:'DELETE'}); }catch(e){}
    },

    // ── Auth actions ──────────────────────────────────────────────────────
    openLogin(){ document.getElementById('sfAuthModal').classList.add('open'); document.getElementById('sfAuthTab-login').click(); },
    openRegister(){ document.getElementById('sfAuthModal').classList.add('open'); document.getElementById('sfAuthTab-register').click(); },
    logout(){
      currentUser=null; favSet=new Set(); rankingsMap={};
      clearToken();
      _updateNav();
      // Let page reload to reset any API-synced state
      location.reload();
    }
  };

  // ── Private helpers ────────────────────────────────────────────────────────
  function _updateFavUI(uuid, isFav){
    document.querySelectorAll(`[data-fav="${uuid}"]`).forEach(el=>{
      el.classList.toggle('fav-active', isFav);
      el.title = isFav ? 'Remove from favorites' : 'Add to favorites';
    });
  }

  function _updateNav(){
    const authEl = document.getElementById('sfNavAuth');
    if(!authEl) return;
    if(currentUser){
      authEl.innerHTML = `
        <div class="sf-user-menu">
          <button class="sf-user-btn" id="sfUserBtn">
            <span class="sf-avatar">${currentUser.username[0].toUpperCase()}</span>
            <span class="sf-username">${currentUser.username}</span>
            <span style="font-size:.7rem;color:var(--muted)">▾</span>
          </button>
          <div class="sf-user-drop" id="sfUserDrop">
            <a href="./account.html" class="sf-drop-item">My Account</a>
            <button class="sf-drop-item sf-drop-btn" onclick="SF.logout()">Log Out</button>
          </div>
        </div>`;
      document.getElementById('sfUserBtn').addEventListener('click', e=>{
        e.stopPropagation();
        document.getElementById('sfUserDrop').classList.toggle('open');
      });
      document.addEventListener('click', ()=>{ document.getElementById('sfUserDrop')?.classList.remove('open'); });
    } else {
      authEl.innerHTML = `<button class="btn btn-ghost btn-sm" onclick="SF.openLogin()">Log In</button>`;
    }
  }

  // ── Auth Modal ────────────────────────────────────────────────────────────
  function _injectStyles(){
    const style = document.createElement('style');
    style.textContent = `
      .sf-modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(6px);z-index:1000;align-items:center;justify-content:center;}
      .sf-modal-overlay.open{display:flex;}
      .sf-modal{background:#101829;border:1px solid rgba(255,255,255,.1);border-radius:20px;width:100%;max-width:420px;overflow:hidden;box-shadow:0 24px 64px rgba(0,0,0,.6);position:relative;}
      .sf-modal-header{padding:24px 24px 0;display:flex;justify-content:space-between;align-items:center;}
      .sf-modal-logo{font-family:'Bebas Neue',sans-serif;font-size:1.4rem;letter-spacing:.06em;display:flex;align-items:center;gap:8px;}
      .sf-modal-logo .dot{width:7px;height:7px;border-radius:50%;background:#e03030;box-shadow:0 0 6px #ff4545;}
      .sf-modal-close{background:none;border:none;color:rgba(255,255,255,.4);font-size:1.4rem;cursor:pointer;padding:4px 8px;line-height:1;transition:color .15s;}
      .sf-modal-close:hover{color:#fff;}
      .sf-tabs{display:flex;gap:0;padding:20px 24px 0;}
      .sf-tab{flex:1;padding:10px;font-family:'DM Sans',sans-serif;font-weight:700;font-size:.9rem;background:none;border:none;border-bottom:2px solid rgba(255,255,255,.08);color:rgba(255,255,255,.4);cursor:pointer;transition:all .15s;}
      .sf-tab.active{color:#fff;border-bottom-color:#e03030;}
      .sf-tab-pane{display:none;padding:20px 24px 28px;}
      .sf-tab-pane.active{display:block;}
      .sf-field{margin-bottom:14px;}
      .sf-label{font-size:.78rem;font-weight:700;color:rgba(255,255,255,.5);letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px;display:block;}
      .sf-input{width:100%;background:#141f33;border:1px solid rgba(255,255,255,.1);color:#e8edf8;border-radius:10px;padding:11px 14px;font-family:'DM Sans',sans-serif;font-size:.9rem;outline:none;transition:border-color .15s;}
      .sf-input:focus{border-color:#e03030;}
      .sf-btn-submit{width:100%;padding:12px;border-radius:10px;background:#e03030;color:#fff;font-family:'DM Sans',sans-serif;font-weight:700;font-size:.95rem;border:none;cursor:pointer;margin-top:4px;transition:opacity .15s;}
      .sf-btn-submit:hover{opacity:.88;}
      .sf-err{font-size:.82rem;color:#ff4545;margin-bottom:10px;min-height:1.2em;}
      .sf-switch{font-size:.82rem;color:rgba(255,255,255,.4);text-align:center;margin-top:14px;}
      .sf-switch button{background:none;border:none;color:#6fa3f5;cursor:pointer;font-family:'DM Sans',sans-serif;font-size:.82rem;padding:0;}
      /* Nav user menu */
      .sf-user-menu{position:relative;}
      .sf-user-btn{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:#e8edf8;border-radius:999px;padding:5px 12px 5px 7px;display:flex;align-items:center;gap:7px;cursor:pointer;font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:600;transition:background .15s;}
      .sf-user-btn:hover{background:rgba(255,255,255,.1);}
      .sf-avatar{width:26px;height:26px;border-radius:50%;background:#e03030;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.8rem;flex-shrink:0;}
      .sf-username{max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
      .sf-user-drop{display:none;position:absolute;top:calc(100% + 6px);right:0;background:#101829;border:1px solid rgba(255,255,255,.1);border-radius:12px;min-width:160px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,.4);z-index:200;}
      .sf-user-drop.open{display:block;}
      .sf-drop-item{display:block;width:100%;padding:11px 16px;font-family:'DM Sans',sans-serif;font-size:.875rem;font-weight:500;color:#e8edf8;text-decoration:none;transition:background .12s;}
      .sf-drop-item:hover{background:rgba(255,255,255,.06);}
      .sf-drop-btn{background:none;border:none;cursor:pointer;text-align:left;}
    `;
    document.head.appendChild(style);
  }

  function _injectModal(){
    const el = document.createElement('div');
    el.id = 'sfAuthModal';
    el.className = 'sf-modal-overlay';
    el.innerHTML = `
      <div class="sf-modal">
        <div class="sf-modal-header">
          <div class="sf-modal-logo"><div class="dot"></div>ShowField</div>
          <button class="sf-modal-close" onclick="document.getElementById('sfAuthModal').classList.remove('open')">×</button>
        </div>
        <div class="sf-tabs">
          <button class="sf-tab active" id="sfAuthTab-login" onclick="sfSwitchTab('login')">Log In</button>
          <button class="sf-tab" id="sfAuthTab-register" onclick="sfSwitchTab('register')">Sign Up</button>
        </div>
        <!-- LOGIN -->
        <div class="sf-tab-pane active" id="sfPane-login">
          <div class="sf-err" id="sfLoginErr"></div>
          <div class="sf-field"><label class="sf-label">Email</label><input class="sf-input" id="sfLoginEmail" type="email" placeholder="you@example.com" autocomplete="email"/></div>
          <div class="sf-field"><label class="sf-label">Password</label><input class="sf-input" id="sfLoginPass" type="password" placeholder="••••••••" autocomplete="current-password"/></div>
          <button class="sf-btn-submit" id="sfLoginBtn">Log In</button>
          <div class="sf-switch">Don't have an account? <button onclick="sfSwitchTab('register')">Sign Up</button></div>
        </div>
        <!-- REGISTER -->
        <div class="sf-tab-pane" id="sfPane-register">
          <div class="sf-err" id="sfRegErr"></div>
          <div class="sf-field"><label class="sf-label">Username</label><input class="sf-input" id="sfRegUser" type="text" placeholder="YourUsername" autocomplete="username"/></div>
          <div class="sf-field"><label class="sf-label">Email</label><input class="sf-input" id="sfRegEmail" type="email" placeholder="you@example.com" autocomplete="email"/></div>
          <div class="sf-field"><label class="sf-label">Password</label><input class="sf-input" id="sfRegPass" type="password" placeholder="Min 6 characters" autocomplete="new-password"/></div>
          <button class="sf-btn-submit" id="sfRegBtn">Create Account</button>
          <div class="sf-switch">Already have an account? <button onclick="sfSwitchTab('login')">Log In</button></div>
        </div>
      </div>`;
    document.body.appendChild(el);
    // Close on backdrop click
    el.addEventListener('click', e=>{ if(e.target===el) el.classList.remove('open'); });
  }

  window.sfSwitchTab = function(tab){
    ['login','register'].forEach(t=>{
      document.getElementById(`sfAuthTab-${t}`)?.classList.toggle('active', t===tab);
      document.getElementById(`sfPane-${t}`)?.classList.toggle('active', t===tab);
    });
    document.getElementById('sfLoginErr').textContent='';
    document.getElementById('sfRegErr').textContent='';
  };

  function _bindForms(){
    document.getElementById('sfLoginBtn').addEventListener('click', async()=>{
      const email = document.getElementById('sfLoginEmail').value.trim();
      const pass  = document.getElementById('sfLoginPass').value;
      const errEl = document.getElementById('sfLoginErr');
      errEl.textContent='';
      try{
        const data = await apiFetch('/api/auth/login', {method:'POST', body:JSON.stringify({email, password:pass})});
        setToken(data.token);
        currentUser = data.user;
        localStorage.setItem(US_KEY, JSON.stringify(data.user));
        document.getElementById('sfAuthModal').classList.remove('open');
        await _loadUserData();
        _updateNav();
        if(window._onAuthReady) window._onAuthReady(currentUser);
      }catch(e){ errEl.textContent = e.message; }
    });

    document.getElementById('sfRegBtn').addEventListener('click', async()=>{
      const username = document.getElementById('sfRegUser').value.trim();
      const email    = document.getElementById('sfRegEmail').value.trim();
      const pass     = document.getElementById('sfRegPass').value;
      const errEl    = document.getElementById('sfRegErr');
      errEl.textContent='';
      try{
        const data = await apiFetch('/api/auth/register', {method:'POST', body:JSON.stringify({username, email, password:pass})});
        setToken(data.token);
        currentUser = data.user;
        localStorage.setItem(US_KEY, JSON.stringify(data.user));
        document.getElementById('sfAuthModal').classList.remove('open');
        await _loadUserData();
        _updateNav();
        if(window._onAuthReady) window._onAuthReady(currentUser);
      }catch(e){ errEl.textContent = e.message; }
    });

    // Enter key on login/register fields
    ['sfLoginEmail','sfLoginPass'].forEach(id => {
      document.getElementById(id).addEventListener('keydown', e => { if(e.key==='Enter') document.getElementById('sfLoginBtn').click(); });
    });
    ['sfRegUser','sfRegEmail','sfRegPass'].forEach(id => {
      document.getElementById(id).addEventListener('keydown', e => { if(e.key==='Enter') document.getElementById('sfRegBtn').click(); });
    });
  }

  async function _loadUserData(){
    if(!currentUser || !getToken()) return;
    try{
      const [favData, rankData] = await Promise.all([
        apiFetch('/api/favorites').catch(()=>({favorites:[]})),
        apiFetch('/api/rankings').catch(()=>({rankings:[]}))
      ]);
      favSet = new Set(favData.favorites || []);
      rankingsMap = {};
      (rankData.rankings||[]).forEach(r=>{ rankingsMap[r.player_uuid]={rank:r.rank, notes:r.notes}; });
    }catch(e){}
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  async function boot(){
    _injectStyles();
    _injectModal();
    _bindForms();

    const token = getToken();
    if(token){
      try{
        const data = await apiFetch('/api/auth/me');
        currentUser = data.user;
        localStorage.setItem(US_KEY, JSON.stringify(data.user));
        await _loadUserData();
      }catch(e){
        clearToken();
        currentUser = null;
      }
    }

    _updateNav();
    if(window._onAuthReady) window._onAuthReady(currentUser);
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
