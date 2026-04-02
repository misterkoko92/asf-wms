(() => {
  const sectionNav = document.getElementById('scan-dashboard-section-nav');
  if (!sectionNav) {
    return;
  }

  const links = Array.from(sectionNav.querySelectorAll('a[href^="#"]'));
  if (!links.length) {
    return;
  }

  const updateCurrentLink = () => {
    const activeHash = window.location.hash || links[0].getAttribute('href');
    links.forEach(link => {
      const isCurrent = link.getAttribute('href') === activeHash;
      if (isCurrent) {
        link.setAttribute('aria-current', 'location');
      } else {
        link.removeAttribute('aria-current');
      }
    });
  };

  window.addEventListener('hashchange', updateCurrentLink);
  updateCurrentLink();
})();
