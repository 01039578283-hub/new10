(() => {
  'use strict';
  const form = document.querySelector('[data-branch-search]');
  if (!form) return;
  const input = form.querySelector('input[type="search"]');
  const stages = [...form.querySelectorAll('input[name="stage"]')];
  const cards = [...document.querySelectorAll('[data-branch-card]')];
  const counter = document.querySelector('[data-result-count]');
  const empty = document.querySelector('[data-empty-results]');
  const normal = value => value.normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g, ' ').trim();
  const refresh = () => {
    const terms = normal(input.value).split(' ').filter(Boolean);
    const selectedStage = stages.find(radio => radio.checked)?.value || '';
    let count = 0;
    for (const card of cards) {
      const stageMatches = !selectedStage || (card.dataset.stages || '').split(' ').includes(selectedStage);
      card.hidden = !stageMatches || !terms.every(term => normal(card.dataset.search).includes(term));
      if (!card.hidden) count += 1;
    }
    counter.textContent = terms.length || selectedStage ? `검색 결과 ${count}개 지점` : `전체 ${cards.length}개 지점`;
    empty.hidden = count > 0;
  };
  input.addEventListener('input', refresh);
  stages.forEach(radio => radio.addEventListener('change', refresh));
  form.addEventListener('submit', event => { event.preventDefault(); refresh(); });
  form.addEventListener('reset', () => {
    input.value = '';
    stages.forEach(radio => { radio.checked = radio.value === ''; });
    refresh();
    input.focus();
  });
  refresh();
})();
