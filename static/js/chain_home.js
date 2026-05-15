(() => {
  const input = document.getElementById("chain-search-input");
  const dropdown = document.getElementById("chain-search-dropdown");
  const preloadNode = document.getElementById("chain-home-search-data");

  if (!input || !dropdown) {
    return;
  }

  let preload = {};
  try {
    preload = preloadNode ? JSON.parse(preloadNode.textContent || "{}") : {};
  } catch (error) {
    preload = {};
  }

  const fallbackGroups = () => ({
    profiles: Array.isArray(preload.profiles) ? preload.profiles : [],
    live_rooms: Array.isArray(preload.live_rooms) ? preload.live_rooms : [],
    posts: Array.isArray(preload.posts) ? preload.posts : [],
    categories: Array.isArray(preload.categories) ? preload.categories : [],
  });

  const escapeHtml = (value) =>
    String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const queryMatches = (value, query) => String(value || "").toLowerCase().includes(query);

  const filterFallback = (query) => {
    const groups = fallbackGroups();
    return {
      profiles: groups.profiles.filter((item) =>
        [item.display_name, item.username, item.location].some((value) => queryMatches(value, query))
      ).slice(0, 4),
      live_rooms: groups.live_rooms.filter((item) =>
        [item.title, item.creator_name, item.category].some((value) => queryMatches(value, query))
      ).slice(0, 4),
      posts: groups.posts.filter((item) =>
        [item.caption, item.display_name, item.category].some((value) => queryMatches(value, query))
      ).slice(0, 4),
      categories: groups.categories.filter((item) =>
        queryMatches(item.name, query)
      ).slice(0, 4),
    };
  };

  const renderSection = (label, items, renderer) => {
    if (!items.length) {
      return "";
    }

    return `
      <div class="search-dropdown__section">
        <span class="search-dropdown__label">${escapeHtml(label)}</span>
        ${items.map(renderer).join("")}
      </div>
    `;
  };

  const renderResults = (data, query) => {
    const html = [
      renderSection("Creators", data.profiles || [], (item) => `
        <a class="search-dropdown__item" href="${escapeHtml(item.profile_url || "/discover/")}">
          <span>${escapeHtml(item.display_name || item.username || "Creator")}</span>
          <span class="search-dropdown__meta">${escapeHtml(item.location || item.username || "")}</span>
        </a>
      `),
      renderSection("Live Rooms", data.live_rooms || [], (item) => `
        <a class="search-dropdown__item" href="${escapeHtml(item.watch_url || "/live/")}">
          <span>${escapeHtml(item.title || item.creator_name || "Live room")}</span>
          <span class="search-dropdown__meta">${escapeHtml(item.category || "Live")}</span>
        </a>
      `),
      renderSection("Posts", data.posts || [], (item) => `
        <a class="search-dropdown__item" href="${escapeHtml(item.profile_url || "/discover/")}">
          <span>${escapeHtml(item.display_name || "Creator")}</span>
          <span class="search-dropdown__meta">${escapeHtml(item.category || item.caption || "Post")}</span>
        </a>
      `),
      renderSection("Categories", data.categories || [], (item) => `
        <a class="search-dropdown__item" href="${escapeHtml(item.href || `/search?q=${encodeURIComponent(item.name || "")}`)}">
          <span>${escapeHtml(item.name || "Category")}</span>
          <span class="search-dropdown__meta">Explore</span>
        </a>
      `),
    ].join("");

    if (!html.trim()) {
      dropdown.innerHTML = `
        <div class="search-dropdown__section">
          <span class="search-dropdown__label">Search</span>
          <div class="search-dropdown__item">
            <span>No instant matches for "${escapeHtml(query)}"</span>
            <span class="search-dropdown__meta">Press enter</span>
          </div>
        </div>
      `;
    } else {
      dropdown.innerHTML = html;
    }

    dropdown.hidden = false;
  };

  const fetchResults = async (rawQuery) => {
    const query = rawQuery.trim().toLowerCase();
    if (!query) {
      dropdown.hidden = true;
      dropdown.innerHTML = "";
      return;
    }

    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(rawQuery)}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`search ${response.status}`);
      }
      const data = await response.json();
      renderResults(
        {
          profiles: data.profiles || [],
          live_rooms: data.live_rooms || [],
          posts: data.posts || [],
          categories: (fallbackGroups().categories || []).slice(0, 4),
        },
        rawQuery
      );
    } catch (error) {
      renderResults(filterFallback(query), rawQuery);
    }
  };

  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = window.setTimeout(() => {
      fetchResults(input.value);
    }, 180);
  });

  input.addEventListener("focus", () => {
    if (input.value.trim()) {
      fetchResults(input.value);
    }
  });

  document.addEventListener("click", (event) => {
    const withinSearch = event.target.closest("#chain-search-form");
    if (!withinSearch) {
      dropdown.hidden = true;
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      dropdown.hidden = true;
    }
  });
})();
