(() => {
  const search = document.querySelector('#project-search');
  if (!search) return;
  const groups = [...document.querySelectorAll('.project-group')];
  const items = [...document.querySelectorAll('.project-item')];
  const count = document.querySelector('#project-count');
  const empty = document.querySelector('#project-empty');
  const normalise = value => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const labels = new Map(items.map(item => [item, normalise(item.textContent)]));
  function filter() {
    const words = normalise(search.value).trim().split(/\s+/).filter(Boolean);
    let visible = 0;
    for (const group of groups) {
      let groupCount = 0;
      for (const item of group.querySelectorAll('.project-item')) {
        item.hidden = !words.every(word => labels.get(item).includes(word));
        if (!item.hidden) { visible++; groupCount++; }
      }
      group.hidden = groupCount === 0;
      group.querySelector('.project-group__count').textContent = `${groupCount} ${groupCount === 1 ? 'page' : 'pages'}`;
    }
    count.textContent = `${visible} of ${items.length} project pages`;
    empty.hidden = visible !== 0;
  }
  search.addEventListener('input', filter);
  // Selecting a category always restores its full list, even after a search.
  for (const card of document.querySelectorAll('.category-card')) {
    card.addEventListener('click', () => { search.value = ''; filter(); });
  }
  document.querySelector('.project-search').hidden = false;
  filter();
})();
