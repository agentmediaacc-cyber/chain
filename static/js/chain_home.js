(() => {
  const drawer = document.getElementById("chain-home-drawer");
  const toggles = document.querySelectorAll("[data-drawer-toggle]");
  const closers = document.querySelectorAll("[data-drawer-close]");
  const backdrop = document.querySelector(".chain-home__drawer-backdrop");

  if (!drawer) {
    return;
  }

  const setDrawerState = (open) => {
    drawer.classList.toggle("is-open", open);
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    toggles.forEach((toggle) => toggle.setAttribute("aria-expanded", open ? "true" : "false"));
    if (backdrop) {
      backdrop.hidden = !open;
    }
    document.body.style.overflow = open ? "hidden" : "";
  };

  toggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      setDrawerState(!drawer.classList.contains("is-open"));
    });
  });

  closers.forEach((closer) => {
    closer.addEventListener("click", () => setDrawerState(false));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setDrawerState(false);
    }
  });
})();
