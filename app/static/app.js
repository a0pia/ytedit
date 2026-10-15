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
    if (!response.ok)
      throw new Error(
        data.error ||
          data.message ||
          "İşlem tamamlanamadı. Lütfen yeniden dene.",
      );
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

  function navigate(view, updateHash = true) {
    if (!labels[view]) view = "dashboard";
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
    $("#page-content").scrollIntoView({ block: "start", behavior: "instant" });
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
    showNewProject({
      title: item.title,
      summary: item.summary || "",
      url: item.url,
      source: item.source,
      news_id: item.id,
    });
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
      button.title = "Bu haberden video oluştur";
      button.setAttribute(
        "aria-label",
        item.title + " haberinden video oluştur",
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
      const button = el("button", "button button-outline", "Videoya dönüştür");
      button.append(icon("plus"));
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
    if (!state.projects.length) {
      grid.append(
        emptyState(
          "Koleksiyonun ilk hikâyesine hazır.",
          "Bir haberden başla veya kendi fikrini bir kısa videoya dönüştür.",
          "folder",
          { label: "İlk videomu oluştur", run: () => showNewProject() },
        ),
      );
      return;
    }
    state.projects.forEach((project) => {
      const card = el("button", "project-card");
      card.type = "button";
      card.setAttribute("aria-label", project.title + " projesini aç");
      const cover = el("div", "project-cover");
      const top = el("div", "project-cover-top", "HYPE ORIGINALS");
      top.append(icon("sparkles"));
      cover.append(
        top,
        el("span", "project-cover-star", "✳"),
        el("h3", "", project.title),
      );
      const body = el("div", "project-card-body");
      const meta = el("div", "project-card-meta");
      meta.append(
        el(
          "span",
          "project-status",
          statusLabels[project.status] || project.status || "Taslak",
        ),
        el("time", "", prettyDate(project.created)),
        icon("arrow-up-right"),
      );
      body.append(el("h3", "", project.title), meta);
      card.append(cover, body);
      card.addEventListener("click", () => openProject(project.id));
      grid.append(card);
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
      ? "ElevenLabs · yapılandırılmamış"
      : "ElevenLabs · kota/ücret olabilir";
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
  async function loadProjects() {
    const data = await api("/api/projects");
    state.projects = data.items || [];
    renderStats();
    renderProjects();
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

  function showNewProject(values = {}) {
    const dialog = $("#new-project-dialog");
    $("#new-project-form").reset();
    $("#new-title").value = values.title || "";
    $("#new-summary").value = values.summary || "";
    $("#new-url").value = values.url || "";
    dialog._draftSource = values;
    clearError("#new-project-error");
    dialog.showModal();
    setTimeout(() => $("#new-title").focus(), 50);
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
    const running = ["rendering", "queued"].includes(project.status);
    $("#render-project").disabled = running;
    $("#render-progress").hidden = !running;
    $("#render-progress-text").textContent = running
      ? "Video hazırlanıyor…"
      : "Video hazır";
    const progress = Math.max(0, Math.min(100, Number(project.progress) || 0));
    $("#render-progress-number").textContent = progress + "%";
    $("#render-progress-bar").style.width = Math.max(3, progress) + "%";
    $("#editor-status").textContent =
      statusLabels[project.status] || project.status || "Taslak";
    $("#upload-project").disabled =
      project.status === "uploading" || !!project.youtube_url;
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
    state.dirty = false;
    countWords();
    updatePreview(project);
  }
  async function openProject(id) {
    try {
      const project = projectFromResponse(
        await api("/api/projects/" + encodeURIComponent(id)),
      );
      state.selected = project;
      updateProject(project);
      fillEditor(project);
      navigate("studio");
      try {
        localStorage.setItem("hype-selected-project", id);
      } catch {}
      if (["rendering", "queued", "uploading"].includes(project.status))
        startPolling();
    } catch (error) {
      toast(error.message, true);
    }
  }
  async function saveCurrent(showToast = true) {
    if (!state.selected) return null;
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
        const options = {
          voice: "tr",
          style: $('input[name="render-style"]:checked').value,
          speech: provider !== "none",
          tts_provider: provider === "elevenlabs" ? "elevenlabs" : "local",
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
    state.poll = setTimeout(pollProject, 1500);
  }
  async function pollProject() {
    if (!state.selected) return;
    try {
      const project = projectFromResponse(
        await api("/api/projects/" + encodeURIComponent(state.selected.id)),
      );
      const previousStatus = state.selected.status;
      state.selected = project;
      updateProject(project);
      updatePreview(project);
      if (["rendering", "queued", "uploading"].includes(project.status))
        startPolling();
      else {
        loadActivity().catch(() => {});
        if (previousStatus === "uploading")
          toast(
            project.youtube_url && !project.error
              ? "Videon YouTube’a yüklendi."
              : project.error ||
                  "YouTube yüklemesi doğrulanamadı; kanalını kontrol et.",
            !!project.error || !project.youtube_url,
          );
        else if (project.status === "ready")
          toast("Videon hazır. İzle, kontrol et ve istersen paylaş.");
        if (project.status === "error")
          toast(project.error || "Video üretimi tamamlanamadı.", true);
      }
    } catch (error) {
      showStudioError(
        "İşlem durumu alınamadı: " +
          error.message +
          " Bağlantı yenilendiğinde projeyi tekrar aç.",
      );
      $("#render-project").disabled = false;
    }
  }
  function showUpload() {
    if (!state.selected?.video_url) return;
    $("#upload-form").reset();
    clearError("#upload-error");
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
            }),
          },
        );
        $("#upload-dialog").close();
        toast("YouTube yüklemesi başladı. Sonucu burada takip edebilirsin.");
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
      button.addEventListener("click", () => button.closest("dialog").close()),
    );
    $$("dialog").forEach((dialog) =>
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
          const rect = dialog.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            dialog.close();
        }
      }),
    );
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
    $("#editor-form").addEventListener("submit", saveProject);
    $("#editor-form").addEventListener("input", () => {
      state.dirty = true;
      countWords();
    });
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
    window.addEventListener("beforeunload", (event) => {
      if (state.dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
  }
  async function init() {
    hydrateIcons();
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
      if (["rendering", "queued", "uploading"].includes(state.selected.status))
        startPolling();
    }
  }
  init();
})();
