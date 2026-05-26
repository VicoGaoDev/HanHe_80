const payload = window.GPT_IMAGE2_PROMPT_SITE_DATA;

if (!payload) {
  throw new Error("Missing site data. Please generate site-data.js first.");
}

const { styleLibrary, casesData } = payload;
const allCases = [...casesData.cases].sort((left, right) => right.id - left.id);
const initialFilterState = readFilterStateFromUrl();

const state = {
  search: "",
  style: initialFilterState.style,
  category: initialFilterState.category,
  scene: initialFilterState.scene,
  featured: initialFilterState.featured,
  referenceImage: initialFilterState.referenceImage,
  sidebarCollapsed: readSidebarPreference(),
  mobileDrawerOpen: false,
  mobileSearchOpen: false,
  sections: {
    ...readSectionPreferences(),
    styles: true,
  },
};

const elements = {
  heroStats: document.querySelector("#hero-stats"),
  mainLayout: document.querySelector("#main-layout"),
  contentPanel: document.querySelector(".content-panel"),
  mobileFloatingActions: document.querySelector(".mobile-floating-actions"),
  searchInput: document.querySelector("#search-input"),
  resetFilters: document.querySelector("#reset-filters"),
  applyFilters: document.querySelector("#apply-filters"),
  controlPanel: document.querySelector(".control-panel"),
  sidebar: document.querySelector("#style-sidebar"),
  sidebarDrawerBackdrop: document.querySelector("#sidebar-drawer-backdrop"),
  toggleSidebar: document.querySelector("#toggle-sidebar"),
  floatingExpandButton: document.querySelector("#floating-expand-button"),
  mobileFilterButton: document.querySelector("#mobile-filter-button"),
  mobileSearchButton: document.querySelector("#mobile-search-button"),
  sectionToggles: document.querySelectorAll("[data-section-toggle]"),
  styleFilters: document.querySelector("#style-filters"),
  categoryFilters: document.querySelector("#category-filters"),
  sceneFilters: document.querySelector("#scene-filters"),
  styleSummary: document.querySelector("#style-summary"),
  resultsTitle: document.querySelector("#results-title"),
  resultsMeta: document.querySelector("#results-meta"),
  resultsGrid: document.querySelector("#results-grid"),
  modal: document.querySelector("#detail-modal"),
  closeModal: document.querySelector("#close-modal"),
  detailImage: document.querySelector("#detail-image"),
  imageLightbox: document.querySelector("#image-lightbox"),
  lightboxImage: document.querySelector("#lightbox-image"),
  closeLightbox: document.querySelector("#close-lightbox"),
  detailCategory: document.querySelector("#detail-category"),
  detailTitle: document.querySelector("#detail-title"),
  detailId: document.querySelector("#detail-id"),
  detailTags: document.querySelector("#detail-tags"),
  detailPrompt: document.querySelector("#detail-prompt"),
  copyPrompt: document.querySelector("#copy-prompt"),
  copyToast: document.querySelector("#copy-toast"),
};

let activeCase = null;

renderHeroStats();
renderFilters();
renderResults();
applySidebarState();
applySectionStates();
bindEvents();
syncFilterStateToUrl();

function bindEvents() {
  elements.applyFilters.addEventListener("click", () => {
    state.search = elements.searchInput.value.trim();
    renderResults();
  });

  elements.resetFilters.addEventListener("click", () => {
    state.search = "";
    state.style = "all";
    state.category = "all";
    state.scene = "all";
    state.featured = false;
    state.referenceImage = false;
    elements.searchInput.value = "";
    syncFilterStateToUrl();
    renderHeroStats();
    renderFilters();
    renderResults();
  });

  elements.resultsMeta.addEventListener("click", (event) => {
    const clearButton = event.target.closest("[data-clear-filter]");
    if (!clearButton) {
      return;
    }

    const filterKey = clearButton.dataset.clearFilter;
    if (!["style", "category", "scene", "featured", "referenceImage"].includes(filterKey)) {
      return;
    }

    state[filterKey] = ["featured", "referenceImage"].includes(filterKey) ? false : "all";
    syncFilterStateToUrl();
    renderHeroStats();
    renderFilters();
    renderResults();
  });

  elements.heroStats.addEventListener("click", (event) => {
    const sectionButton = event.target.closest("[data-stat-section]");
    if (sectionButton) {
      openSidebarSection(sectionButton.dataset.statSection);
      return;
    }

    const statButton = event.target.closest("[data-stat-filter]");
    if (!statButton || !["featured", "referenceImage"].includes(statButton.dataset.statFilter)) {
      return;
    }

    const filterKey = statButton.dataset.statFilter;
    state[filterKey] = !state[filterKey];
    syncFilterStateToUrl();
    renderHeroStats();
    renderResults();
  });

  elements.toggleSidebar.addEventListener("click", () => {
    if (isDrawerViewport()) {
      state.mobileDrawerOpen = false;
      applySidebarState();
      return;
    }

    state.sidebarCollapsed = !state.sidebarCollapsed;
    writeSidebarPreference(state.sidebarCollapsed);
    applySidebarState();
  });

  elements.floatingExpandButton.addEventListener("click", () => {
    if (isDrawerViewport()) {
      state.mobileDrawerOpen = true;
      state.mobileSearchOpen = false;
      applySidebarState();
      return;
    }

    state.sidebarCollapsed = false;
    writeSidebarPreference(state.sidebarCollapsed);
    applySidebarState();
  });

  elements.sidebarDrawerBackdrop.addEventListener("click", () => {
    state.mobileDrawerOpen = false;
    state.mobileSearchOpen = false;
    applySidebarState();
  });

  elements.mobileFilterButton.addEventListener("click", () => {
    if (!isDrawerViewport()) {
      return;
    }
    state.mobileDrawerOpen = !state.mobileDrawerOpen;
    state.mobileSearchOpen = false;
    applySidebarState();
  });

  elements.mobileSearchButton.addEventListener("click", () => {
    if (!isDrawerViewport()) {
      return;
    }
    state.mobileSearchOpen = !state.mobileSearchOpen;
    state.mobileDrawerOpen = false;
    applySidebarState();
  });

  elements.sectionToggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const sectionKey = toggle.dataset.sectionToggle;
      state.sections[sectionKey] = !state.sections[sectionKey];
      writeSectionPreferences(state.sections);
      applySectionStates();
    });
  });

  /* Capture phase: close mobile search without letting the click reach cards/links below */
  document.addEventListener(
    "click",
    (event) => {
      if (!isDrawerViewport() || !state.mobileSearchOpen) {
        return;
      }

      const t = event.target;
      if (!(t instanceof Element)) {
        return;
      }

      if (
        t.closest(".search-row") ||
        t.closest(".mobile-floating-actions") ||
        t.closest("#floating-expand-button")
      ) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      state.mobileSearchOpen = false;
      applySidebarState();
    },
    true
  );

  elements.resultsGrid.addEventListener("click", async (event) => {
    const copyButton = event.target.closest("[data-copy-case-id]");
    if (copyButton) {
      event.stopPropagation();
      const caseId = Number(copyButton.dataset.copyCaseId);
      const matchedCase = allCases.find((item) => item.id === caseId);
      if (matchedCase) {
        await copyPromptText(matchedCase.prompt);
      }
      return;
    }

    const card = event.target.closest("[data-case-id]");
    if (!card) {
      return;
    }

    const caseId = Number(card.dataset.caseId);
    const matchedCase = allCases.find((item) => item.id === caseId);

    if (matchedCase) {
      openModal(matchedCase);
    }
  });

  elements.closeModal.addEventListener("click", closeModal);
  elements.modal.addEventListener("click", (event) => {
    if (event.target.dataset.closeModal === "true") {
      closeModal();
    }
  });
  elements.detailImage.addEventListener("click", openImageLightbox);
  elements.closeLightbox.addEventListener("click", closeImageLightbox);
  elements.imageLightbox.addEventListener("click", (event) => {
    if (event.target.dataset.closeLightbox === "true") {
      closeImageLightbox();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.imageLightbox.classList.contains("open")) {
      closeImageLightbox();
      return;
    }

    if (event.key === "Escape" && elements.modal.classList.contains("open")) {
      closeModal();
      return;
    }

    if (event.key === "Escape" && (state.mobileDrawerOpen || state.mobileSearchOpen)) {
      state.mobileDrawerOpen = false;
      state.mobileSearchOpen = false;
      applySidebarState();
    }
  });

  window.addEventListener("resize", () => {
    if (!isDrawerViewport()) {
      state.mobileDrawerOpen = false;
      state.mobileSearchOpen = false;
    }
    applySidebarState();
  });

  window.addEventListener("popstate", () => {
    const nextFilterState = readFilterStateFromUrl();
    state.style = nextFilterState.style;
    state.category = nextFilterState.category;
    state.scene = nextFilterState.scene;
    state.featured = nextFilterState.featured;
    renderHeroStats();
    renderFilters();
    renderResults();
  });

  elements.copyPrompt.addEventListener("click", async () => {
    if (!activeCase) {
      return;
    }

    await copyPromptText(activeCase.prompt);
  });
}

function renderHeroStats() {
  const featuredCount = allCases.filter((item) => item.featured).length;
  const referenceImageCount = allCases.filter((item) => item.requiresReferenceImage).length;

  const stats = [
    {
      label: "个风格标签",
      value: styleLibrary.styles.length,
      key: "styles",
      action: "section",
    },
    {
      label: "个分类",
      value: styleLibrary.categories.length,
      key: "categories",
      action: "section",
    },
    {
      label: "个场景",
      value: styleLibrary.scenes.length,
      key: "scenes",
      action: "section",
    },
    {
      label: "条精选案例",
      value: featuredCount,
      key: "featured",
      action: "filter",
      active: state.featured,
    },
    {
      label: "条需参考图",
      value: referenceImageCount,
      key: "referenceImage",
      action: "filter",
      active: state.referenceImage,
    },
  ];

  elements.heroStats.innerHTML = stats
    .map(
      (stat) => `
        <${stat.action ? "button" : "article"}
          ${
            stat.action === "filter"
              ? `type="button" data-stat-filter="${escapeAttribute(stat.key)}"`
              : stat.action === "section"
                ? `type="button" data-stat-section="${escapeAttribute(stat.key)}"`
                : ""
          }
          class="stat-card ${stat.key ? "stat-card-button" : ""} ${stat.active ? "active" : ""}"
        >
          <span class="stat-value">${stat.value}</span>
          <span class="stat-label">${stat.label}</span>
        </${stat.action ? "button" : "article"}>
      `
    )
    .join("");
}

function openSidebarSection(sectionKey) {
  if (!["styles", "categories", "scenes"].includes(sectionKey)) {
    return;
  }

  if (isDrawerViewport()) {
    state.mobileDrawerOpen = true;
    state.mobileSearchOpen = false;
  } else if (state.sidebarCollapsed) {
    state.sidebarCollapsed = false;
    writeSidebarPreference(false);
  }

  state.sections = {
    styles: false,
    categories: false,
    scenes: false,
    [sectionKey]: true,
  };
  writeSectionPreferences(state.sections);
  applySidebarState();
  applySectionStates();

  const targetSection = document.querySelector(`.sidebar-section[data-section="${sectionKey}"]`);
  targetSection?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderFilters() {
  renderSidebarMenu({
    container: elements.styleFilters,
    activeValue: state.style,
    options: [
      { value: "all", label: "全部", count: allCases.length },
      ...styleLibrary.styles.map((style) => ({
        value: style.value,
        label: style.title?.zh || style.value,
        count: countByField("styles", style.value),
      })),
    ],
    onSelect(value) {
      state.style = value;
      syncFilterStateToUrl();
      renderFilters();
      renderResults();
    },
  });

  renderSidebarMenu({
    container: elements.categoryFilters,
    activeValue: state.category,
    options: [
      { value: "all", label: "全部分类", count: allCases.length },
      ...styleLibrary.categories.map((category) => ({
        value: category.value,
        label: category.title?.zh || category.value,
        count: countByField("category", category.value),
      })),
    ],
    onSelect(value) {
      state.category = value;
      syncFilterStateToUrl();
      renderFilters();
      renderResults();
    },
  });

  renderSidebarMenu({
    container: elements.sceneFilters,
    activeValue: state.scene,
    options: [
      { value: "all", label: "全部场景", count: allCases.length },
      ...styleLibrary.scenes.map((scene) => ({
        value: scene.value,
        label: scene.title?.zh || scene.value,
        count: countByField("scenes", scene.value),
      })),
    ],
    onSelect(value) {
      state.scene = value;
      syncFilterStateToUrl();
      renderFilters();
      renderResults();
    },
  });

  applySectionStates();
}

function renderSidebarMenu({ container, options, activeValue, onSelect }) {
  container.innerHTML = options
    .map((option) => {
      const shortLabel = getShortLabel(option.label);
      return `
        <button
          type="button"
          class="sidebar-item ${option.value === activeValue ? "active" : ""}"
          data-filter-value="${escapeHtml(option.value)}"
          data-short-label="${escapeAttribute(shortLabel)}"
          title="${escapeAttribute(option.label)}"
        >
          <span class="sidebar-item-label">${escapeHtml(option.label)}</span>
          <span class="sidebar-item-count">${option.count}</span>
        </button>
      `;
    })
    .join("");

  container.querySelectorAll("[data-filter-value]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextValue = button.dataset.filterValue === activeValue ? "all" : button.dataset.filterValue;
      onSelect(nextValue);
      if (isDrawerViewport()) {
        state.mobileDrawerOpen = false;
        state.mobileSearchOpen = false;
        applySidebarState();
      }
    });
  });
}

function applySidebarState() {
  const isDrawer = isDrawerViewport();
  const isCollapsed = state.sidebarCollapsed && window.innerWidth > 1120;
  const drawerVisible = isDrawer && state.mobileDrawerOpen;
  const searchVisible = isDrawer && state.mobileSearchOpen;
  const hasMobileOverlay = drawerVisible || searchVisible;
  const shouldShowExpandButton = isCollapsed || isDrawer;
  const toggleIcon = elements.toggleSidebar.querySelector(".toggle-icon");

  elements.mainLayout.classList.toggle("sidebar-hidden", isCollapsed);
  elements.sidebar.classList.toggle("is-hidden", isCollapsed);
  elements.sidebar.classList.toggle("is-expanded", !isCollapsed);
  elements.sidebar.classList.toggle("is-mobile-drawer", isDrawer);
  elements.sidebar.classList.toggle("is-mobile-open", drawerVisible);
  elements.controlPanel.classList.toggle("is-mobile-search-open", searchVisible);
  elements.contentPanel?.classList.toggle(
    "is-mobile-search-overlay",
    Boolean(isDrawer && searchVisible)
  );

  elements.mobileFloatingActions.classList.toggle("is-hidden", drawerVisible);
  elements.sidebarDrawerBackdrop.classList.toggle("is-visible", hasMobileOverlay);
  elements.sidebarDrawerBackdrop.classList.toggle("is-search-only", searchVisible && !drawerVisible);
  elements.floatingExpandButton.classList.toggle("is-visible", shouldShowExpandButton);

  elements.toggleSidebar.setAttribute("aria-expanded", String(isDrawer ? drawerVisible : !isCollapsed));
  elements.toggleSidebar.setAttribute(
    "aria-label",
    isDrawer ? "关闭筛选抽屉" : isCollapsed ? "展开风格标签侧栏" : "收起风格标签侧栏"
  );
  elements.floatingExpandButton.setAttribute("aria-hidden", String(!shouldShowExpandButton));
  elements.floatingExpandButton.setAttribute("aria-expanded", String(drawerVisible));
  elements.mobileFilterButton.setAttribute("aria-expanded", String(drawerVisible));
  elements.mobileSearchButton.setAttribute("aria-expanded", String(searchVisible));
  elements.mobileFilterButton.setAttribute("aria-label", drawerVisible ? "收起筛选" : "展开筛选");
  elements.mobileSearchButton.setAttribute("aria-label", searchVisible ? "收起搜索" : "展开搜索");
  elements.sidebarDrawerBackdrop.setAttribute("aria-hidden", String(!hasMobileOverlay));
  document.body.dataset.sidebarDrawer = hasMobileOverlay ? "open" : "closed";

  if (toggleIcon) {
    toggleIcon.textContent = isDrawer ? "×" : "◀";
  }

  if (searchVisible) {
    window.setTimeout(() => {
      elements.searchInput.focus();
    }, 30);
  }
}

function applySectionStates() {
  const sectionCurrentMap = {
    styles: state.style === "all" ? "全部风格" : getStyleLabel(state.style),
    categories: state.category === "all" ? "全部分类" : getCategoryLabel(state.category),
    scenes: state.scene === "all" ? "全部场景" : getSceneLabel(state.scene),
  };

  document.querySelectorAll(".sidebar-section").forEach((section) => {
    const sectionKey = section.dataset.section;
    const isOpen = state.sections[sectionKey] !== false;
    section.classList.toggle("is-collapsed", !isOpen);

    const toggle = section.querySelector("[data-section-toggle]");
    if (toggle) {
      toggle.setAttribute("aria-expanded", String(isOpen));
    }

    const currentValue = section.querySelector("[data-section-current]");
    if (currentValue && sectionCurrentMap[sectionKey]) {
      currentValue.textContent = sectionCurrentMap[sectionKey];
    }
  });
}

function renderResults() {
  const filteredCases = getFilteredCases();
  const styleLabel = getStyleLabel(state.style);
  const categoryLabel = getCategoryLabel(state.category);
  const sceneLabel = getSceneLabel(state.scene);
  elements.styleSummary.textContent =
    state.style === "all"
      ? "已按 style-library 风格标签构建筛选"
      : `当前风格：${styleLabel}`;

  elements.resultsTitle.textContent = `共 ${filteredCases.length} 条结果`;
  elements.resultsMeta.innerHTML = renderResultsMeta({
    styleLabel,
    categoryLabel,
    sceneLabel,
    featuredLabel: state.featured ? "精选案例" : "",
    referenceImageLabel: state.referenceImage ? "需要参考图" : "",
    searchLabel: state.search ? `搜索 “${state.search}”` : "",
  });

  if (!filteredCases.length) {
    elements.resultsGrid.innerHTML = `
      <div class="empty-state">
        <p>没有匹配到结果。</p>
        <p>可以尝试减少关键词、切换风格标签，或点击“重置筛选”。</p>
      </div>
    `;
    return;
  }

  elements.resultsGrid.innerHTML = filteredCases
    .map((item) => {
      const preview = item.promptPreview || item.prompt;
      const previewTags = [
        ...(item.requiresReferenceImage ? ["input:referenceImage"] : []),
        ...item.styles.slice(0, 3),
        ...item.scenes.slice(0, 2).map((scene) => `scene:${scene}`),
      ];
      return `
        <article class="case-card" data-case-id="${item.id}">
          <div class="case-image-wrap">
            <img src="${escapeAttribute(resolveAssetPath(item.image))}" alt="${escapeAttribute(item.imageAlt || item.title)}" loading="lazy" />
            <span class="case-badge">#${item.id}</span>
          </div>
          <div class="case-body">
            <span class="case-category">${escapeHtml(getCategoryLabel(item.category))}</span>
            <div class="case-title-row">
              <h3 class="case-title">${escapeHtml(item.title)}</h3>
              <button
                type="button"
                class="card-copy-button"
                data-copy-case-id="${item.id}"
                aria-label="复制提示词"
              >
                <span class="copy-icon" aria-hidden="true">⧉</span>
                <span class="copy-tooltip">复制提示词</span>
              </button>
            </div>
            <p class="case-preview">${escapeHtml(preview)}</p>
            <div class="tag-list">
              ${previewTags
                .map((tag) => {
                  if (tag.startsWith("scene:")) {
                    return `<span class="tag scene">${escapeHtml(getSceneLabel(tag.slice(6)))}</span>`;
                  }
                  if (tag === "input:referenceImage") {
                    return `<span class="tag input">需参考图</span>`;
                  }
                  return `<span class="tag">${escapeHtml(getStyleLabel(tag))}</span>`;
                })
                .join("")}
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function getFilteredCases() {
  return allCases.filter((item) => {
    if (state.featured && !item.featured) {
      return false;
    }

    if (state.referenceImage && !item.requiresReferenceImage) {
      return false;
    }

    if (state.style !== "all" && !item.styles.includes(state.style)) {
      return false;
    }

    if (state.category !== "all" && item.category !== state.category) {
      return false;
    }

    if (state.scene !== "all" && !item.scenes.includes(state.scene)) {
      return false;
    }

    if (!state.search) {
      return true;
    }

    const haystack = [
      item.title,
      item.prompt,
      item.promptPreview,
      item.category,
      item.sourceLabel,
      item.requiresReferenceImage ? "需要参考图 参考图 上传图 模板图 reference image" : "",
      ...(item.styles || []),
      ...(item.scenes || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(state.search.toLowerCase());
  });
}

function openModal(item) {
  activeCase = item;
  elements.detailImage.src = resolveAssetPath(item.image);
  elements.detailImage.alt = item.imageAlt || item.title;
  elements.detailCategory.textContent = getCategoryLabel(item.category);
  elements.detailTitle.textContent = item.title;
  elements.detailId.textContent = `#${item.id}`;
  elements.detailPrompt.textContent = item.prompt;

  const detailTags = [
    ...(item.requiresReferenceImage ? [`<span class="tag input">需参考图</span>`] : []),
    ...item.styles.map((style) => `<span class="tag">${escapeHtml(getStyleLabel(style))}</span>`),
    ...item.scenes.map((scene) => `<span class="tag scene">${escapeHtml(getSceneLabel(scene))}</span>`),
  ];

  elements.detailTags.innerHTML = detailTags.join("");
  elements.modal.classList.add("open");
  elements.modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  closeImageLightbox();
  activeCase = null;
  elements.modal.classList.remove("open");
  elements.modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function openImageLightbox() {
  const imageSrc = elements.detailImage.getAttribute("src");
  if (!imageSrc) {
    return;
  }

  elements.lightboxImage.src = imageSrc;
  elements.lightboxImage.alt = elements.detailImage.alt;
  elements.imageLightbox.classList.add("open");
  elements.imageLightbox.setAttribute("aria-hidden", "false");
}

function closeImageLightbox() {
  elements.imageLightbox.classList.remove("open");
  elements.imageLightbox.setAttribute("aria-hidden", "true");
  elements.lightboxImage.src = "";
  elements.lightboxImage.alt = "";
}

function showCopyToast(message = "复制成功") {
  const isSuccess = message === "复制成功";
  elements.copyToast.querySelector(".copy-toast-text").textContent = message;
  elements.copyToast.classList.toggle("is-success", isSuccess);
  elements.copyToast.classList.toggle("is-error", !isSuccess);
  elements.copyToast.classList.add("is-visible");
  elements.copyToast.setAttribute("aria-hidden", "false");

  window.clearTimeout(showCopyToast.timeoutId);
  showCopyToast.timeoutId = window.setTimeout(() => {
    elements.copyToast.classList.remove("is-visible");
    elements.copyToast.setAttribute("aria-hidden", "true");
  }, 1600);
}

async function copyPromptText(value) {
  try {
    await navigator.clipboard.writeText(value);
    showCopyToast();
  } catch (error) {
    showCopyToast("复制失败，请手动复制");
  }
}

function countByField(field, value) {
  return allCases.filter((item) => {
    const target = item[field];
    if (Array.isArray(target)) {
      return target.includes(value);
    }
    return target === value;
  }).length;
}

function resolveAssetPath(path) {
  if (!path) {
    return "./data/images/banner.svg";
  }
  if (path.startsWith("/images/")) {
    return `./data${path}`;
  }
  return path;
}

function getStyleLabel(value) {
  if (value === "all") {
    return "全部风格";
  }
  const matched = styleLibrary.styles.find((item) => item.value === value || item.id === value);
  return matched?.title?.zh || matched?.value || value;
}

function getCategoryLabel(value) {
  if (value === "all") {
    return "全部分类";
  }
  const matched = styleLibrary.categories.find((item) => item.value === value || item.id === value);
  return matched?.title?.zh || matched?.value || value;
}

function getSceneLabel(value) {
  if (value === "all") {
    return "全部场景";
  }
  const matched = styleLibrary.scenes.find((item) => item.value === value || item.id === value);
  return matched?.title?.zh || matched?.value || value;
}

function getShortLabel(label) {
  const normalized = String(label).trim();
  if (!normalized) {
    return "ALL";
  }
  const compact = normalized.replaceAll(/\s+/g, "");
  return compact.length <= 4 ? compact : compact.slice(0, 4);
}

function renderResultsMeta({
  styleLabel,
  categoryLabel,
  sceneLabel,
  featuredLabel,
  referenceImageLabel,
  searchLabel,
}) {
  const parts = [
    featuredLabel
      ? renderResultsMetaItem({ key: "featured", label: featuredLabel, isActive: true })
      : `<span class="results-meta-item">全部案例</span>`,
    renderResultsMetaItem({ key: "style", label: styleLabel, isActive: state.style !== "all" }),
    renderResultsMetaItem({ key: "category", label: categoryLabel, isActive: state.category !== "all" }),
    renderResultsMetaItem({ key: "scene", label: sceneLabel, isActive: state.scene !== "all" }),
  ];

  if (referenceImageLabel) {
    parts.push(renderResultsMetaItem({ key: "referenceImage", label: referenceImageLabel, isActive: true }));
  }

  if (searchLabel) {
    parts.push(`<span class="results-meta-item">${escapeHtml(searchLabel)}</span>`);
  }

  return parts.join('<span class="results-meta-separator">·</span>');
}

function renderResultsMetaItem({ key, label, isActive }) {
  if (!isActive) {
    return `<span class="results-meta-item">${escapeHtml(label)}</span>`;
  }

  return `
    <button type="button" class="results-meta-clear" data-clear-filter="${escapeAttribute(key)}">
      <span>${escapeHtml(label)}</span>
      <span class="results-meta-clear-icon" aria-hidden="true">×</span>
    </button>
  `;
}

function readFilterStateFromUrl() {
  const searchParams = new URLSearchParams(window.location.search);

  return {
    style: getValidUrlFilterValue(searchParams.get("style"), styleLibrary.styles.map((item) => item.value)),
    category: getValidUrlFilterValue(
      searchParams.get("category"),
      styleLibrary.categories.map((item) => item.value)
    ),
    scene: getValidUrlFilterValue(searchParams.get("scene"), styleLibrary.scenes.map((item) => item.value)),
    featured: searchParams.get("featured") === "1",
    referenceImage: searchParams.get("referenceImage") === "1",
  };
}

function getValidUrlFilterValue(value, allowedValues) {
  if (!value || value === "all") {
    return "all";
  }

  return allowedValues.includes(value) ? value : "all";
}

function syncFilterStateToUrl() {
  const url = new URL(window.location.href);

  updateUrlFilterParam(url.searchParams, "style", state.style);
  updateUrlFilterParam(url.searchParams, "category", state.category);
  updateUrlFilterParam(url.searchParams, "scene", state.scene);
  updateUrlBooleanParam(url.searchParams, "featured", state.featured);
  updateUrlBooleanParam(url.searchParams, "referenceImage", state.referenceImage);

  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

function updateUrlFilterParam(searchParams, key, value) {
  if (!value || value === "all") {
    searchParams.delete(key);
    return;
  }

  searchParams.set(key, value);
}

function updateUrlBooleanParam(searchParams, key, value) {
  if (!value) {
    searchParams.delete(key);
    return;
  }

  searchParams.set(key, "1");
}

function isDrawerViewport() {
  return window.innerWidth <= 820;
}

function readSidebarPreference() {
  try {
    return window.localStorage.getItem("gptimage2-sidebar-collapsed") === "true";
  } catch (error) {
    return false;
  }
}

function writeSidebarPreference(value) {
  try {
    window.localStorage.setItem("gptimage2-sidebar-collapsed", String(value));
  } catch (error) {
    // Ignore storage failures in restricted browser modes.
  }
}

function readSectionPreferences() {
  try {
    const rawValue = window.localStorage.getItem("gptimage2-sidebar-sections");
    const parsed = rawValue ? JSON.parse(rawValue) : {};
    return {
      styles: parsed.styles !== false,
      categories: parsed.categories !== false,
      scenes: parsed.scenes !== false,
    };
  } catch (error) {
    return {
      styles: true,
      categories: true,
      scenes: true,
    };
  }
}

function writeSectionPreferences(value) {
  try {
    window.localStorage.setItem("gptimage2-sidebar-sections", JSON.stringify(value));
  } catch (error) {
    // Ignore storage failures in restricted browser modes.
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
