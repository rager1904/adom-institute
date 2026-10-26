(() => {
  // Keep links from older school sections useful without a separate redirect.
  const search = new URLSearchParams(window.location.search);
  const legacyCategory = window.location.hash.slice(1);
  if (!search.has('category') && ['ai', 'finance', 'accounting', 'ict'].includes(legacyCategory)) {
    search.set('category', legacyCategory);
    window.location.replace(`${window.location.pathname}?${search.toString()}`);
  } else if (window.location.hash === '#tuition') {
    window.location.replace('/tuition/');
  }

  const tabs = [...document.querySelectorAll('.detail-tabs a')];
  if (tabs.length && 'IntersectionObserver' in window) {
    const markActive = (id) => tabs.forEach((tab) => {
      const active = tab.hash === `#${id}`;
      tab.classList.toggle('active', active);
      if (active) tab.setAttribute('aria-current', 'location');
      else tab.removeAttribute('aria-current');
    });
    tabs.forEach((tab) => tab.addEventListener('click', () => markActive(tab.hash.slice(1))));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.find((entry) => entry.isIntersecting);
      if (visible) markActive(visible.target.id);
    }, { rootMargin: '-15% 0px -60% 0px', threshold: 0 });
    document.querySelectorAll('.detail-section').forEach((section) => observer.observe(section));
  }
})();
