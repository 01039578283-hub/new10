(() => {
  'use strict';
  const form = document.querySelector('[data-curriculum-search]');
  if (!form) return;
  const cards = [...document.querySelectorAll('[data-curriculum-card]')];
  const keys = ['stage', 'grade', 'subject', 'q'];
  const result = document.querySelector('[data-curriculum-result]');
  const empty = document.querySelector('[data-curriculum-empty]');
  const normalize = value => value.normalize('NFKC').toLocaleLowerCase('ko-KR').replace(/\s+/g, '');
  const initial = new URL(location.href).searchParams;
  keys.forEach(key => {
    const control = form.elements.namedItem(key);
    const value = initial.get(key) || '';
    if (control instanceof HTMLSelectElement && ![...control.options].some(o => o.value === value)) return;
    control.value = value;
  });
  function update(writeUrl) {
    const stage = form.elements.namedItem('stage').value;
    const grade = form.elements.namedItem('grade');
    const highestGrade = stage === '중등' || stage === '고등' ? 3 : 6;
    [...grade.options].forEach(option => { option.disabled = Number(option.value) > highestGrade; });
    if (Number(grade.value) > highestGrade) grade.value = '';
    const selected = Object.fromEntries(keys.map(key => [key, form.elements.namedItem(key).value.trim()]));
    const query = normalize(selected.q);
    let count = 0;
    cards.forEach(card => {
      const show = (!selected.stage || card.dataset.stage === selected.stage)
        && (!selected.grade || card.dataset.grade === selected.grade)
        && (!selected.subject || card.dataset.subject === selected.subject)
        && (!query || normalize(card.dataset.search).includes(query));
      card.hidden = !show;
      if (show) count++;
    });
    result.textContent = `학년·과목별 안내 ${count}개`;
    empty.hidden = count !== 0;
    if (writeUrl) {
      const url = new URL(location.href);
      keys.forEach(key => selected[key] ? url.searchParams.set(key, selected[key]) : url.searchParams.delete(key));
      history.replaceState(null, '', url);
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); update(true); });
  form.addEventListener('change', () => update(true));
  form.querySelector('input').addEventListener('input', () => update(true));
  document.querySelector('[data-curriculum-reset]').addEventListener('click', () => { form.reset(); update(true); });
  update(false);
})();
