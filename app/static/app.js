(() => {
  "use strict";
  if (/Electron/i.test(navigator.userAgent))
    document.documentElement.classList.add("desktop");
  const paths = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    compass:
      '<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z"/>',
    film: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
    folder:
      '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
    sliders:
      '<path d="M4 7h8M16 7h4M4 17h4M12 17h8"/><circle cx="14" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    chevrons: '<path d="m9 9 3-3 3 3M9 15l3 3 3-3"/>',
    refresh:
      '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.6 8a7 7 0 0 1 11.8-2L20 9M4 15l2.6 3A7 7 0 0 0 18.4 16"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    sparkles:
      '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/><path d="M20 2v4M18 4h4"/>',
    "arrow-up-right": '<path d="M6 18 18 6M6 6h12v12"/>',
    "arrow-right": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    play: '<path d="m8 5 11 7-11 7V5Z"/>',
    wave: '<path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    magic:
      '<path d="m4 20 12-12 4 4L8 24M13 11l4 4M5 3v4M3 5h4M17 2v4M15 4h4M21 17v4M19 19h4" transform="translate(0 -2)"/>',
    upload:
      '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/>',
    audio:
      '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',
    activity: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    leaf: '<path d="M20 3c0 12-2 17-9 17a7 7 0 0 1-7-7C4 6 10 5 20 3Z"/><path d="M4 21 15 10"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    youtube:
      '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3V9Z"/>',
    link: '<path d="m10 13 4-4M9 15l-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M15 9l2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(0 -1) scale(.95)"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
    x: '<path d="m6 6 12 12M6 18 18 6"/>',
    globe:
      '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
    trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
    cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
  };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) =>
    Array.from(root.querySelectorAll(selector));
  const state = {
    view: "dashboard",
    news: [],
    projects: [],
    status: null,
    selected: null,
    filter: "all",
    search: "",
    newsWarning: "",
    newsError: "",
    dirty: false,
    poll: null,
    toastTimer: null,
    projectSearch: "",
    projectFilter: "all",
    sources: [],
    lastRefreshed: null,
    cached: false,
    pollInFlight: false,
    confirmResolver: null,
    translatingProjectIds: new Set(),
    audioBusy: false,
    audioTimingDirty: false,
    audioTimingKey: "",
  };
  const labels = {
    dashboard: "Genel bakış",
    news: "Haber keşfi",
    studio: "Video stüdyosu",
    videos: "Videolarım",
    settings: "Bağlantılar ve ayarlar",
  };
  const statusLabels = {
    draft: "Taslak",
    ready: "Yayına hazır",
    rendering: "Hazırlanıyor",
    queued: "Sırada",
    error: "İşlem başarısız",
    uploaded: "YouTube’a yüklendi",
    uploading: "Yükleniyor",
    translating: "Türkçeye çevriliyor",
    processing_audio: "Ses işleniyor",
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function icon(name) {
    const node = el("span");
    node.dataset.icon = name;
    node.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      (paths[name] || paths.film) +
      "</svg>";
    return node;
  }
  function hydrateIcons() {
    $$("[data-icon]").forEach((node) => {
      if (!node.firstElementChild)
        node.replaceChildren(icon(node.dataset.icon).firstElementChild);
    });
  }
  function safeUrl(value, localOnly = false) {
    if (typeof value !== "string" || !value.trim()) return "";
    try {
      const url = new URL(value.trim(), location.origin);
      return ["http:", "https:"].includes(url.protocol) &&
        !url.username &&
        !url.password &&
        (!localOnly || url.origin === location.origin)
        ? url.href
        : "";
    } catch {
      return "";
    }
  }
  function sourceLink(url, text, className) {
    const anchor = el("a", className, text);
    const href = safeUrl(url);
    if (href) {
      anchor.href = href;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
    } else {
      anchor.removeAttribute("href");
    }
    return anchor;
  }
  function prettyDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("tr-TR", {
      day: "numeric",
      month: "short",
    }).format(date);
  }
  function ago(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const minutes = Math.max(0, Math.floor((Date.now() - date) / 60000));
    if (minutes < 1) return "Az önce";
    if (minutes < 60) return minutes + " dk önce";
    if (minutes < 1440) return Math.floor(minutes / 60) + " sa önce";
    return prettyDate(value);
  }
  function toast(message, error = false) {
    const target = $("#toast");
    target.textContent = message;
    target.classList.toggle("error", error);
    target.hidden = false;
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(
      () => {
        target.hidden = true;
      },
      error ? 7500 : 4200,
    );
  }
  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(
        "Sunucudan beklenmeyen bir yanıt alındı. Uygulamanın çalıştığını kontrol et.",
      );
    }
    if (!response.ok) {
      const error = new Error(
        data.error ||
          data.message ||
          "İşlem tamamlanamadı. Lütfen yeniden dene.",
      );
      error.details = data;
      error.status = response.status;
      throw error;
    }
    return data;
  }
  async function busy(button, work) {
    const disabled = button.disabled;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    try {
      return await work();
    } finally {
      button.disabled = disabled;
      button.removeAttribute("aria-busy");
    }
  }
  function clearError(id) {
    $(id).hidden = true;
    $(id).textContent = "";
  }
  function showError(id, message) {
    $(id).hidden = false;
    $(id).textContent = message;
  }
  function emptyState(title, message, iconName = "sparkles", action = null) {
    const box = el("div", "empty-state");
    box.append(icon(iconName), el("h3", "", title), el("p", "", message));
    if (action) {
      const button = el("button", "button button-outline", action.label);
      button.type = "button";
      button.addEventListener("click", action.run);
      box.append(button);
    }
    return box;
  }

  async function navigate(view, updateHash = true, skipGuard = false) {
    if (!labels[view]) view = "dashboard";
    if (view !== state.view && !skipGuard && !(await canDiscard())) {
      history.replaceState(null, "", "#" + state.view);
      return false;
    }
    state.view = view;
    $$(".view").forEach((section) => {
      section.hidden = section.id !== "view-" + view;
    });
    $$(".nav-item[data-view]").forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    $("#breadcrumb-current").textContent = labels[view];
    if (updateHash) history.replaceState(null, "", "#" + view);
    $(".main-panel").scrollTop = 0;
    if (window.innerWidth < 1000)
      window.scrollTo({ top: 0, behavior: "instant" });
    return true;
  }
  function askConfirmation(title, message, acceptLabel = "Onayla") {
    if (state.confirmResolver) return Promise.resolve(false);
    $("#confirm-title").textContent = title;
    $("#confirm-message").textContent = message;
    $("#confirm-accept").textContent = acceptLabel;
    $("#confirm-dialog").showModal();
    $("#confirm-cancel").focus();
    return new Promise((resolve) => {
      state.confirmResolver = resolve;
    });
  }
  function resolveConfirmation(accepted) {
    const resolve = state.confirmResolver;
    state.confirmResolver = null;
    $("#confirm-dialog").close();
    if (resolve) resolve(accepted);
  }
  async function canDiscard() {
    if (state.audioBusy) {
      toast("Ses dosyası işleminin tamamlanmasını bekle.");
      return false;
    }
    if (!state.dirty && !state.audioTimingDirty) return true;
    const accepted = await askConfirmation(
      "Kaydedilmemiş değişiklikler var",
      "Bu projedeki düzenlemelerin henüz kaydedilmedi. Devam edersen bu değişiklikler silinecek.",
      "Değişiklikleri bırak",
    );
    if (accepted) {
      state.dirty = false;
      state.audioTimingDirty = false;
      if (state.selected) fillEditor(state.selected);
    }
    return accepted;
  }
  function activeProject(project) {
    return ["queued", "rendering", "uploading", "translating", "processing_audio"].includes(project?.status) ||
      state.translatingProjectIds.has(project?.id);
  }
  function markDirty() {
    $("#dirty-indicator").textContent = state.dirty
      ? "Kaydedilmedi"
      : "Kaydedildi";
    $("#dirty-indicator").classList.toggle("unsaved", state.dirty);
  }

  function newsMeta(item) {
    const meta = el("div", "news-meta");
    meta.append(el("span", "", item.source || "Haber kaynağı"));
    if (item.published)
      meta.append(
        el("i", "meta-dot"),
        el("time", "", prettyDate(item.published)),
      );
    return meta;
  }
  function newsTile(index) {
    const tile = el("div", "news-tile tile-" + (index % 3));
    tile.append(icon(["cpu", "sparkles", "globe"][index % 3]));
    return tile;
  }
  function openNewsDraft(item) {
    showTranslation(item);
  }
  function renderDashboardNews() {
    const list = $("#dashboard-news");
    list.replaceChildren();
    if (!state.news.length) {
      list.append(
        emptyState(
          state.newsError
            ? "Haber kaynaklarına erişilemiyor"
            : "Sıradaki hikâyen seni bekliyor.",
          state.newsError ||
            state.newsWarning ||
            "Kaynakları yenile veya kendi fikrinle yeni bir video oluştur.",
          "compass",
          { label: "Haber keşfine git", run: () => navigate("news") },
        ),
      );
      return;
    }
    state.news.slice(0, 3).forEach((item, i) => {
      const row = el("article", "news-preview");
      const body = el("div", "news-preview-body");
      body.append(newsMeta(item), el("h3", "", item.title));
      const button = el("button", "icon-button");
      button.type = "button";
      button.title = "Türkçe video hazırla";
      button.setAttribute(
        "aria-label",
        item.title + " haberinden Türkçe video hazırla",
      );
      button.append(icon("arrow-up-right"));
      button.addEventListener("click", () => openNewsDraft(item));
      row.append(newsTile(i), body, button);
      list.append(row);
    });
  }
  function matchesFilter(item) {
    if (
      state.search &&
      ![item.title, item.summary, item.source]
        .join(" ")
        .toLocaleLowerCase("tr")
        .includes(state.search.toLocaleLowerCase("tr"))
    )
      return false;
    if (state.filter === "all") return true;
    const isAi =
      /yapay zek|\bai\b|openai|anthropic|claude|chatgpt|llm|machine learning|artificial intelligence/i.test(
        [item.category, item.title, item.summary].join(" "),
      );
    return state.filter === "ai" ? isAi : !isAi;
  }
  function renderNews() {
    const grid = $("#news-grid");
    grid.replaceChildren();
    if (state.newsWarning || state.newsError)
      showError("#news-warning", state.newsWarning || state.newsError);
    else clearError("#news-warning");
    const items = state.news.filter(matchesFilter);
    if (!items.length) {
      grid.append(
        emptyState(
          state.news.length
            ? "Bu aramada henüz bir hikâye yok."
            : "Haberlerini buraya getirelim.",
          state.news.length
            ? "Farklı bir konu veya kategori deneyebilirsin."
            : "Kaynakları yenile. Erişim sağlanamazsa kendi başlığınla üretmeye devam edebilirsin.",
          "compass",
          { label: "Kendi fikrimle başla", run: () => showNewProject() },
        ),
      );
      return;
    }
    items.forEach((item, i) => {
      const card = el("article", "news-card");
      const top = el("div", "news-card-top");
      top.append(newsTile(i));
      if (Number.isFinite(Number(item.score))) {
        const score = el(
          "span",
          "score-tag",
          "İlgi tahmini · " + Math.round(Number(item.score)),
        );
        score.title =
          "Güncellik ve konu kelimelerine göre hesaplanır; doğrulanmış trend verisi değildir.";
        top.append(score);
      }
      const footer = el("div", "news-card-footer");
      const link = sourceLink(item.url, "Kaynağı oku", "text-button");
      link.append(icon("arrow-up-right"));
      const button = el("button", "button button-outline", "Türkçe video hazırla");
      button.type = "button";
      button.dataset.action = "translate-news";
      button.append(icon("globe"));
      button.addEventListener("click", () => openNewsDraft(item));
      footer.append(link, button);
      card.append(
        top,
        el("h3", "", item.title),
        el("p", "", item.summary || "Ayrıntıları kaynaktan okuyarak incele."),
        newsMeta(item),
        footer,
      );
      grid.append(card);
    });
  }
  function renderStats() {
    const stats = state.status?.stats || {};
    $("#stat-news").textContent = String(state.news.length || stats.news || 0);
    $("#stat-projects").textContent = String(state.projects.length);
    const ready = state.projects.filter(
      (project) =>
        project.video_url && ["ready", "uploaded"].includes(project.status),
    ).length;
    $("#stat-ready").textContent = String(ready);
    $("#nav-project-count").textContent = String(state.projects.length);
  }
  function renderProjects() {
    const grid = $("#projects-grid");
    grid.replaceChildren();
    const query = state.projectSearch.trim().toLocaleLowerCase("tr");
    const projects = state.projects.filter((project) => {
      const matchesText =
        !query ||
        [project.title, project.script, project.description]
          .join(" ")
          .toLocaleLowerCase("tr")
          .includes(query);
      const filter = state.projectFilter;
      const matchesStatus =
        filter === "all" ||
        (filter === "uploaded"
          ? !!project.youtube_url
          : filter === "rendering"
            ? activeProject(project)
            : filter === "ready"
              ? project.status === "ready" && !project.youtube_url
              : project.status === filter);
      return matchesText && matchesStatus;
    });
    $("#project-result-count").textContent =
      projects.length + " / " + state.projects.length + " proje";
    if (!projects.length) {
      grid.append(
        emptyState(
          state.projects.length
            ? "Eşleşen proje bulunamadı."
            : "İlk projen için hazırsın.",
          state.projects.length
            ? "Arama metnini veya durum filtresini değiştirebilirsin."
            : "Bir haber seç veya kendi fikrinle video üretmeye başla.",
          "folder",
          { label: "Yeni proje", run: () => showNewProject() },
        ),
      );
      return;
    }
    projects.forEach((project) => {
      const card = el("article", "project-card");
      const open = el("button", "project-open");
      open.type = "button";
      open.setAttribute("aria-label", project.title + " projesini aç");
      const cover = el("div", "project-cover");
      const top = el("div", "project-cover-top", "HYPE ORIGINALS");
      top.append(icon("sparkles"));
      cover.append(
        top,
        el("span", "project-cover-star", "✳︎"),
        el("h3", "", project.title),
      );
      const body = el("div", "project-card-body");
      const meta = el("div", "project-card-meta");
      meta.append(
        el(
          "span",
          "project-status",
          project.youtube_url
            ? "YouTube’a yüklendi"
            : statusLabels[project.status] || "Taslak",
        ),
        el("time", "", prettyDate(project.created)),
        icon("arrow-up-right"),
      );
      body.append(el("h3", "", project.title), meta);
      open.append(cover, body);
      open.addEventListener("click", () => openProject(project.id));
      const actions = el("div", "project-card-actions");
      const duplicate = el("button", "project-action-button", "Çoğalt");
      duplicate.type = "button";
      duplicate.prepend(icon("copy"));
      duplicate.disabled = activeProject(project);
      duplicate.setAttribute("aria-label", project.title + " projesini çoğalt");
      duplicate.addEventListener("click", () =>
        duplicateProject(project, duplicate),
      );
      const exportLink = el("a", "project-action-button", "JSON");
      exportLink.href =
        "/api/projects/" + encodeURIComponent(project.id) + "/export";
      exportLink.download = "hype-project-" + project.id + ".json";
      exportLink.setAttribute(
        "aria-label",
        project.title + " projesini JSON olarak dışa aktar",
      );
      exportLink.prepend(icon("download"));
      const remove = el("button", "project-action-button delete-action");
      remove.type = "button";
      remove.title = "Projeyi sil";
      remove.setAttribute("aria-label", project.title + " projesini sil");
      remove.append(icon("trash"));
      remove.disabled = activeProject(project);
      remove.addEventListener("click", () => deleteProject(project, remove));
      actions.append(duplicate, exportLink, remove);
      card.append(open, actions);
      grid.append(card);
    });
  }
  async function duplicateProject(project, button) {
    if (!(await canDiscard())) return;
    await busy(button, async () => {
      try {
        const copy = projectFromResponse(
          await api(
            "/api/projects/" + encodeURIComponent(project.id) + "/duplicate",
            { method: "POST", body: "{}" },
          ),
        );
        updateProject(copy);
        await openProject(copy.id);
        toast("Projenin yeni bir taslak kopyası oluşturuldu.");
        loadActivity().catch(() => {});
      } catch (error) {
        toast(error.message, true);
      }
    });
  }
  async function deleteProject(project, button) {
    const accepted = await askConfirmation(
      "Bu proje silinsin mi?",
      "“" +
        project.title +
        "” projesi ve yerel video dosyaları silinecek. YouTube'a yüklenmiş bir video varsa bu işlem YouTube'daki videoyu silmez.",
      "Projeyi sil",
    );
    if (!accepted) return;
    await busy(button, async () => {
      try {
        await api("/api/projects/" + encodeURIComponent(project.id), {
          method: "DELETE",
        });
        state.projects = state.projects.filter(
          (item) => item.id !== project.id,
        );
        if (state.selected?.id === project.id) {
          state.selected = null;
          state.dirty = false;
          $("#studio-editor").hidden = true;
          $("#studio-empty").hidden = false;
          $("#preview-video").pause();
          $("#preview-video").removeAttribute("src");
          showStudioError("");
          try {
            localStorage.removeItem("hype-selected-project");
          } catch {}
        }
        renderProjects();
        renderStats();
        toast("Proje silindi.");
        loadActivity().catch(() => {});
      } catch (error) {
        toast(error.message, true);
      }
    });
  }

  function updateProject(project) {
    const index = state.projects.findIndex((item) => item.id === project.id);
    if (index === -1) state.projects.unshift(project);
    else state.projects[index] = project;
    renderStats();
    renderProjects();
  }
  function renderSettings() {
    const status = state.status;
    if (!status) return;
    const list = $("#local-status-list");
    list.replaceChildren();
    [
      ["Video motoru · FFmpeg", status.ffmpeg],
      [
        "Türkçe ses · " + (status.providers?.tts || status.provider || "Yerel"),
        status.tts,
      ],
      ["Ücretsiz senaryo şablonu", true],
      ["YouTube yetkilendirmesi", status.youtube],
    ].forEach(([name, available]) => {
      const row = el("div");
      const value = el(
        "span",
        available ? "" : "unavailable",
        available ? "Hazır" : "Yapılandırılmalı",
      );
      value.prepend(el("i"));
      row.append(el("span", "", name), value);
      list.append(row);
    });
    $("#engine-state").textContent = status.tts
      ? "Yerel ses hazır"
      : "Ses kurulumu gerekli";
    $("#connect-youtube").replaceChildren(
      icon(status.youtube ? "check" : "link"),
      document.createTextNode(
        status.youtube ? "Hesabı yeniden bağla" : "Hesabını bağla",
      ),
    );
    const warnings = Array.isArray(status.warnings) ? status.warnings : [];
    if (warnings.length) showError("#system-message", warnings.join(" "));
    else clearError("#system-message");
    const elevenOption = $('#tts-provider option[value="elevenlabs"]');
    elevenOption.disabled =
      !status.elevenlabs && !status.configured?.elevenlabs;
    elevenOption.textContent = elevenOption.disabled
      ? "ElevenLabs API · yapılandırılmamış"
      : "ElevenLabs API · kota/ücret olabilir";
    const audioLimits = status.audio_upload;
    if (audioLimits) $("#voice-upload-limits").textContent = "MP3 veya WAV · en fazla " +
      Math.round((audioLimits.max_bytes || 26214400) / 1024 / 1024) + " MB / " +
      (audioLimits.max_duration || 90) + " saniye";
    renderTranslationHelp();
  }
  function renderTranslationHelp() {
    const translation = state.status?.translation;
    const providers = translation?.providers;
    $$(".translation-provider").forEach((select) => {
      ["openai", "anthropic"].forEach((provider) => {
        const option = $('option[value="' + provider + '"]', select);
        option.disabled = !!providers && !providers[provider];
        option.textContent =
          (provider === "openai" ? "OpenAI API" : "Claude API") +
          (option.disabled ? " · API anahtarı gerekli" : " · ücretli olabilir");
      });
    });
    ["#translation-setup", "#editor-translation-help", "#settings-translation-help"].forEach((id) => {
      const target = $(id);
      const select = id === "#translation-setup" ? $("#translation-provider") :
        id === "#editor-translation-help" ? $("#editor-translation-provider") : null;
      target.replaceChildren();
      if (select && select.value !== "ollama") {
        target.append(el("p", "field-help", "Seçtiğin API sağlayıcısı ayrıca ücretlendirebilir. ChatGPT / Claude abonelikleri API kullanımını kapsamaz."));
        return;
      }
      const ready = providers?.ollama;
      target.append(el("p", "field-help", ready
        ? "Ollama modeli hazır · " + (translation.model || "yerel model") + ". Çeviri cihazında çalışır."
        : ready === false
          ? "Ollama modeli hazır değil. Ücretsiz çeviri için Mac'inde Ollama'yı ve modeli kur, ardından stüdyoyu yenile."
          : "Ücretsiz çeviri için yerel Ollama ve bir model gerekir. Sağlayıcı durumu henüz doğrulanmadı."));
      const guide = el("details", "translation-install");
      guide.append(el("summary", "", "Ücretsiz yerel çeviri kurulumu"));
      const commands = translation?.setup_commands || ["brew install ollama", "brew services start ollama", "ollama pull llama3.2:3b"];
      const code = el("code", "", commands.join("\n"));
      const pre = el("pre");
      pre.append(code);
      guide.append(el("p", "field-help", "Mac Terminal'de sırayla çalıştır (Homebrew gerekli). İlk model indirmesi internet ve boş disk alanı gerektirir."), pre,
        el("p", "field-help", "Model indirildikten sonra üstteki yenile düğmesine bas. Ücretli bir sağlayıcıya otomatik geçilmez."));
      target.append(guide);
    });
  }
  async function loadStatus() {
    state.status = await api("/api/status");
    renderSettings();
    renderStats();
  }
  async function loadNews(refresh = false) {
    const data = await api(
      "/api/news" + (refresh ? "/refresh" : ""),
      refresh ? { method: "POST", body: "{}" } : {},
    );
    state.news = data.items || [];
    state.newsWarning = data.warning || "";
    state.newsError = "";
    state.sources = Array.isArray(data.sources) ? data.sources : [];
    state.lastRefreshed = data.last_refreshed || null;
    state.cached = !!data.cached;
    renderSourceHealth();
    renderNews();
    renderDashboardNews();
    renderStats();
    if (refresh)
      toast(
        state.news.length
          ? state.news.length + " haber keşfe hazır."
          : state.newsWarning ||
              "Kaynaklar şu anda kullanılabilir haber döndürmedi.",
        !state.news.length,
      );
  }
  function renderSourceHealth() {
    const health = $("#source-health");
    health.replaceChildren();
    state.sources.forEach((source) => {
      const chip = el("span", "source-chip");
      const available = ["ok", "ready", "success"].includes(source.status);
      const cached = source.status === "cached";
      chip.dataset.state = available
        ? "ready"
        : cached
          ? "cached"
          : source.status === "unknown"
            ? "unknown"
            : "error";
      const label = available
        ? (Number(source.count) || 0) + " haber"
        : cached
          ? "Önbellek"
          : source.status === "unknown"
            ? "Henüz taranmadı"
            : "Erişilemiyor";
      chip.append(
        el("i"),
        document.createTextNode(
          (source.source || source.name || "Kaynak") + " · " + label,
        ),
      );
      if (source.error) chip.title = source.error;
      health.append(chip);
    });
    const stamp = state.lastRefreshed ? new Date(state.lastRefreshed) : null;
    $("#news-refreshed").textContent =
      stamp && !Number.isNaN(stamp.getTime())
        ? "Son yenileme: " +
          stamp.toLocaleString("tr-TR", {
            day: "numeric",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          }) +
          (state.cached ? " · Kayıtlı haberler gösteriliyor" : "")
        : "Kaynakları yenileyerek haber akışını başlat.";
  }

  async function loadProjects(notify = false) {
    const data = await api("/api/projects");
    const previous = new Map(
      state.projects.map((project) => [project.id, project]),
    );
    state.projects = data.items || [];
    state.projects.forEach((project) => {
      if (notify) notifyTransition(previous.get(project.id), project);
    });
    if (state.selected) {
      const latest = state.projects.find(
        (project) => project.id === state.selected.id,
      );
      if (latest) {
        state.selected = latest;
        if (previous.get(latest.id)?.status === "translating" && latest.status !== "translating" &&
            !state.dirty && !state.translatingProjectIds.has(latest.id)) fillEditor(latest);
        else updatePreview(latest);
      }
    }
    renderStats();
    renderProjects();
    if (state.projects.some(activeProject)) startPolling();
  }
  function notifyTransition(previous, project) {
    if (!previous || !activeProject(previous) || activeProject(project)) return;
    if (previous.status === "translating") {
      if (!state.translatingProjectIds.has(project.id) && project.language === "tr")
        toast("Türkçe metinler hazır. Videoyu yeniden oluştur: " + project.title);
    } else if (previous.status === "uploading")
      toast(
        project.youtube_url && !project.error
          ? "YouTube yüklemesi tamamlandı: " + project.title
          : project.error ||
              "Yükleme doğrulanamadı; YouTube kanalını kontrol et.",
        !!project.error || !project.youtube_url,
      );
    else if (project.error || project.status === "error")
      toast(project.error || "Video oluşturulamadı: " + project.title, true);
    else if (project.status === "ready") {
      toast("Video hazır: " + project.title);
      if (state.view === "studio" && state.selected?.id === project.id && !state.dirty) {
        requestAnimationFrame(() => $("#preview-phone").scrollIntoView({
          block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
        }));
      }
    }
  }

  async function loadActivity() {
    const data = await api("/api/activity");
    const list = $("#activity-list");
    list.replaceChildren();
    const items = (data.items || []).slice(0, 4);
    if (!items.length) {
      list.append(
        el(
          "p",
          "quiet-empty",
          "Henüz bir hareket yok. Yeni bir hikâyeyle başla.",
        ),
      );
      return;
    }
    items.forEach((item) => {
      const row = el("div", "activity-row");
      const body = el("div");
      body.append(
        el("p", "", item.text || item.message || "Stüdyo güncellendi."),
        el("time", "", ago(item.created)),
      );
      row.append(el("i", "activity-dot"), body);
      list.append(row);
    });
  }

  async function showNewProject(values = {}) {
    if (!(await canDiscard())) return;
    const dialog = $("#new-project-dialog");
    $("#new-project-form").reset();
    $("#new-title").value = values.title || "";
    $("#new-summary").value = values.summary || "";
    $("#new-url").value = values.url || "";
    dialog._draftSource = values;
    clearError("#new-project-error");
    dialog.showModal();
    $("#new-title").focus();
  }
  async function showTranslation(article) {
    if (!(await canDiscard())) return;
    const dialog = $("#translation-dialog");
    $("#translation-form").reset();
    dialog._article = { ...article };
    dialog._translation = null;
    $("#translation-original-title").textContent = article.title || "";
    $("#translation-original-summary").textContent = article.summary || "Ayrı bir özet bulunmuyor.";
    const source = $("#translation-source-link");
    source.replaceChildren();
    if (article.url) source.append(sourceLink(article.url, article.source || "Kaynağı oku", "text-button"));
    clearError("#translation-error");
    setArticleTranslationBusy(false);
    renderTranslationHelp();
    $("#new-project-dialog").close();
    dialog.showModal();
    $("#translate-article").focus();
  }
  function setArticleTranslationBusy(running, creating = false) {
    const dialog = $("#translation-dialog");
    if (running) dialog.setAttribute("aria-busy", "true");
    else dialog.removeAttribute("aria-busy");
    $$("input, textarea, select, button", dialog).forEach((control) => {
      control.disabled = running;
    });
    $("#create-translated-project").disabled = running || !dialog._translation;
    $("#translation-progress").hidden = !running;
    $("#translation-progress").replaceChildren(icon("globe"), document.createTextNode(
      creating ? "Türkçe video taslağı oluşturuluyor…" : "Haber Türkçeye çevriliyor…",
    ));
  }
  async function translateArticle() {
    const dialog = $("#translation-dialog");
    if (dialog.getAttribute("aria-busy") === "true") return;
    const article = dialog._article;
    if (!article) return;
    clearError("#translation-error");
    const provider = $("#translation-provider").value;
    const payload = article.id ? { news_id: article.id, provider } : {
      title: article.title, summary: article.summary || "", url: article.url || "",
      source: article.source || "Manuel", provider,
    };
    setArticleTranslationBusy(true);
    try {
      const translated = await api("/api/translate", { method: "POST", body: JSON.stringify(payload) });
      dialog._translation = translated;
      $("#translation-title").value = translated.title || "";
      $("#translation-summary").value = translated.summary || "";
      $("#translation-title").focus();
    } catch (error) {
      showError("#translation-error", error.message);
    } finally {
      setArticleTranslationBusy(false);
    }
  }
  async function createTranslatedProject(event) {
    event.preventDefault();
    const dialog = $("#translation-dialog");
    if (!dialog._translation || dialog.getAttribute("aria-busy") === "true") return;
    clearError("#translation-error");
    const translated = dialog._translation;
    const payload = {
      title: $("#translation-title").value.trim(), summary: $("#translation-summary").value.trim(),
      url: translated.source_url || "", source: translated.source || "Manuel",
      mode: "template", language: "tr", translation: { ...translated },
    };
    if (!payload.title) return showError("#translation-error", "Türkçe başlığı yaz.");
    setArticleTranslationBusy(true, true);
    try {
      const project = projectFromResponse(await api("/api/projects", {
        method: "POST", body: JSON.stringify(payload),
      }));
      updateProject(project);
      dialog.close();
      await openProject(project.id);
      toast("Türkçe taslak hazır. Seslendirme ve altyazılar bu metinden üretilecek.");
      loadActivity().catch(() => {});
    } catch (error) {
      showError("#translation-error", error.message);
    } finally {
      setArticleTranslationBusy(false);
    }
  }
  async function translateNewArticle() {
    clearError("#new-project-error");
    const title = $("#new-title").value.trim();
    if (!title) return showError("#new-project-error", "Önce çevirmek istediğin başlığı ve varsa özeti yaz.");
    if (!$("#new-url").checkValidity()) return $("#new-url").reportValidity();
    const source = $("#new-project-dialog")._draftSource || {};
    await showTranslation({ title, summary: $("#new-summary").value.trim(),
      url: $("#new-url").value.trim(), source: source.source || "Manuel" });
  }
  function projectFromResponse(data) {
    return data.project || data;
  }
  async function createProject(event) {
    event.preventDefault();
    clearError("#new-project-error");
    const source = $("#new-project-dialog")._draftSource || {};
    const payload = {
      title: $("#new-title").value.trim(),
      summary: $("#new-summary").value.trim(),
      url: $("#new-url").value.trim(),
      source: source.source || "Kendi fikrim",
      mode: $("#new-mode").value,
      language: $("#new-language").value,
    };
    if (!payload.title || !payload.summary)
      return showError(
        "#new-project-error",
        "Başlığını ve hikâyenin özünü yaz.",
      );
    if (source.news_id) payload.news_id = source.news_id;
    await busy($("#create-project"), async () => {
      try {
        const project = projectFromResponse(
          await api("/api/projects", {
            method: "POST",
            body: JSON.stringify(payload),
          }),
        );
        updateProject(project);
        $("#new-project-dialog").close();
        await openProject(project.id);
        toast("Taslağın hazır. Kendi anlatımını ekleyebilirsin.");
        loadActivity().catch(() => {});
      } catch (error) {
        showError("#new-project-error", error.message);
      }
    });
  }
  function countWords() {
    const text = $("#edit-script").value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    $("#script-word-count").textContent = words + " kelime";
    $("#preview-title").textContent =
      $("#edit-title").value || "Hikâyene bir başlık ver.";
  }
  function audioIsStale(project) {
    const normalize = (value) => value.normalize("NFC").replace(/\s+/g, " ").trim();
    return !!project.audio && (project.audio.valid === false ||
      normalize($("#edit-script").value) !== normalize(project.script || ""));
  }
  function updateAudio(project) {
    const audio = project.audio;
    const locked = activeProject(project) || state.audioBusy;
    const stale = audioIsStale(project);
    const provider = $("#tts-provider");
    $('option[value="uploaded"]', provider).disabled = !audio;
    if (!audio && provider.value === "uploaded") provider.value = "local";
    $("#audio-file-panel").hidden = !audio;
    $("#audio-warning").hidden = !stale;
    $("#audio-warning").textContent = stale
      ? "Metin değişti. Aynı metinden üretilen sesi yeniden yükle." : "";
    $("#copy-script").disabled = locked;
    $("#download-script").disabled = locked;
    $("#voice-file").disabled = locked;
    $("#upload-voice").disabled = locked || !$("#voice-file").files.length;
    $("#upload-voice").setAttribute("aria-busy", state.audioBusy ? "true" : "false");
    $("#remove-audio").disabled = locked || !audio;
    $("#save-audio-timings").disabled = locked || stale || !audio || !state.audioTimingDirty;
    if (provider.value === "uploaded")
      $("#render-project").disabled = locked || !audio || stale || state.audioTimingDirty;
    else $("#render-project").disabled = locked;
    const preview = $("#audio-preview");
    if (!audio) {
      preview.pause();
      preview.removeAttribute("src");
      $("#audio-info").textContent = "";
      $("#audio-timings-body").replaceChildren();
      state.audioTimingKey = "";
      state.audioTimingDirty = false;
      return;
    }
    const duration = Number(audio.duration) || 0;
    $("#audio-info").textContent = audio.filename + " · " +
      duration.toLocaleString("tr-TR", { maximumFractionDigits: 2 }) + " saniye" +
      (stale ? " · metinle eşleşmiyor" : " · seslendirmeye hazır");
    $("#audio-timing-mode").textContent = audio.timing_mode === "manual"
      ? "Elle düzenlenmiş zamanlama" : "Konuşma aralıklarından tahmini zamanlama";
    const href = safeUrl(audio.url, true);
    if (href) {
      const url = new URL(href);
      url.searchParams.set("v", audio.uploaded_at || audio.filename || "audio");
      if (preview.src !== url.href) {
        preview.src = url.href;
        preview.load();
      }
    } else preview.removeAttribute("src");
    const key = project.id + ":" + JSON.stringify([audio.uploaded_at, audio.script_hash, audio.captions]);
    if (state.audioTimingKey !== key) {
      state.audioTimingKey = key;
      state.audioTimingDirty = false;
      const rows = (audio.captions || []).map((caption, index) => {
        const row = el("tr");
        const text = el("td", "audio-caption-text");
        const listen = el("button", "audio-caption-listen", caption.text);
        listen.type = "button";
        listen.title = "Bu altyazı aralığını dinle";
        listen.setAttribute("aria-label", "Dinle: " + caption.text);
        listen.addEventListener("click", () => {
          const input = $('[data-timing-index="' + index + '"][data-timing-field="start"]');
          preview.currentTime = Math.max(0, Number(input.value) || 0);
          preview.play().catch(() => toast("Sesi dinlemek için oynat düğmesine bas."));
        });
        text.append(listen);
        row.append(text);
        ["start", "end"].forEach((field) => {
          const cell = el("td");
          const input = el("input", "text-input audio-time-input");
          input.type = "number";
          input.min = "0";
          input.max = String(duration);
          input.step = "any";
          input.value = String(caption[field]);
          input.dataset.timingIndex = String(index);
          input.dataset.timingField = field;
          input.setAttribute("aria-label", (index + 1) + ". altyazı " + (field === "start" ? "başlangıç" : "bitiş") + " saniyesi");
          cell.append(input);
          row.append(cell);
        });
        return row;
      });
      $("#audio-timings-body").replaceChildren(...rows);
    }
    $$("#audio-timings-body input").forEach((input) => { input.disabled = locked || stale; });
    $$("#audio-timings-body button").forEach((button) => { button.disabled = locked; });
    if (state.audioTimingDirty) $("#audio-timing-mode").textContent += " · Kaydedilmedi";
    $("#save-audio-timings").disabled = locked || stale || !state.audioTimingDirty;
  }
  async function copyScript() {
    if (!state.selected || activeProject(state.selected) || state.audioBusy) return;
    await busy($("#copy-script"), async () => {
      try {
        const project = await saveCurrent(false);
        let copied = false;
        try {
          await navigator.clipboard.writeText(project.script);
          copied = true;
        } catch {}
        if (!copied) {
          const field = el("textarea", "clipboard-fallback");
          field.value = project.script;
          field.setAttribute("readonly", "");
          document.body.append(field);
          field.select();
          try { copied = document.execCommand("copy"); } catch {}
          field.remove();
        }
        if (!copied) {
          $("#edit-script").focus();
          $("#edit-script").select();
          throw new Error("Metin seçildi. Kopyalamak için ⌘C veya Ctrl+C kullan.");
        }
        toast("Seslendirme metni kopyalandı.");
      } catch (error) { toast(error.message, true); }
    });
    if (state.selected) updateAudio(state.selected);
  }
  async function downloadScript() {
    if (!state.selected || activeProject(state.selected) || state.audioBusy) return;
    await busy($("#download-script"), async () => {
      try {
        const project = await saveCurrent(false);
        const link = el("a");
        link.href = "/api/projects/" + encodeURIComponent(project.id) + "/script";
        link.download = "seslendirme.txt";
        document.body.append(link);
        link.click();
        link.remove();
      } catch (error) { toast(error.message, true); }
    });
    if (state.selected) updateAudio(state.selected);
  }
  async function audioOperation(work) {
    if (!state.selected || activeProject(state.selected) || state.audioBusy) return;
    clearError("#audio-error");
    state.audioBusy = true;
    updatePreview(state.selected);
    try { await work(); }
    catch (error) { showError("#audio-error", error.message); }
    finally {
      state.audioBusy = false;
      if (state.selected) updatePreview(state.selected);
    }
  }
  function receiveAudioProject(project) {
    updateProject(project);
    if (state.selected?.id !== project.id) return;
    state.selected = project;
    state.audioTimingDirty = false;
    state.audioTimingKey = "";
    updatePreview(project);
  }
  async function uploadVoice() {
    const file = $("#voice-file").files[0];
    if (!file) return;
    const maxBytes = state.status?.audio_upload?.max_bytes || 25 * 1024 * 1024;
    if (!/\.(mp3|wav)$/i.test(file.name))
      return showError("#audio-error", "MP3 veya WAV dosyası seç.");
    if (file.size > maxBytes)
      return showError("#audio-error", "Ses dosyası en fazla " + Math.round(maxBytes / 1024 / 1024) + " MB olabilir.");
    await audioOperation(async () => {
      const saved = await saveCurrent(false);
      const form = new FormData();
      form.append("file", file);
      const project = projectFromResponse(await api("/api/projects/" + encodeURIComponent(saved.id) + "/audio", {
        method: "POST", headers: {}, body: form,
      }));
      receiveAudioProject(project);
      if (state.selected?.id === project.id) {
        $("#tts-provider").value = "uploaded";
        $("#voice-file").value = "";
        $("#voice-workflow").open = true;
      }
      toast("Ses dosyası hazır. Videon bu seslendirmeyle oluşturulacak.");
    });
  }
  async function removeAudio() {
    if (!state.selected?.audio || activeProject(state.selected) || state.audioBusy) return;
    const id = state.selected.id;
    const accepted = await askConfirmation("Yüklenen ses kaldırılsın mı?",
      "Ses dosyası bu projeden silinecek. Yeniden kullanmak için orijinal dosyanı sakla. Videoya tekrar ses eklemek istersen dosyayı yeniden yükleyebilirsin.", "Sesi kaldır");
    if (!accepted || state.selected?.id !== id) return;
    await audioOperation(async () => {
      const project = projectFromResponse(await api("/api/projects/" + encodeURIComponent(id) + "/audio", { method: "DELETE" }));
      receiveAudioProject(project);
      if (state.selected?.id === id) $("#tts-provider").value = "local";
      toast("Yüklenen ses kaldırıldı. Yerel ses seçildi.");
    });
  }
  async function saveAudioTimings() {
    if (!state.selected?.audio || audioIsStale(state.selected) || !state.audioTimingDirty) return;
    if ($$("#audio-timings-body input").some((input) => !input.value.trim()))
      return showError("#audio-error", "Her altyazı için başlangıç ve bitiş saniyesini yaz.");
    const captions = state.selected.audio.captions.map((caption, index) => ({
      text: caption.text,
      start: Number($('[data-timing-index="' + index + '"][data-timing-field="start"]').value),
      end: Number($('[data-timing-index="' + index + '"][data-timing-field="end"]').value),
    }));
    let previousEnd = 0;
    for (const caption of captions) {
      if (!Number.isFinite(caption.start) || !Number.isFinite(caption.end) ||
          caption.start < previousEnd || caption.end <= caption.start || caption.end > Number(state.selected.audio.duration))
        return showError("#audio-error", "Zamanlar sıralı olmalı; her başlangıç önceki bitişten sonra, bitiş de sesin süresi içinde olmalı.");
      previousEnd = caption.end;
    }
    await audioOperation(async () => {
      const saved = await saveCurrent(false);
      const project = projectFromResponse(await api("/api/projects/" + encodeURIComponent(saved.id) + "/audio/timings", {
        method: "PATCH", body: JSON.stringify({ captions }),
      }));
      receiveAudioProject(project);
      toast("Altyazı zamanları kaydedildi. Videoyu yeniden oluşturarak kontrol edebilirsin.");
    });
  }
  function updatePreview(project) {
    const video = $("#preview-video");
    const hasVideo = !!safeUrl(project.video_url, true);
    video.hidden = !hasVideo;
    $("#preview-placeholder").hidden = hasVideo;
    $(".phone-top").hidden = hasVideo;
    $(".phone-bottom").hidden = hasVideo;
    if (hasVideo) {
      const url = safeUrl(project.video_url, true);
      if (video.src !== url) {
        video.src = url;
        video.load();
      }
    } else {
      video.pause();
      video.removeAttribute("src");
    }
    $("#video-actions").hidden = !hasVideo;
    if (hasVideo) $("#download-video").href = safeUrl(project.video_url, true);
    else $("#download-video").removeAttribute("href");
    const subtitle = safeUrl(project.subtitle_url, true);
    $("#download-subtitles").hidden = !subtitle;
    if (subtitle) $("#download-subtitles").href = subtitle;
    const running = activeProject(project);
    const locked = running || state.audioBusy;
    $$(
      "#editor-form input, #editor-form textarea, #editor-form select, #editor-form button, .render-settings select, .theme-picker input",
    ).forEach((control) => {
      control.disabled = locked;
    });
    const published = !!(project.youtube_id || project.youtube_url);
    $("#translate-project").disabled = locked || published;
    $("#editor-translation-notice").hidden = !published;
    $("#editor-translation-notice").textContent = published
      ? "Yayımlanmış videoyu korumak için Videolarım'da projeyi çoğalt, ardından kopyayı Türkçeye çevir."
      : "";
    $("#render-project").disabled = locked;
    $("#render-progress").hidden = !running;
    $("#render-progress-text").textContent =
      project.status === "processing_audio"
        ? "Ses dosyası işleniyor…"
        : project.status === "queued"
        ? "Üretim sırasında bekliyor…"
        : project.status === "uploading"
          ? "YouTube’a yükleniyor…"
          : project.status === "translating" || state.translatingProjectIds.has(project.id)
            ? "Metinler Türkçeye çevriliyor…"
            : "Video hazırlanıyor…";
    const progress = Math.max(0, Math.min(100, Number(project.progress) || 0));
    const knownProgress =
      project.status === "rendering" &&
      Number.isFinite(Number(project.progress));
    $("#render-progress-number").textContent = knownProgress
      ? progress + "%"
      : "";
    $("#render-progress-bar").style.width = knownProgress
      ? progress + "%"
      : "0%";
    $("#render-progress").classList.toggle(
      "indeterminate",
      running && !knownProgress,
    );
    $("#editor-status").textContent =
      state.translatingProjectIds.has(project.id) ? statusLabels.translating :
        statusLabels[project.status] || project.status || "Taslak";
    const designSummary = $("#video-design-summary");
    const design = project.design || project.render_options?.video_design;
    designSummary.hidden = !hasVideo || !design;
    designSummary.textContent = (design === "classic" ? "Klasik tasarım" : design === "host"
      ? "Anlatıcılı" + (project.render_options?.host_name ? " · " + project.render_options.host_name : "") : "Animasyonlu sahneler") +
      (Number.isFinite(Number(project.scene_count)) && Number(project.scene_count) > 0
        ? " · " + Number(project.scene_count) + " sahne" : "") +
      (Number(project.duration) > 0 ? " · " + Number(project.duration).toLocaleString("tr-TR", { maximumFractionDigits: 1 }) + " sn" : "") +
      (Array.isArray(project.emphasis) && project.emphasis.length
        ? " · Vurgular: " + project.emphasis.map((item) => item.word).join(", ") : "") +
      (project.subtitle_timing === "audio_estimated" ? " · Tahmini altyazı zamanlaması" :
        ["manual", "audio_manual"].includes(project.subtitle_timing) ? " · Elle düzenlenmiş altyazı zamanlaması" : "");
    $("#upload-project").disabled = running || !!project.youtube_url;
    if (project.youtube_url) {
      $("#upload-project").replaceChildren(
        icon("check"),
        document.createTextNode("YouTube’a yüklendi"),
      );
    } else {
      $("#upload-project").replaceChildren(
        icon("youtube"),
        document.createTextNode("YouTube'a yükle"),
      );
    }
    let youtubeLink = $("#youtube-video-link");
    const youtubeUrl = safeUrl(project.youtube_url);
    if (youtubeUrl) {
      if (!youtubeLink) {
        youtubeLink = el("a", "text-button");
        youtubeLink.id = "youtube-video-link";
        youtubeLink.target = "_blank";
        youtubeLink.rel = "noopener noreferrer";
        $("#video-actions").append(youtubeLink);
      }
      youtubeLink.href = youtubeUrl;
      youtubeLink.textContent = "YouTube’da görüntüle";
      youtubeLink.append(icon("arrow-up-right"));
      youtubeLink.hidden = false;
    } else if (youtubeLink) youtubeLink.hidden = true;
    if (project.error) showStudioError(project.error);
    else showStudioError("");
    updateAudio(project);
  }
  function showStudioError(message) {
    let target = $("#studio-error");
    if (!target) {
      target = el("div", "inline-warning");
      target.id = "studio-error";
      $("#studio-editor").before(target);
    }
    target.textContent = message;
    target.hidden = !message;
  }
  function fillEditor(project) {
    $("#studio-empty").hidden = true;
    $("#studio-editor").hidden = false;
    $("#edit-title").value = project.title || "";
    $("#edit-script").value = project.script || "";
    $("#edit-description").value = project.description || "";
    $("#edit-tags").value = Array.isArray(project.tags)
      ? project.tags.join(", ")
      : project.tags || "";
    const source = $("#editor-source");
    source.replaceChildren();
    if (project.source_url) {
      const line = el("span");
      line.append(icon("link"), document.createTextNode("Haber kaynağı"));
      source.append(
        line,
        sourceLink(project.source_url, project.source || project.source_url),
      );
    }
    if (project.editorial_note) {
      const note = el("p", "editorial-note", project.editorial_note);
      source.append(note);
    }
    $("#editor-language").textContent = project.language === "tr" ? "Türkçe" : "Kaynak dili";
    const original = $("#editor-original-content");
    original.replaceChildren();
    const translation = project.translation || {};
    [
      ["original_title", "Başlık"], ["original_summary", "Haber özeti"],
      ["original_script", "Seslendirme metni"], ["original_description", "Açıklama"], ["original_tags", "Etiketler"],
    ].forEach(([key, label]) => {
      const value = translation[key];
      if (Array.isArray(value) ? value.length : typeof value === "string" && value) {
        original.append(el("strong", "", label), el("p", "", Array.isArray(value) ? value.join(", ") : value));
      }
    });
    $("#editor-original").hidden = !original.childElementCount;
    $("#video-design").value = project.render_options?.video_design || project.design || "host";
    $("#host-look").value = project.render_options?.host_look || "vega";
    $("#render-sfx").checked = project.render_options?.sfx !== false;
    $("#render-palette").value = project.render_options?.palette || "auto";
    const savedStyle = project.render_options?.style || "capsule";
    const styleInput = $(`input[name="render-style"][value="${savedStyle}"]`);
    if (styleInput) styleInput.checked = true;
    $("#host-name").value = project.render_options?.host_name || "";
    $("#host-fields").hidden = $("#video-design").value !== "host";
    const savedOptions = project.render_options;
    const savedProvider = savedOptions?.tts_provider;
    let voiceProvider = savedOptions ? "local" : project.audio ? "uploaded" : "local";
    if (savedOptions?.speech === false) voiceProvider = "none";
    else if (savedProvider === "local" || savedProvider === "uploaded" && project.audio ||
        savedProvider === "elevenlabs" && !$('#tts-provider option[value="elevenlabs"]').disabled)
      voiceProvider = savedProvider;
    $("#tts-provider").value = voiceProvider;
    $("#voice-file").value = "";
    state.audioTimingDirty = false;
    state.audioTimingKey = "";
    $("#voice-workflow").open = !!project.audio;
    clearError("#audio-error");
    clearError("#editor-translation-error");
    state.dirty = false;
    markDirty();
    countWords();
    updatePreview(project);
  }
  async function openProject(id) {
    if (!(await canDiscard())) return;
    try {
      const project = projectFromResponse(
        await api("/api/projects/" + encodeURIComponent(id)),
      );
      state.selected = project;
      updateProject(project);
      fillEditor(project);
      navigate("studio", true, true);
      try {
        localStorage.setItem("hype-selected-project", id);
      } catch {}
      if (activeProject(project))
        startPolling();
    } catch (error) {
      toast(error.message, true);
    }
  }
  async function saveCurrent(showToast = true) {
    if (!state.selected) return null;
    if (activeProject(state.selected))
      throw new Error(
        "Bu proje işleniyor. Düzenlemek için işlemin tamamlanmasını bekle.",
      );
    if (!state.dirty) {
      if (showToast) toast("Tüm değişikliklerin kaydedilmiş.");
      return state.selected;
    }
    const payload = {
      title: $("#edit-title").value.trim(),
      script: $("#edit-script").value.trim(),
      description: $("#edit-description").value,
      tags: $("#edit-tags")
        .value.split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    };
    if (!payload.title || !payload.script)
      throw new Error("Video başlığı ve seslendirme metni boş bırakılamaz.");
    const project = projectFromResponse(
      await api("/api/projects/" + encodeURIComponent(state.selected.id), {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    );
    state.selected = project;
    state.dirty = false;
    markDirty();
    updateProject(project);
    updatePreview(project);
    if (showToast) toast("Değişikliklerin kaydedildi.");
    return project;
  }
  async function saveProject(event) {
    event.preventDefault();
    await busy($("#save-project"), async () => {
      try {
        await saveCurrent();
      } catch (error) {
        toast(error.message, true);
      }
    });
  }
  async function translateCurrentProject() {
    if (!state.selected || activeProject(state.selected)) return;
    const accepted = await askConfirmation(
      "Video metinleri Türkçeye çevrilsin mi?",
      (state.dirty ? "Düzenlemelerin önce kaydedilecek. " : "") +
        "Başlık, seslendirme, açıklama ve etiketler Türkçe çeviriyle değiştirilecek. Özgün metinler karşılaştırma için saklanır. Hazır video varsa yeni metinlerle yeniden oluşturman gerekir.",
      state.dirty ? "Kaydet ve Türkçeye çevir" : "Türkçeye çevir",
    );
    if (!accepted) return;
    if (!state.selected || activeProject(state.selected)) return;
    clearError("#editor-translation-error");
    let original;
    try {
      original = await saveCurrent(false);
    } catch (error) {
      showError("#editor-translation-error", error.message);
      return;
    }
    const id = original.id;
    const provider = $("#editor-translation-provider").value;
    state.translatingProjectIds.add(id);
    updatePreview(original);
    renderProjects();
    startPolling();
    try {
      const project = projectFromResponse(await api("/api/projects/" + encodeURIComponent(id) + "/translate", {
        method: "POST", body: JSON.stringify({ provider }),
      }));
      state.translatingProjectIds.delete(id);
      updateProject(project);
      if (state.selected?.id === id) {
        state.selected = project;
        fillEditor(project);
      }
      toast("Metinler Türkçeye çevrildi. Türkçe ses ve altyazılar için videoyu yeniden oluştur.");
      loadActivity().catch(() => {});
    } catch (error) {
      let restored = original;
      try { restored = projectFromResponse(await api("/api/projects/" + encodeURIComponent(id))); } catch {}
      state.translatingProjectIds.delete(id);
      updateProject(restored);
      if (state.selected?.id === id) {
        state.selected = restored;
        fillEditor(restored);
        showError("#editor-translation-error", error.message);
      } else toast(error.message, true);
    } finally {
      state.translatingProjectIds.delete(id);
      if (state.selected?.id === id) updatePreview(state.selected);
    }
  }
  async function renderProject() {
    if (!state.selected) return;
    if (state.status && !state.status.ffmpeg)
      return toast(
        "Video üretimi için FFmpeg kurulumu gerekli. Kurulum rehberini kontrol et.",
        true,
      );
    await busy($("#render-project"), async () => {
      try {
        const project = await saveCurrent(false);
        const provider = $("#tts-provider").value;
        if (provider === "uploaded" && (!project.audio || project.audio.valid === false))
          throw new Error("Metin değişti. Aynı metinden üretilen sesi yeniden yükle.");
        if (provider === "uploaded" && state.audioTimingDirty)
          throw new Error("Videoyu oluşturmadan önce altyazı zamanlarını kaydet.");
        const options = {
          voice: "tr",
          style: $('input[name="render-style"]:checked').value,
          video_design: $("#video-design").value,
          ...($("#video-design").value === "host"
            ? { host_look: $("#host-look").value, host_name: $("#host-name").value.trim(),
                sfx: $("#render-sfx").checked } : {}),
          palette: $("#render-palette").value,
          speech: provider !== "none",
          tts_provider: ["elevenlabs", "uploaded"].includes(provider) ? provider : "local",
        };
        const result = projectFromResponse(
          await api(
            "/api/projects/" + encodeURIComponent(project.id) + "/render",
            { method: "POST", body: JSON.stringify(options) },
          ),
        );
        if (result.id) {
          state.selected = result;
          updateProject(result);
          updatePreview(result);
        } else {
          state.selected.status = "rendering";
          updatePreview(state.selected);
        }
        toast("Video üretimi başladı. Bu ekranı açık tutabilirsin.");
        startPolling();
      } catch (error) {
        toast(error.message, true);
        showStudioError(error.message);
      }
    });
    if (
      state.selected &&
      ["rendering", "queued"].includes(state.selected.status)
    )
      $("#render-project").disabled = true;
  }
  function startPolling() {
    clearTimeout(state.poll);
    state.poll = setTimeout(pollProject, 2200);
  }

  async function pollProject() {
    if (state.pollInFlight || document.hidden) {
      startPolling();
      return;
    }
    if (!state.projects.some(activeProject)) return;
    state.pollInFlight = true;
    try {
      await loadProjects(true);
      await Promise.allSettled([loadActivity(), loadStatus()]);
    } catch (error) {
      showError(
        "#system-message",
        "İşlem durumu yenilenemedi. Yeniden bağlanılıyor: " + error.message,
      );
    } finally {
      state.pollInFlight = false;
      if (state.projects.some(activeProject)) startPolling();
    }
  }

  async function showUpload() {
    if (!state.selected?.video_url || activeProject(state.selected)) return;
    if (state.dirty) {
      toast(
        "Yüklemeden önce değişikliklerini kaydet ve videonu tekrar kontrol et.",
        true,
      );
      return;
    }
    $("#upload-form").reset();
    clearError("#upload-error");
    $("#upload-retry-row").hidden = !state.selected.upload_uncertain;
    $("#upload-retry-confirm").required = !!state.selected.upload_uncertain;
    $("#upload-summary").textContent = state.selected.title;
    $("#upload-dialog").showModal();
  }
  async function uploadProject(event) {
    event.preventDefault();
    if (!$("#upload-confirm").checked || !state.selected) return;
    clearError("#upload-error");
    await busy($("#confirm-upload"), async () => {
      try {
        const result = await api(
          "/api/projects/" + encodeURIComponent(state.selected.id) + "/upload",
          {
            method: "POST",
            body: JSON.stringify({
              confirm: true,
              privacy: $("#upload-privacy").value,
              ...($("#upload-retry-confirm").checked
                ? { retry_confirmed: true }
                : {}),
            }),
          },
        );
        const acceptedProject = projectFromResponse(result);
        if (acceptedProject.error) throw new Error(acceptedProject.error);
        $("#upload-dialog").close();
        toast(
          acceptedProject.youtube_url
            ? "Videon YouTube’a yüklendi."
            : "YouTube yüklemesi başladı. Sonucu burada takip edebilirsin.",
        );
        if (result.project || result.id) {
          state.selected = projectFromResponse(result);
          updateProject(state.selected);
          updatePreview(state.selected);
        } else {
          await openProject(state.selected.id);
        }
        if (state.selected.status === "uploading") startPolling();
        loadActivity().catch(() => {});
      } catch (error) {
        if (error.details?.requires_retry_confirmation) {
          $("#upload-retry-row").hidden = false;
          $("#upload-retry-confirm").required = true;
          state.selected.upload_uncertain = true;
        }
        showError("#upload-error", error.message);
      }
    });
  }
  async function connectYoutube() {
    await busy($("#connect-youtube"), async () => {
      try {
        const result = await api("/api/youtube/connect");
        const url = safeUrl(result.url);
        if (!url)
          throw new Error(
            "Yetkilendirme bağlantısı oluşturulamadı. YouTube yapılandırmasını kontrol et.",
          );
        window.open(url, "_blank", "noopener,noreferrer");
        let authLink = $("#youtube-auth-link");
        if (!authLink) {
          authLink = el("a", "text-button");
          authLink.id = "youtube-auth-link";
          authLink.target = "_blank";
          authLink.rel = "noopener noreferrer";
          $("#connect-youtube").after(authLink);
        }
        authLink.href = url;
        authLink.textContent = "Yetkilendirme açılmadıysa buraya tıkla";
        authLink.append(icon("arrow-up-right"));
        toast(
          "YouTube yetkilendirmesi tarayıcında açıldı. Tamamladıktan sonra stüdyoyu yenile.",
        );
      } catch (error) {
        toast(error.message, true);
      }
    });
  }
  async function refreshAll() {
    await busy($("#refresh-all"), async () => {
      const results = await Promise.allSettled([
        loadStatus(),
        loadNews(),
        loadProjects(),
        loadActivity(),
      ]);
      const failure = results.find((result) => result.status === "rejected");
      toast(
        failure
          ? "Bazı stüdyo bilgileri alınamadı: " + failure.reason.message
          : "Stüdyon güncellendi.",
        !!failure,
      );
    });
  }
  function bindEvents() {
    $("#confirm-accept").addEventListener("click", () =>
      resolveConfirmation(true),
    );
    $("#confirm-cancel").addEventListener("click", () =>
      resolveConfirmation(false),
    );
    $("#confirm-close").addEventListener("click", () =>
      resolveConfirmation(false),
    );
    $("#confirm-dialog").addEventListener("cancel", (event) => {
      event.preventDefault();
      resolveConfirmation(false);
    });
    $("#confirm-dialog").addEventListener("close", () => {
      if (state.confirmResolver) resolveConfirmation(false);
    });
    $("#project-search").addEventListener("input", (event) => {
      state.projectSearch = event.target.value;
      renderProjects();
    });
    $("#project-filter").addEventListener("change", (event) => {
      state.projectFilter = event.target.value;
      renderProjects();
    });
    $("#preview-video").addEventListener("loadedmetadata", (event) => {
      const video = event.target;
      if (video.currentTime === 0 && video.duration > 0.05)
        video.currentTime = 0.05;
    });
    $$("[data-view]").forEach((button) =>
      button.addEventListener("click", () => navigate(button.dataset.view)),
    );
    $$('[data-action="new-project"]').forEach((button) =>
      button.addEventListener("click", () => showNewProject()),
    );
    $$("[data-close-dialog]").forEach((button) =>
      button.addEventListener("click", () => {
        const dialog = button.closest("dialog");
        if (dialog.getAttribute("aria-busy") !== "true") dialog.close();
      }),
    );
    $$("dialog").forEach((dialog) => {
      dialog.addEventListener("cancel", (event) => {
        if (dialog.getAttribute("aria-busy") === "true") event.preventDefault();
      });
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog && dialog.getAttribute("aria-busy") !== "true") {
          const rect = dialog.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            dialog.close();
        }
      });
    });
    $("#refresh-all").addEventListener("click", refreshAll);
    $("#refresh-news").addEventListener("click", () =>
      busy($("#refresh-news"), async () => {
        try {
          await loadNews(true);
          loadActivity().catch(() => {});
        } catch (error) {
          state.newsError = error.message;
          renderNews();
          renderDashboardNews();
          toast(error.message, true);
        }
      }),
    );
    $("#new-project-form").addEventListener("submit", createProject);
    $("#translate-new-article").addEventListener("click", translateNewArticle);
    $("#translate-article").addEventListener("click", translateArticle);
    $("#translation-form").addEventListener("submit", createTranslatedProject);
    $("#translate-project").addEventListener("click", translateCurrentProject);
    $$(".translation-provider").forEach((select) => select.addEventListener("change", renderTranslationHelp));
    $("#editor-form").addEventListener("submit", saveProject);
    $("#editor-form").addEventListener("input", (event) => {
      if (!["edit-title", "edit-script", "edit-description", "edit-tags"].includes(event.target.id)) return;
      state.dirty = true;
      markDirty();
      countWords();
      if (state.selected) updateAudio(state.selected);
    });
    $("#copy-script").addEventListener("click", copyScript);
    $("#download-script").addEventListener("click", downloadScript);
    $("#voice-file").addEventListener("change", () => {
      clearError("#audio-error");
      if (state.selected) updateAudio(state.selected);
    });
    $("#upload-voice").addEventListener("click", uploadVoice);
    $("#remove-audio").addEventListener("click", removeAudio);
    $("#video-design").addEventListener("change", () => {
      $("#host-fields").hidden = $("#video-design").value !== "host";
    });
    $("#tts-provider").addEventListener("change", () => {
      if (state.selected) updateAudio(state.selected);
    });
    $("#audio-timings-body").addEventListener("input", () => {
      state.audioTimingDirty = true;
      clearError("#audio-error");
      if (state.selected) updateAudio(state.selected);
    });
    $("#save-audio-timings").addEventListener("click", saveAudioTimings);
    $("#render-project").addEventListener("click", renderProject);
    $("#upload-project").addEventListener("click", showUpload);
    $("#upload-form").addEventListener("submit", uploadProject);
    $("#connect-youtube").addEventListener("click", connectYoutube);
    $("#news-search").addEventListener("input", (event) => {
      state.search = event.target.value;
      renderNews();
    });
    $$("#news-filters button").forEach((button) =>
      button.addEventListener("click", () => {
        state.filter = button.dataset.filter;
        $$("#news-filters button").forEach((item) =>
          item.classList.toggle("active", item === button),
        );
        renderNews();
      }),
    );
    window.addEventListener("hashchange", () =>
      navigate(location.hash.slice(1), false),
    );
    const refreshOnFocus = () => {
      if (document.hidden) return;
      Promise.allSettled([
        loadStatus(),
        loadProjects(true),
        loadNews(),
        loadActivity(),
      ]);
    };
    window.addEventListener("focus", refreshOnFocus);
    document.addEventListener("visibilitychange", refreshOnFocus);
    window.addEventListener("beforeunload", (event) => {
      if (state.dirty || state.audioTimingDirty || state.audioBusy) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
  }
  async function loadLogos() {
    const data = await api("/api/logos");
    const palette = $("#render-palette");
    const current = palette.value;
    palette.replaceChildren(el("option", "", "Otomatik · habere göre"));
    palette.firstChild.value = "auto";
    data.palettes.forEach((item) => {
      const option = el("option", "", item.label);
      option.value = item.id;
      palette.append(option);
    });
    palette.value = [...palette.options].some((option) => option.value === current) ? current : "auto";
    const brands = $("#logo-brand");
    const selected = brands.value;
    brands.replaceChildren(...data.brands.map((brand) => {
      const option = el("option", "", brand.name + (brand.has_logo ? " · logo yüklü" : ""));
      option.value = brand.slug;
      return option;
    }));
    if (selected) brands.value = selected;
    const uploaded = data.brands.filter((brand) => brand.has_logo).map((brand) => brand.name);
    $("#logo-status").textContent = uploaded.length ? "Yüklü logolar: " + uploaded.join(", ") : "Henüz logo yüklenmedi.";
  }
  async function uploadLogo() {
    const file = $("#logo-file").files[0];
    if (!file) return toast("Önce bir logo dosyası seç.", true);
    if (file.size > 3 * 1024 * 1024) return toast("Logo en fazla 3 MB olabilir.", true);
    await busy($("#upload-logo"), async () => {
      try {
        const form = new FormData();
        form.append("file", file);
        await api("/api/logos/" + encodeURIComponent($("#logo-brand").value), { method: "POST", headers: {}, body: form });
        $("#logo-file").value = "";
        await loadLogos();
        toast("Logo yüklendi.");
      } catch (error) {
        toast(error.message, true);
      }
    });
  }
  async function init() {
    hydrateIcons();
    $("#upload-logo").addEventListener("click", uploadLogo);
    loadLogos().catch(() => {});
    bindEvents();
    navigate(location.hash.slice(1) || "dashboard", false);
    const results = await Promise.allSettled([
      loadStatus(),
      loadNews(),
      loadProjects(),
      loadActivity(),
    ]);
    results.forEach((result, index) => {
      if (result.status === "rejected") {
        if (index === 1) {
          state.newsError = result.reason.message;
          renderNews();
          renderDashboardNews();
        } else if (index === 2) {
          $("#projects-grid").replaceChildren(
            emptyState(
              "Projeler yüklenemedi.",
              result.reason.message,
              "folder",
            ),
          );
        } else if (index === 0) {
          showError(
            "#system-message",
            "Stüdyoya bağlanılamadı: " + result.reason.message,
          );
          $("#engine-state").textContent = "Bağlantı bekleniyor";
        }
      }
    });
    let selectedId;
    try {
      selectedId = localStorage.getItem("hype-selected-project");
    } catch {}
    if (
      selectedId &&
      state.projects.some((project) => project.id === selectedId)
    ) {
      state.selected = state.projects.find(
        (project) => project.id === selectedId,
      );
      fillEditor(state.selected);
      if (activeProject(state.selected))
        startPolling();
    }
  }
  init();
})();
