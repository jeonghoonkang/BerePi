// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize
    initTheme();
    initNav();
    initI18n();
    initSmoothScroll();
    initExpandableText();
    initDownloadCounters();
    initSaleDeadlines();
});

// ===== Expandable Text (Click to Expand/Collapse) =====
function initExpandableText() {
    const talkDescs = document.querySelectorAll('.talk-desc');

    talkDescs.forEach(desc => {
        desc.addEventListener('click', (e) => {
            e.stopPropagation();
            desc.classList.toggle('expanded');
        });
    });
}

// ===== E-book Download Counters =====
function initDownloadCounters() {
    const counterEls = document.querySelectorAll('[data-counter-key]');
    const downloadLinks = document.querySelectorAll('.js-download-track[data-counter-key]');

    if (!counterEls.length && !downloadLinks.length) return;

    const counterBaseUrl = 'https://countapi.mileshilliard.com/api/v1';
    const keys = [...new Set(Array.from(counterEls).map(el => el.dataset.counterKey).filter(Boolean))];

    keys.forEach(key => {
        setCounterState(key, 'loading');
        fetch(`${counterBaseUrl}/get/${encodeURIComponent(key)}`)
            .then(response => {
                if (response.status === 404) {
                    return { value: 0 };
                }
                if (!response.ok) {
                    throw new Error(`Counter request failed: ${response.status}`);
                }
                return response.json();
            })
            .then(data => setCounterValue(key, data.value || 0))
            .catch(() => setCounterState(key, 'unavailable'));
    });

    downloadLinks.forEach(link => {
        link.addEventListener('click', () => {
            const key = link.dataset.counterKey;
            if (!key) return;

            fetch(`${counterBaseUrl}/hit/${encodeURIComponent(key)}`, {
                method: 'GET',
                cache: 'no-store',
                keepalive: true
            })
                .then(response => response.ok ? response.json() : null)
                .then(data => {
                    if (data && data.value !== undefined) {
                        setCounterValue(key, data.value);
                    }
                })
                .catch(() => {
                    // Counting should never block the download action.
                });
        });
    });
}

function setCounterValue(key, value) {
    document.querySelectorAll(`[data-counter-key="${key}"]`).forEach(el => {
        const valueEl = el.querySelector('[data-count-value]');
        if (!valueEl) return;

        el.classList.remove('is-loading', 'is-unavailable');
        valueEl.textContent = Number(value).toLocaleString();
    });
}

function setCounterState(key, state) {
    document.querySelectorAll(`[data-counter-key="${key}"]`).forEach(el => {
        const valueEl = el.querySelector('[data-count-value]');
        if (!valueEl) return;

        el.classList.toggle('is-loading', state === 'loading');
        el.classList.toggle('is-unavailable', state === 'unavailable');
        valueEl.textContent = state === 'loading' ? '...' : getCounterUnavailableText();
    });
}

function getCounterUnavailableText() {
    return document.documentElement.lang === 'ko' ? '집계 준비 중' : 'Counting soon';
}

// ===== Limited E-book Sales =====
function initSaleDeadlines() {
    const saleLinks = document.querySelectorAll('[data-sale-deadline]');

    saleLinks.forEach(link => {
        const deadline = Date.parse(link.dataset.saleDeadline);
        if (Number.isNaN(deadline)) return;

        const closeSaleIfNeeded = () => {
            if (Date.now() < deadline || link.classList.contains('is-sale-closed')) return;

            link.classList.add('is-sale-closed');
            link.removeAttribute('href');
            link.removeAttribute('target');
            link.removeAttribute('rel');
            link.setAttribute('aria-disabled', 'true');
            link.setAttribute('tabindex', '-1');

            const cta = link.querySelector('.js-sale-cta');
            if (cta) {
                cta.dataset.i18n = 'arrow.closed';
                cta.textContent = document.documentElement.lang === 'ko' ? '판매 종료' : 'Sale ended';
            }

            const deadlineNote = link.querySelector('.ebook-sale-deadline');
            if (deadlineNote) {
                deadlineNote.dataset.i18n = 'arrow.closedNote';
                deadlineNote.textContent = document.documentElement.lang === 'ko'
                    ? '한정 판매 기간이 종료되었습니다.'
                    : 'This limited sale has ended.';
            }
        };

        closeSaleIfNeeded();

        const remainingTime = deadline - Date.now();
        if (remainingTime > 0) {
            window.setTimeout(closeSaleIfNeeded, Math.min(remainingTime, 2147483647));
        }
    });
}

// ===== Theme Toggle =====
function initTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const savedTheme = localStorage.getItem('theme');

    // Set initial theme
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    } else if (prefersDark) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }

    // Toggle theme on click
    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });
}

// ===== Mobile Navigation =====
function initNav() {
    const menuToggle = document.getElementById('menuToggle');
    const nav = document.getElementById('nav');
    const navLinks = nav.querySelectorAll('a');

    // Toggle mobile menu
    menuToggle.addEventListener('click', () => {
        nav.classList.toggle('active');
        menuToggle.classList.toggle('active');
    });

    // Close menu on link click
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            nav.classList.remove('active');
            menuToggle.classList.remove('active');
        });
    });

    // Header scroll effect
    let lastScroll = 0;
    const header = document.getElementById('header');

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        if (currentScroll > 100) {
            header.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.1)';
        } else {
            header.style.boxShadow = 'none';
        }

        lastScroll = currentScroll;
    });
}

// ===== Initialize i18n =====
function initI18n() {
    // Initialize translations
    if (window.i18n && window.i18n.init) {
        window.i18n.init();
    }

    // Language toggle button
    const langToggle = document.getElementById('langToggle');
    if (langToggle) {
        langToggle.addEventListener('click', () => {
            if (window.i18n && window.i18n.toggle) {
                window.i18n.toggle();
            }
        });
    }
}

// ===== Smooth Scroll =====
function initSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');

    links.forEach(link => {
        link.addEventListener('click', (e) => {
            const href = link.getAttribute('href');

            if (href === '#') return;

            e.preventDefault();
            const target = document.querySelector(href);

            if (target) {
                const headerHeight = document.getElementById('header').offsetHeight;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - headerHeight;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// ===== Intersection Observer for animations =====
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

// Observe sections after DOM load
document.addEventListener('DOMContentLoaded', () => {
    const sections = document.querySelectorAll('.section');
    sections.forEach(section => observer.observe(section));
});
