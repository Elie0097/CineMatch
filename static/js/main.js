document.addEventListener('DOMContentLoaded', () => {

    // Auto-dismiss flash messages after 4 seconds
    document.querySelectorAll('.flash').forEach(el => {
        setTimeout(() => {
            el.style.transition = 'opacity 0.4s';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 400);
        }, 4000);
    });

    // Star rating hover effect
    const starRatings = document.querySelectorAll('.star-rating');
    starRatings.forEach(container => {
        const stars = Array.from(container.querySelectorAll('.star-btn'));
        const current = parseInt(container.dataset.current) || 0;

        stars.forEach((star, i) => {
            star.addEventListener('mouseenter', () => {
                stars.forEach((s, j) => {
                    s.style.color = j <= i ? 'var(--accent)' : 'var(--text-dim)';
                });
            });
            star.addEventListener('mouseleave', () => {
                stars.forEach((s, j) => {
                    s.style.color = '';
                    s.classList.toggle('active', j < current);
                });
            });
        });
    });

    // ── Browse-page search autocomplete ─────────────────────────────────────
    const searchInput    = document.getElementById('browse-search-input');
    const searchDropdown = document.getElementById('browse-search-dropdown');
    const searchForm     = document.getElementById('browse-search-form');

    if (!searchInput || !searchDropdown) return;

    const IMAGE_BASE = 'https://image.tmdb.org/t/p/w92';
    let debounceTimer = null;
    let currentIndex  = -1;
    let suggestions   = [];

    function openDropdown() {
        searchDropdown.classList.add('open');
        searchInput.setAttribute('aria-expanded', 'true');
    }

    function closeDropdown() {
        searchDropdown.classList.remove('open');
        searchDropdown.innerHTML = '';
        searchInput.setAttribute('aria-expanded', 'false');
        currentIndex = -1;
        suggestions  = [];
    }

    function setActiveItem(index) {
        const items = searchDropdown.querySelectorAll('.ac-item');
        items.forEach((el, i) => el.classList.toggle('ac-item-active', i === index));
        currentIndex = index;
    }

    function renderSuggestions(movies) {
        suggestions = movies;
        currentIndex = -1;
        searchDropdown.innerHTML = '';

        if (!movies.length) { closeDropdown(); return; }

        movies.forEach((movie, idx) => {
            const item = document.createElement('a');
            item.className = 'ac-item';
            item.href = `/movies/${movie.id}`;
            item.setAttribute('role', 'option');

            const thumb = document.createElement('div');
            thumb.className = 'ac-thumb';
            if (movie.poster_path) {
                const img = document.createElement('img');
                img.src = IMAGE_BASE + movie.poster_path;
                img.alt = movie.title;
                img.loading = 'lazy';
                thumb.appendChild(img);
            } else {
                thumb.textContent = '▶';
                thumb.classList.add('ac-thumb-placeholder');
            }

            const text = document.createElement('div');
            text.className = 'ac-text';
            const title = document.createElement('span');
            title.className = 'ac-title';
            title.textContent = movie.title;
            text.appendChild(title);
            if (movie.year) {
                const year = document.createElement('span');
                year.className = 'ac-year';
                year.textContent = movie.year;
                text.appendChild(year);
            }

            item.appendChild(thumb);
            item.appendChild(text);

            item.addEventListener('mouseenter', () => setActiveItem(idx));
            item.addEventListener('mouseleave', () => setActiveItem(-1));
            item.addEventListener('click', e => {
                e.preventDefault();
                closeDropdown();
                window.location.href = item.href;
            });

            searchDropdown.appendChild(item);
        });

        openDropdown();
    }

    async function fetchSuggestions(query) {
        try {
            const res = await fetch(`/api/search-suggestions?q=${encodeURIComponent(query)}`);
            if (!res.ok) return;
            renderSuggestions(await res.json());
        } catch (_) {
            closeDropdown();
        }
    }

    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const val = searchInput.value.trim();
        if (val.length < 2) { closeDropdown(); return; }
        debounceTimer = setTimeout(() => fetchSuggestions(val), 200);
    });

    searchInput.addEventListener('keydown', e => {
        const items = searchDropdown.querySelectorAll('.ac-item');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActiveItem(Math.min(currentIndex + 1, items.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActiveItem(Math.max(currentIndex - 1, -1));
        } else if (e.key === 'Enter' && currentIndex >= 0) {
            e.preventDefault();
            closeDropdown();
            window.location.href = items[currentIndex].getAttribute('href');
        } else if (e.key === 'Escape') {
            closeDropdown();
        }
    });

    document.addEventListener('click', e => {
        if (!searchForm.contains(e.target)) closeDropdown();
    });

    searchForm.addEventListener('submit', () => closeDropdown());
});
