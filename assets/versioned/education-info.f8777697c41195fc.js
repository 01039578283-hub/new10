(() => {
  'use strict';
  const form = document.querySelector('[data-education-search]');
  if (form) {
    const cards = [...document.querySelectorAll('[data-education-card]')];
    const q = form.elements.q, category = form.elements.category;
    const stage = form.elements.stage, kind = form.elements.kind;
    const result = document.querySelector('[data-education-result]');
    const empty = document.querySelector('[data-education-empty]');
    const params = new URLSearchParams(location.search);
    q.value = params.get('q') || '';
    for (const field of [category, stage, kind]) {
      const value = params.get(field.name) || '';
      if ([...field.options].some(option => option.value === value)) field.value = value;
    }
    const normalize = text => text.normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g, ' ').trim();
    const apply = (updateUrl = true) => {
      const words = normalize(q.value).split(' ').filter(Boolean);
      let visible = 0, newCount = 0, guideCount = 0;
      for (const card of cards) {
        const match = words.every(word => normalize(card.dataset.educationSearch).includes(word))
          && (!category.value || card.dataset.category === category.value)
          && (!stage.value || card.dataset.stages.split(',').includes(stage.value))
          && (!kind.value || card.dataset.kind === kind.value);
        card.hidden = !match;
        if (match) { visible++; card.dataset.kind === 'education' ? newCount++ : guideCount++; }
      }
      for (const section of document.querySelectorAll('[data-education-group]')) {
        section.hidden = ![...section.querySelectorAll('[data-education-card]')].some(card => !card.hidden);
      }
      result.textContent = `검색 결과 ${visible}편 · 교육정보 ${newCount}편 · 학습가이드 ${guideCount}편`;
      empty.hidden = visible !== 0;
      if (updateUrl) {
        const url = new URL(location.href);
        for (const field of [q, category, stage, kind]) {
          const value = field.value.trim();
          value ? url.searchParams.set(field.name, value) : url.searchParams.delete(field.name);
        }
        history.replaceState(null, '', url);
      }
    };
    form.addEventListener('submit', event => { event.preventDefault(); apply(); });
    [category, stage, kind].forEach(field => field.addEventListener('change', () => apply()));
    document.querySelector('[data-education-reset]').addEventListener('click', () => {
      q.value = ''; category.value = ''; stage.value = ''; kind.value = ''; apply(); q.focus();
    });
    apply(false);
  }
  const region = document.querySelector('[data-location-region]');
  const town = document.querySelector('[data-location-town]');
  const school = document.querySelector('[data-location-school]');
  if (!region || !town || !school) return;
  const status = document.querySelector('[data-location-status]');
  const actions = document.querySelector('[data-location-actions]');
  const controls = document.querySelector('[data-location-controls]');
  const option = (value, label) => { const node = document.createElement('option'); node.value = value; node.textContent = label; return node; };
  const button = (href, label) => { const link = document.createElement('a'); link.href = href; link.textContent = label; return link; };
  fetch('/assets/education-info/locations.json').then(response => {
    if (!response.ok) throw new Error('지역 자료를 불러오지 못했습니다.');
    return response.json();
  }).then(data => {
    controls.hidden = false;
    for (const item of data.regions) region.append(option(item.name, item.name));
    const update = () => {
      actions.replaceChildren();
      const selectedRegion = data.regions.find(item => item.name === region.value);
      if (!selectedRegion) { status.textContent = '지역을 고르면 해당 동네와 지점 안내를 확인할 수 있습니다.'; return; }
      const entry = data.towns.find(item => item.id === town.value && item.region === region.value);
      if (!entry) {
        status.textContent = `${selectedRegion.name}의 동네를 고르거나 지역 지점 목록을 확인하세요.`;
        actions.append(button(selectedRegion.href, `${selectedRegion.name} 지점 목록 보기`)); return;
      }
      status.textContent = `${entry.name}의 ${school.value} 학습 안내와 ${entry.branch} 정보를 확인하세요.`;
      const destination = entry.paths[school.value];
      if (destination) actions.append(button(destination, `${entry.name} ${school.value} 학습 안내 보기`));
      actions.append(button(entry.branchHref, `${entry.branch} 지점 정보 보기`));
      if (entry.teacherHref) actions.append(button(entry.teacherHref, `${entry.branch} 선생님 소개 보기`));
    };
    region.addEventListener('change', () => {
      town.replaceChildren(option('', '동네를 선택하세요'));
      for (const entry of data.towns.filter(item => item.region === region.value)) town.append(option(entry.id, `${entry.name} · ${entry.branch}`));
      town.disabled = !region.value; update();
    });
    town.addEventListener('change', update); school.addEventListener('change', update); update();
  }).catch(() => {
    controls.hidden = true;
    status.textContent = '아래 지역 지점 목록에서 동네와 지점 정보를 확인해 주세요.';
  });
})();
