/**
 * FairPanel - Landing Page Interactivity
 * Focus trap, mobile menu drawer, video handling, and metric count-ups.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Menu Drawer
  const menuBtn = document.querySelector('.mobile-menu-btn');
  const overlay = document.querySelector('.mobile-overlay');
  const sheet = document.querySelector('.mobile-menu-sheet');

  if (menuBtn && overlay && sheet) {
    let previousActiveElement = null;

    function openMenu() {
      previousActiveElement = document.activeElement;
      menuBtn.classList.add('open');
      menuBtn.setAttribute('aria-expanded', 'true');
      overlay.classList.add('active');
      sheet.classList.add('active');
      document.body.style.overflow = 'hidden';

      const firstLink = sheet.querySelector('a, button');
      if (firstLink) firstLink.focus();
    }

    function closeMenu() {
      menuBtn.classList.remove('open');
      menuBtn.setAttribute('aria-expanded', 'false');
      overlay.classList.remove('active');
      sheet.classList.remove('active');
      document.body.style.overflow = '';

      if (previousActiveElement) {
        previousActiveElement.focus();
      }
    }

    menuBtn.addEventListener('click', () => {
      if (menuBtn.classList.contains('open')) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    overlay.addEventListener('click', closeMenu);

    sheet.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', closeMenu);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && menuBtn.classList.contains('open')) {
        closeMenu();
      }
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth > 720 && menuBtn.classList.contains('open')) {
        closeMenu();
      }
    });
  }

  // 2. Metrics Count-Up Animation
  const metricValues = document.querySelectorAll('.metric-value');
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function animateCount(el, target, duration, delay) {
    if (prefersReducedMotion || duration <= 0) {
      el.textContent = target;
      return;
    }

    setTimeout(() => {
      let start = 0;
      const startTime = performance.now();

      function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const current = Math.floor(easeOutCubic(progress) * target);
        el.textContent = current;

        if (progress < 1) {
          requestAnimationFrame(update);
        } else {
          el.textContent = target;
        }
      }

      requestAnimationFrame(update);
    }, delay);
  }

  if (metricValues.length > 0 && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          metricValues.forEach((el, i) => {
            const target = parseInt(el.getAttribute('data-target') || el.textContent, 10);
            if (!isNaN(target)) {
              const duration = 1500 + i * 80;
              const delay = 480 + i * 90;
              animateCount(el, target, duration, delay);
            }
          });
          obs.disconnect();
        }
      });
    }, { threshold: 0.25 });

    const footer = document.querySelector('.landing-footer');
    if (footer) observer.observe(footer);
  }

  // 3. Background Video Graceful Fallback
  const video = document.querySelector('.landing-video');
  if (video) {
    video.play().catch(() => {
      // Autoplay blocked by browser policy; quiet fallback to CSS/poster
      video.style.opacity = '0';
    });
  }
});
