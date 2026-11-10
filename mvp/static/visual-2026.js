(() => {
  const video = document.querySelector('.hero-motion');
  if (!video) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  function updateMotion() {
    if (reducedMotion.matches || document.hidden) video.pause();
    else video.play().catch(() => {});
  }
  reducedMotion.addEventListener('change', updateMotion);
  document.addEventListener('visibilitychange', updateMotion);
  updateMotion();
})();
