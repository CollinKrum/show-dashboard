(function(){
  function esc(v){return String(v ?? '').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));}
  function num(v){const n=Number(String(v ?? '').replace(/[$,% ,]/g,''));return Number.isFinite(n)?n:null;}
  function money(v){const n=num(v);return n==null?'--':n.toLocaleString();}
  function pct(v){const n=num(v);return n==null?'--':`${n.toFixed(1)}%`;}
  function val(card,names){for(const n of names){if(card && card[n] !== undefined && card[n] !== null && card[n] !== '') return card[n];}return '';}
  function stat(label,value,cls=''){
    return `<div class="sfm-stat"><span>${esc(label)}</span><b class="${cls}">${esc(value === '' || value == null ? '--' : value)}</b></div>`;
  }
  function inject(){
    if(document.getElementById('sfm-style')) return;
    const style=document.createElement('style');
    style.id='sfm-style';
    style.textContent=`
      .clickable-card{cursor:pointer}.clickable-card:hover{outline:1px solid rgba(86,182,255,.35)}
      .sfm-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.68);z-index:9999;display:none;align-items:center;justify-content:center;padding:16px}
      .sfm-backdrop.open{display:flex}
      .sfm-modal{width:min(920px,100%);max-height:90vh;overflow:auto;background:linear-gradient(180deg,#101b2d,#14243b);border:1px solid rgba(255,255,255,.12);border-radius:22px;box-shadow:0 24px 80px rgba(0,0,0,.55);color:#edf4ff}
      .sfm-head{display:grid;grid-template-columns:96px 1fr auto;gap:16px;align-items:center;padding:18px;border-bottom:1px solid rgba(255,255,255,.08)}
      .sfm-img{width:96px;height:128px;object-fit:cover;border-radius:14px;background:#07101d;border:1px solid rgba(255,255,255,.1)}
      .sfm-title h2{margin:0 0 6px;font-size:1.45rem}.sfm-title p{margin:0;color:#9fb2cd}.sfm-close{border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.06);color:#edf4ff;border-radius:12px;padding:10px 12px;cursor:pointer}
      .sfm-body{padding:18px}.sfm-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}.sfm-stat{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:12px}.sfm-stat span{display:block;color:#9fb2cd;font-size:.8rem;margin-bottom:5px}.sfm-stat b{font-size:1.05rem}.sfm-good{color:#78f0a3}.sfm-bad{color:#ff7b7b}.sfm-gold{color:#ffd56a}.sfm-section{margin-top:14px}.sfm-section h3{margin:0 0 10px;font-size:1rem}.sfm-tags{display:flex;gap:8px;flex-wrap:wrap}.sfm-tag{padding:6px 9px;border-radius:999px;background:rgba(86,182,255,.1);border:1px solid rgba(86,182,255,.2);color:#cdeaff;font-size:.8rem}
      @media(max-width:640px){.sfm-head{grid-template-columns:72px 1fr}.sfm-close{grid-column:1/-1}.sfm-img{width:72px;height:96px}.sfm-grid{grid-template-columns:repeat(2,1fr)}}
    `;
    document.head.appendChild(style);
    const wrap=document.createElement('div');
    wrap.id='sfm-backdrop';wrap.className='sfm-backdrop';wrap.onclick=e=>{if(e.target.id==='sfm-backdrop') closeCardModal();};
    document.body.appendChild(wrap);
    document.addEventListener('keydown',e=>{if(e.key==='Escape') closeCardModal();});
  }
  window.openCardModal=function(card){
    inject();
    const name=val(card,['name','player_name','card_name']);
    const img=val(card,['img','image','image_url','card_image','card_img','card_art']);
    const pos=val(card,['display_position','position','pos']);
    const team=val(card,['team_short','team','team_abbrev']);
    const series=val(card,['series','card_series']);
    const rarity=val(card,['rarity','tier']);
    const profit=num(val(card,['profit_after_tax','profit','net_profit']));
    const roi=num(val(card,['roi','roi_pct','return_pct']));
    const tags=Array.isArray(card.tags)?card.tags:String(card.tags||'').split(',').map(s=>s.trim()).filter(Boolean);
    const html=`
      <div class="sfm-modal">
        <div class="sfm-head">
          ${img?`<img class="sfm-img" src="${esc(img)}" onerror="this.style.display='none'">`:`<div class="sfm-img"></div>`}
          <div class="sfm-title"><h2>${esc(name)}</h2><p>${esc(pos)} · ${esc(team)} · ${esc(series)} · ${esc(rarity)}</p></div>
          <button class="sfm-close" onclick="closeCardModal()">Close</button>
        </div>
        <div class="sfm-body">
          <div class="sfm-grid">
            ${stat('OVR',val(card,['ovr','overall','rating']),'sfm-gold')}
            ${stat('Buy',money(val(card,['best_buy_price','buy_price','buy']))) }
            ${stat('Sell',money(val(card,['best_sell_price','sell_price','sell']))) }
            ${stat('Profit',money(profit),profit>=0?'sfm-good':'sfm-bad')}
            ${stat('ROI',pct(roi),'sfm-gold')}
            ${stat('Confidence',val(card,['flip_confidence'])?`${val(card,['flip_confidence'])}/100`:'--','sfm-good')}
            ${stat('Age',val(card,['age']))}
            ${stat('Hand',`${val(card,['bat_hand','bats','bat']) || '--'} / ${val(card,['throw_hand','throws','throw']) || '--'}`)}
          </div>
          <div class="sfm-section"><h3>Hitting / Fielding</h3><div class="sfm-grid">
            ${stat('CON L/R',`${val(card,['contact_l']) || '--'} / ${val(card,['contact_r']) || '--'}`)}
            ${stat('POW L/R',`${val(card,['power_l']) || '--'} / ${val(card,['power_r']) || '--'}`)}
            ${stat('Speed',val(card,['speed']))}
            ${stat('Fielding',val(card,['fielding']))}
          </div></div>
          <div class="sfm-section"><h3>Pitching</h3><div class="sfm-grid">
            ${stat('Stamina',val(card,['stamina']))}
            ${stat('Control',val(card,['control']))}
            ${stat('Velocity',val(card,['velocity']))}
            ${stat('Break',val(card,['break']))}
          </div></div>
          ${tags.length?`<div class="sfm-section"><h3>Tags</h3><div class="sfm-tags">${tags.map(t=>`<span class="sfm-tag">${esc(t)}</span>`).join('')}</div></div>`:''}
          ${val(card,['quirks'])?`<div class="sfm-section"><h3>Quirks</h3><p style="color:#9fb2cd;line-height:1.5">${esc(val(card,['quirks']))}</p></div>`:''}
        </div>
      </div>`;
    const back=document.getElementById('sfm-backdrop');back.innerHTML=html;back.classList.add('open');
  };
  window.closeCardModal=function(){const b=document.getElementById('sfm-backdrop');if(b)b.classList.remove('open');};
})();
