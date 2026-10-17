/* Load a single map only as its reserved area approaches the viewport. */
(()=>{
 const start=slot=>{if(slot.dataset.kakaoStarted)return;const template=slot.querySelector('template'),frame=template?.content.querySelector('iframe');if(!frame)return;slot.dataset.kakaoStarted='true';slot.replaceChildren(frame.cloneNode(true));};
 const observer='IntersectionObserver'in window?new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){observer.unobserve(e.target);start(e.target)}},{rootMargin:'192px 0px'}):null;
 const bind=root=>root.querySelectorAll('.kd-map-slot[data-kakao-src]').forEach(slot=>{if(observer)observer.observe(slot);else start(slot)});
 bind(document);
 document.querySelectorAll('[data-kakao-select]').forEach(select=>{
  const section=select.closest('[data-kakao-hub]'),panel=section.querySelector('.kd-hub-panel'),status=section.querySelector('.kd-hub-status');
  select.addEventListener('change',async()=>{
   const previous=select.dataset.selected,chosen=select.selectedOptions[0];
   if(!chosen||chosen.value===previous)return;
   select.disabled=true;status.textContent='선택한 지점의 위치를 불러오고 있습니다.';
   try{
    const url=chosen.dataset.kakaoEntry;
    if(!/^\/assets\/kakao-directions\/entry-[a-f0-9]+\.json$/.test(url))throw Error('Invalid location data');
    const response=await fetch(url,{credentials:'omit'});if(!response.ok)throw Error('Location unavailable');
    const data=await response.json();if(data.branch!==chosen.value||typeof data.html!=='string')throw Error('Location mismatch');
    const template=document.createElement('template');template.innerHTML=data.html;
    // A noscript fallback parsed as an HTML fragment must not hide an active map.
    template.content.querySelectorAll('noscript').forEach(node=>node.remove());
    if(template.content.querySelector('script,link,a,button'))throw Error('Unexpected location markup');
    if(observer)panel.querySelectorAll('.kd-map-slot').forEach(slot=>observer.unobserve(slot));
    panel.replaceChildren(template.content);bind(panel);select.dataset.selected=chosen.value;status.textContent='';
   }catch{select.value=previous;status.textContent='지점 정보를 불러오지 못했습니다. 현재 표시된 지점명과 주소를 확인해 주세요.';}
   finally{select.disabled=false;}
  });
 });
})();
