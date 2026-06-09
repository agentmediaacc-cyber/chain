document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  body.classList.add("has-premium-profile");

  document.querySelectorAll("[data-file-trigger]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.fileTrigger);
      if (input) input.click();
    });
  });

  document.querySelectorAll("[data-auto-submit]").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.files && input.files.length && input.form) input.form.submit();
    });
  });

  const activateTab = (tabId, shouldScroll = false) => {
    if (!tabId || !document.getElementById(`${tabId}-content`)) return;
    document.querySelectorAll("[data-tab-target]").forEach((tab) => {
      const active = tab.dataset.tabTarget === tabId;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll(".tab-content").forEach((panel) => {
      panel.hidden = panel.id !== `${tabId}-content`;
    });
    window.history.replaceState(null, "", `#${tabId}`);
    if (shouldScroll) {
      document.querySelector("[data-profile-tabs]")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  document.querySelectorAll("[data-tab-target]").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tabTarget, true));
  });
  activateTab(window.location.hash.replace("#", "") || "posts", false);

  const miniProfile = document.querySelector("[data-mini-profile]");
  if (miniProfile) {
    const updateMiniHeader = () => miniProfile.classList.toggle("is-visible", window.scrollY > 420);
    updateMiniHeader();
    window.addEventListener("scroll", updateMiniHeader, { passive: true });
  }

  document.querySelectorAll("[data-copy-profile]").forEach((button) => {
    button.addEventListener("click", async () => {
      const url = `${window.location.origin}${button.dataset.copyProfile || window.location.pathname}`;
      try {
        await navigator.clipboard.writeText(url);
        const original = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i>Copied';
        window.setTimeout(() => {
          button.innerHTML = original;
        }, 1400);
      } catch (error) {
        window.prompt("Copy profile link", url);
      }
    });
  });

  document.querySelectorAll("[data-share-profile]").forEach((button) => {
    button.addEventListener("click", async () => {
      const url = window.location.href;
      if (navigator.share) {
        try {
          await navigator.share({ title: document.title, url });
          return;
        } catch (error) {
          if (error.name === "AbortError") return;
        }
      }
      try {
        await navigator.clipboard.writeText(url);
      } catch (error) {
        window.prompt("Share profile link", url);
      }
    });
  });

  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      [...body.classList].forEach((className) => {
        if (className.startsWith("profile-theme-")) body.classList.remove(className);
      });
      body.classList.add(`profile-theme-${button.dataset.themeChoice}`);
      document.querySelector(".premium-profile-shell")?.setAttribute("data-theme", button.dataset.themeChoice);
      localStorage.setItem("chain_profile_theme_preview", button.dataset.themeChoice);
    });
  });

  const savedTheme = localStorage.getItem("chain_profile_theme_preview");
  if (savedTheme && document.querySelector(".premium-profile-shell")) {
    body.classList.add(`profile-theme-${savedTheme}`);
    document.querySelector(".premium-profile-shell")?.setAttribute("data-theme", savedTheme);
  }

  const animateNumber = (element) => {
    const target = Number(element.dataset.countUp || "0");
    if (!Number.isFinite(target) || target <= 0) {
      element.textContent = "0";
      return;
    }
    const duration = 900;
    const start = performance.now();
    const formatter = new Intl.NumberFormat();
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = formatter.format(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  const countObserver = "IntersectionObserver" in window
    ? new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          animateNumber(entry.target);
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.4 })
    : null;

  document.querySelectorAll("[data-count-up]").forEach((counter) => {
    if (countObserver) countObserver.observe(counter);
    else animateNumber(counter);
  });

  const qrPopover = document.querySelector("[data-profile-qr-popover]");
  const qrCode = document.querySelector("[data-profile-qr-code]");
  const buildQr = (value) => {
    if (!qrCode) return;
    qrCode.innerHTML = "";
    const seed = [...String(value || window.location.href)].reduce((sum, char) => sum + char.charCodeAt(0), 0);
    for (let index = 0; index < 169; index += 1) {
      const cell = document.createElement("span");
      const row = Math.floor(index / 13);
      const col = index % 13;
      const finder =
        (row < 4 && col < 4) ||
        (row < 4 && col > 8) ||
        (row > 8 && col < 4);
      const dark = finder || ((index * 17 + seed + row * col) % 5 < 2);
      cell.classList.toggle("is-dark", dark);
      qrCode.appendChild(cell);
    }
  };

  document.querySelectorAll("[data-profile-qr]").forEach((button) => {
    button.addEventListener("click", () => {
      const path = button.dataset.profileUrl || window.location.pathname;
      buildQr(`${window.location.origin}${path}`);
      if (qrPopover) qrPopover.hidden = false;
    });
  });

  document.querySelectorAll("[data-profile-qr-close]").forEach((button) => {
    button.addEventListener("click", () => {
      if (qrPopover) qrPopover.hidden = true;
    });
  });

  qrPopover?.addEventListener("click", (event) => {
    if (event.target === qrPopover) qrPopover.hidden = true;
  });

  document.querySelectorAll("[data-profile-follow]").forEach((button) => {
    button.addEventListener("click", async () => {
      const profileId = button.dataset.profileId;
      if (!profileId || button.disabled) return;
      button.disabled = true;
      try {
        const response = await fetch(`/profile/follow/${profileId}`, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("Follow request failed");
        const following = button.dataset.following !== "true";
        document.querySelectorAll(`[data-profile-follow][data-profile-id="${profileId}"]`).forEach((followButton) => {
          followButton.dataset.following = following ? "true" : "false";
          followButton.innerHTML = following
            ? '<i class="fas fa-user-check"></i><span>Following</span>'
            : '<i class="fas fa-user-plus"></i><span>Follow</span>';
        });
      } catch (error) {
        console.error("Follow action failed", error);
      } finally {
        button.disabled = false;
      }
    });
  });
});
