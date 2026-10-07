// ==========================================================
// Student Smart Planner - Global JS
// Handles: sidebar toggle (mobile) + light/dark theme persistence
// ==========================================================

document.addEventListener('DOMContentLoaded', function () {
    // ---- Reveal cards as they enter the viewport ----
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!motionPreference.matches && 'IntersectionObserver' in window) {
        const revealObserver = new IntersectionObserver(function (entries, observer) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        document.querySelectorAll(
            '.page-content .panel-card, .page-content .stat-card, ' +
            '.page-content .subject-card, .page-content .exam-card'
        ).forEach(function (element) {
            element.classList.add('scroll-reveal');
            revealObserver.observe(element);
        });
    }

    // ---- Animate progress bars from empty to their rendered values ----
    if (!motionPreference.matches) {
        document.querySelectorAll('.progress-rail span').forEach(function (bar) {
            const targetWidth = bar.style.width;
            bar.style.width = '0';
            requestAnimationFrame(function () {
                bar.style.width = targetWidth;
            });
        });
    }

    // ---- Stagger list and table rows on page load ----
    if (!motionPreference.matches) {
        document.querySelectorAll('.page-content .simple-list > li, .page-content tbody tr')
            .forEach(function (element, index) {
                element.classList.add('list-enter');
                element.style.animationDelay = Math.min(index * 40, 280) + 'ms';
            });
    }

    // ---- Sidebar toggle (mobile) ----
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function (event) {
            if (window.innerWidth <= 991) {
                if (!sidebar.contains(event.target) && !sidebarToggle.contains(event.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }

    // ---- Theme toggle (light / dark) ----
    const themeToggle = document.getElementById('themeToggle');
    const htmlEl = document.documentElement;

    const savedTheme = localStorage.getItem('planner-theme') || 'light';
    htmlEl.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            const currentTheme = htmlEl.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            htmlEl.setAttribute('data-theme', newTheme);
            localStorage.setItem('planner-theme', newTheme);
            updateThemeIcon(newTheme);
        });
    }

    function updateThemeIcon(theme) {
        if (!themeToggle) return;
        const icon = themeToggle.querySelector('i');
        if (!icon) return;
        icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    }

    // ---- Auto-dismiss alerts after 4 seconds ----
    document.querySelectorAll('.alert').forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 4000);
    });
});
