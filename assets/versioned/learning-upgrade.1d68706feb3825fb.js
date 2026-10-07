(() => {
  'use strict';
  const menu = document.querySelector('.em-mobile');
  if (menu) {
    menu.addEventListener('click', event => { if (event.target.closest('a')) menu.open = false; });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && menu.open) { menu.open = false; menu.querySelector('summary').focus(); } });
    document.addEventListener('click', event => { if (!menu.contains(event.target)) menu.open = false; });
  }
  const area = document.querySelector('[data-video-player]');
  if (!area) return;
  let opener;
  const allowed = new Set(['avpJfW7eIV0', 'f_skFu40U04', 'UIXUaBZdNXU']);
  document.querySelectorAll('[data-play-video]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => {
      const id = button.dataset.playVideo;
      if (!allowed.has(id)) return;
      area.querySelector('iframe')?.remove();
      const frame = document.createElement('iframe');
      frame.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`;
      frame.title = button.dataset.videoTitle;
      frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      frame.allowFullscreen = true;
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      area.prepend(frame);
      area.hidden = false;
      opener = button;
      area.querySelector('button').focus();
    });
  });
  area.querySelector('button').addEventListener('click', () => {
    area.querySelector('iframe')?.remove();
    area.hidden = true;
    opener?.focus();
  });
})();
