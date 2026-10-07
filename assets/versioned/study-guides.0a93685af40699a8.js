(() => {
  'use strict';
  const root = document.querySelector('[data-guide-library]');
  if (root) {
    const search = root.querySelector('#guide-search');
    const stage = root.querySelector('#guide-stage');
    const buttons = [...root.querySelectorAll('[data-guide-category]')];
    const cards = [...root.querySelectorAll('[data-guide-card]')];
    const groups = [...root.querySelectorAll('[data-guide-group]')];
    const count = root.querySelector('#guide-count');
    const empty = root.querySelector('#guide-empty');
    const normalize = value => value.normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g, ' ').trim();
    let category = '전체';
    const filter = () => {
      const terms = normalize(search.value).split(' ').filter(Boolean);
      let total = 0;
      cards.forEach(card => {
        const haystack = normalize(card.dataset.guideSearch);
        const visible = (category === '전체' || card.dataset.category === category) && (!stage.value || card.dataset.stages.split(',').includes(stage.value)) && terms.every(term => haystack.includes(term));
        card.hidden = !visible;
        if (visible) total += 1;
      });
      groups.forEach(group => {
        const visible = [...group.querySelectorAll('[data-guide-card]')].filter(card => !card.hidden).length;
        group.hidden = visible === 0;
        group.querySelector('[data-group-count]').textContent = `${visible}편`;
      });
      count.textContent = `${total}편`;
      empty.hidden = total !== 0;
    };
    buttons.forEach(button => button.addEventListener('click', () => {
      category = button.dataset.guideCategory;
      buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      filter();
    }));
    search.addEventListener('input', filter);
    stage.addEventListener('change', filter);
    root.querySelectorAll('[data-guide-reset]').forEach(button => button.addEventListener('click', () => {
      search.value = '';
      stage.value = '';
      category = '전체';
      buttons.forEach(item => item.setAttribute('aria-pressed', String(item.dataset.guideCategory === '전체')));
      filter();
      search.focus();
    }));
    root.querySelector('[data-guide-controls]').hidden = false;
    filter();
  }
  document.querySelectorAll('[data-guide-print]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => window.print());
  });
  const revealAnchor = () => {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch { return; }
    const target = id && document.getElementById(id);
    if (!target) return;
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
  };
  window.addEventListener('hashchange', revealAnchor);
  revealAnchor();
})();
