/* The supplied Kakao embed runs inside a script-only sandbox. Keep its
   attribution, pan and zoom controls; remove outgoing navigation and contact UI. */
(()=>{
 let scheduled=false;
 const clean=()=>{
  scheduled=false;
  document.querySelectorAll('.phone,.wrap_btn_roadview').forEach(e=>e.remove());
  document.querySelectorAll('a,[role="link"]').forEach(e=>{
   const span=document.createElement('span');
   for(const a of e.attributes)if(!/^(?:href|target|rel|role|tabindex|on.*)$/i.test(a.name))span.setAttribute(a.name,a.value);
   span.classList.add('kd-disabled-link');
   span.append(...e.childNodes);e.replaceWith(span);
  });
  document.querySelectorAll('img[alt*="이동"]').forEach(e=>e.alt='카카오맵');
  if(document.querySelector('.root_daum_roughmap .wrap_map')){
   const status=document.querySelector('.kd-frame-status');if(status)status.hidden=true;
   document.documentElement.dataset.mapReady='true';
  }
 };
 new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(clean)}}).observe(document.documentElement,{childList:true,subtree:true});
 document.addEventListener('click',e=>{if(e.target.closest('.kd-disabled-link')){e.preventDefault();e.stopImmediatePropagation()}},true);
 clean();
 setTimeout(()=>{const e=document.querySelector('.kd-frame-status');if(e&&!e.hidden)e.textContent='지도 연결이 지연되고 있습니다. 위의 지도 이미지와 아래 주소를 확인해 주세요.'},12000);
})();
