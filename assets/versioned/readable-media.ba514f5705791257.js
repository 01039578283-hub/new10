(() => {
  'use strict';
  let opener, dialog;
  function closeImage() {
    if (!dialog) return;
    dialog.close(); dialog.remove(); dialog = null;
    opener?.focus(); opener = null;
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[data-image-enlarge]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !HTMLDialogElement.prototype.showModal) return;
    event.preventDefault(); closeImage(); opener = link;
    const thumbnail = link.querySelector('img');
    dialog = document.createElement('dialog'); dialog.className = 'readable-dialog'; dialog.setAttribute('aria-label', '본문·지도 이미지 확대');
    const toolbar = document.createElement('div'); toolbar.className = 'readable-toolbar';
    const zoom = document.createElement('button'); zoom.type = 'button'; zoom.textContent = '화면에 맞추기'; zoom.setAttribute('aria-pressed', 'false');
    const originalLink = document.createElement('a'); originalLink.href = link.href; originalLink.target = '_blank'; originalLink.rel = 'noopener'; originalLink.textContent = '원본 파일 열기';
    const close = document.createElement('button'); close.type = 'button'; close.textContent = '닫기'; close.addEventListener('click', closeImage);
    toolbar.append(zoom, originalLink, close);
    const caption = document.createElement('p'); caption.className = 'readable-caption'; caption.textContent = '원본 너비로 표시합니다. 화면을 가로·세로로 밀어 글씨를 읽을 수 있습니다.';
    const scroll = document.createElement('div'); scroll.className = 'readable-scroll'; scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', '확대 이미지 가로·세로 이동');
    const img = document.createElement('img'); img.className = 'readable-original'; img.alt = link.dataset.originalAlt || thumbnail.alt; img.width = Number(link.dataset.originalWidth || thumbnail.width); img.height = Number(link.dataset.originalHeight || thumbnail.height); img.style.width = img.width + 'px'; img.style.setProperty('--original-width', img.width + 'px');
    // The full-resolution file is requested only after the visible image is clicked.
    img.src = link.href; scroll.append(img);
    zoom.addEventListener('click', () => {
      const fit = img.classList.toggle('fit'); zoom.textContent = fit ? '원본 너비로 확대' : '화면에 맞추기'; zoom.setAttribute('aria-pressed', String(fit));
      caption.textContent = fit ? '화면 너비에 맞춰 전체 구성을 표시합니다.' : '원본 너비로 표시합니다. 화면을 가로·세로로 밀어 글씨를 읽을 수 있습니다.';
    });
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeImage(); });
    dialog.append(toolbar, caption, scroll); document.body.append(dialog); dialog.showModal(); close.focus();
  });
})();
