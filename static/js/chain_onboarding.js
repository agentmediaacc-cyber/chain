(() => {
  const form = document.getElementById("chain-onboarding-form");
  if (!form) return;

  const steps = Array.from(form.querySelectorAll(".onboard-step"));
  const prevBtn = document.getElementById("chain-onboard-prev");
  const nextBtn = document.getElementById("chain-onboard-next");
  const submitBtn = document.getElementById("chain-onboard-submit");
  const progressBar = document.getElementById("chain-onboard-progress-bar");
  const progressText = document.getElementById("chain-onboard-progress-text");
  const dobInput = document.getElementById("date_of_birth");
  const ageInput = document.getElementById("age");
  const agePreview = document.getElementById("age_preview");
  const zodiacInput = document.getElementById("zodiac_sign");
  const zodiacPreview = document.getElementById("zodiac_preview");
  const countrySelect = document.getElementById("country_origin");
  const regionSelect = document.getElementById("region");

  let stepIndex = 0;

  const zodiacFor = (month, day) => {
    const signs = [
      ["Capricorn", 1, 19], ["Aquarius", 2, 18], ["Pisces", 3, 20], ["Aries", 4, 19],
      ["Taurus", 5, 20], ["Gemini", 6, 20], ["Cancer", 7, 22], ["Leo", 8, 22],
      ["Virgo", 9, 22], ["Libra", 10, 22], ["Scorpio", 11, 21], ["Sagittarius", 12, 21], ["Capricorn", 12, 31],
    ];
    return signs.find((item) => month < item[1] || (month === item[1] && day <= item[2]))[0];
  };

  const updateAgeAndZodiac = () => {
    if (!dobInput?.value) return;
    const dob = new Date(dobInput.value);
    if (Number.isNaN(dob.getTime())) return;
    const today = new Date();
    let age = today.getFullYear() - dob.getFullYear();
    const notYetBirthday = today.getMonth() < dob.getMonth() || (today.getMonth() === dob.getMonth() && today.getDate() < dob.getDate());
    if (notYetBirthday) age -= 1;
    const zodiac = zodiacFor(dob.getMonth() + 1, dob.getDate());
    if (ageInput) ageInput.value = age;
    if (agePreview) agePreview.value = age;
    if (zodiacInput) zodiacInput.value = zodiac;
    if (zodiacPreview) zodiacPreview.value = zodiac;
  };

  const renderCountries = () => {
    if (!countrySelect || !window.CHAIN_LOCATIONS) return;
    const selected = countrySelect.dataset.selected || countrySelect.value || "Namibia";
    const options = ['<option value="">Select country</option>']
      .concat(window.CHAIN_LOCATIONS.map((item) => `<option value="${item.country}" ${item.country === selected ? "selected" : ""}>${item.country}</option>`));
    countrySelect.innerHTML = options.join("");
  };

  const renderRegions = () => {
    if (!countrySelect || !regionSelect || !window.CHAIN_LOCATIONS) return;
    const selectedCountry = countrySelect.value || countrySelect.dataset.selected || "Namibia";
    const selectedRegion = regionSelect.dataset.selected || regionSelect.value || "";
    const record = window.CHAIN_LOCATIONS.find((item) => item.country === selectedCountry);
    const regions = record?.regions || [];
    const base = ['<option value="">Select region/state</option>'];
    if (!regions.length) {
      base.push(`<option value="${selectedRegion}" selected>${selectedRegion || "Custom region"}</option>`);
      regionSelect.innerHTML = base.join("");
      regionSelect.removeAttribute("disabled");
      return;
    }
    regionSelect.innerHTML = base.concat(regions.map((region) => `<option value="${region}" ${region === selectedRegion ? "selected" : ""}>${region}</option>`)).join("");
  };

  const syncChipGroups = () => {
    form.querySelectorAll(".choice-card--single[data-target]").forEach((button) => {
      const input = document.getElementById(button.dataset.target);
      if (!input) return;
      if (input.value === button.dataset.singleValue) button.classList.add("is-selected");
      button.addEventListener("click", () => {
        form.querySelectorAll(`.choice-card--single[data-target="${button.dataset.target}"]`).forEach((node) => node.classList.remove("is-selected"));
        button.classList.add("is-selected");
        input.value = button.dataset.singleValue;
      });
    });

    form.querySelectorAll("[data-target]").forEach((group) => {
      if (group.classList.contains("choice-card--single")) return;
      const targetName = group.dataset.target;
      const input = document.getElementById(targetName);
      if (!input) return;
      const current = new Set(String(input.value || "").split(",").map((item) => item.trim()).filter(Boolean));
      group.querySelectorAll("[data-value]").forEach((button) => {
        if (current.has(button.dataset.value)) button.classList.add("is-selected");
        button.addEventListener("click", () => {
          const multi = group.dataset.multi !== "false";
          if (!multi) {
            group.querySelectorAll("[data-value]").forEach((node) => node.classList.remove("is-selected"));
            button.classList.add("is-selected");
            input.value = button.dataset.value;
            return;
          }
          button.classList.toggle("is-selected");
          const values = Array.from(group.querySelectorAll(".is-selected")).map((node) => node.dataset.value);
          input.value = values.join(", ");
        });
      });
    });
  };

  const updateStep = () => {
    steps.forEach((step, index) => step.classList.toggle("is-active", index === stepIndex));
    const current = stepIndex + 1;
    const total = steps.length;
    progressText.textContent = `Step ${current} of ${total}`;
    progressBar.style.width = `${(current / total) * 100}%`;
    prevBtn.style.visibility = stepIndex === 0 ? "hidden" : "visible";
    nextBtn.style.display = stepIndex === total - 1 ? "none" : "inline-flex";
    submitBtn.style.display = stepIndex === total - 1 ? "inline-flex" : "none";
  };

  prevBtn?.addEventListener("click", () => {
    stepIndex = Math.max(0, stepIndex - 1);
    updateStep();
  });

  nextBtn?.addEventListener("click", () => {
    stepIndex = Math.min(steps.length - 1, stepIndex + 1);
    updateStep();
  });

  dobInput?.addEventListener("change", updateAgeAndZodiac);
  countrySelect?.addEventListener("change", renderRegions);

  renderCountries();
  renderRegions();
  syncChipGroups();
  updateAgeAndZodiac();
  updateStep();

  const cameraAvatar = form.querySelector('input[name="camera_avatar"]');
  cameraAvatar?.addEventListener("change", () => {
    const avatarMode = document.getElementById("avatar_mode");
    if (cameraAvatar.files?.length && avatarMode) avatarMode.value = "camera";
  });
})();
