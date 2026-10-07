(() => {
  'use strict';
  const form = document.querySelector('[data-teacher-search]');
  if (!form) return;
  const search = form.querySelector('[name="q"]');
  const region = form.querySelector('[name="region"]');
  const focus = form.querySelector('[name="focus"]');
  const cards = [...document.querySelectorAll('[data-teacher-branch]')];
  const result = document.querySelector('[data-teacher-result]');
  const empty = document.querySelector('[data-teacher-empty]');
  const normalize = value => value.normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g, ' ').trim();
  const params = new URLSearchParams(location.search);
  search.value = params.get('q') || '';
  for (const select of [region, focus]) {
    const value = params.get(select.name) || '';
    if ([...select.options].some(option => option.value === value)) select.value = value;
  }
  const refresh = (updateUrl = false) => {
    const terms = normalize(search.value).split(' ').filter(Boolean);
    let branches = 0;
    let profiles = 0;
    for (const card of cards) {
      card.hidden = (region.value && card.dataset.region !== region.value)
        || (focus.value && !JSON.parse(card.dataset.focus).includes(focus.value))
        || !terms.every(term => normalize(card.dataset.search).includes(term));
      if (!card.hidden) {
        branches += 1;
        profiles += Number(card.dataset.profileCount);
      }
    }
    result.textContent = `검색 결과 ${branches}개 지점 · 해당 지점의 등록 프로필 ${profiles.toLocaleString('ko-KR')}개`;
    empty.hidden = branches > 0;
    if (updateUrl) {
      const url = new URL(location.href);
      for (const input of [search, region, focus]) {
        if (input.value.trim()) url.searchParams.set(input.name, input.value.trim());
        else url.searchParams.delete(input.name);
      }
      history.replaceState(null, '', url);
    }
  };
  search.addEventListener('input', () => refresh(true));
  region.addEventListener('change', () => refresh(true));
  focus.addEventListener('change', () => refresh(true));
  form.addEventListener('submit', event => { event.preventDefault(); refresh(true); });
  form.addEventListener('reset', event => {
    event.preventDefault();
    search.value = region.value = focus.value = '';
    refresh(true);
    search.focus();
  });
  refresh();
})();
