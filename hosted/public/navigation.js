const destinations = [...document.querySelectorAll('.shell-nav a')];
function markDestination() {
  const location = window.location.hash || '#snapshot';
  for (const link of destinations) {
    if (link.hash === location) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  }
}
window.addEventListener('hashchange', markDestination);
document.querySelectorAll('.portfolio-tools a').forEach(link => link.addEventListener('click', () => {
  link.closest('details').open = false;
}));
markDestination();
