(function () {
  let panelOpen = false;

  function createButton() {
    if (document.getElementById("mydownloader-btn")) return;

    const btn = document.createElement("button");
    btn.id = "mydownloader-btn";
    btn.textContent = "⬇ Download with NDA";
    btn.addEventListener("click", onButtonClick);
    document.body.appendChild(btn);
  }

  function getPageTitle() {
    // Try YouTube's title element first
    const ytTitle = document.querySelector("h1.ytd-watch-metadata yt-formatted-string") ||
                    document.querySelector("h1.title");
    if (ytTitle && ytTitle.textContent.trim()) {
      return ytTitle.textContent.trim();
    }

    // Try Instagram / X — fall back to document.title, cleaned up
    let title = document.title || "video";
    title = title.replace(" - YouTube", "")
                  .replace(" • Instagram", "")
                  .replace(" / X", "")
                  .replace(" on X", "")
                  .trim();
    return title || "video";
  }

  function onButtonClick() {
    if (panelOpen) return;
    showPanel("Loading available qualities...", []);

    chrome.runtime.sendMessage(
      { action: "extractFormats", url: window.location.href },
      (response) => {
        if (!response || !response.ok) {
          showPanel("Error: could not reach desktop app. Is it running?", []);
          return;
        }
        const data = response.data;
        if (data.status !== "ok") {
          showPanel(
            `Couldn't extract this link. It may be private, login-required, or unsupported.\n\nDetails: ${data.error || "unknown error"}`,
            []
          );
          return;
        }
        renderOptions(data.title || getPageTitle(), data.video_options, data.audio_option);
      }
    );
  }

  function renderOptions(title, videoOptions, audioOption) {
    const panel = document.getElementById("mydownloader-panel");
    if (!panel) return;

    panel.innerHTML = "";

    const titleEl = document.createElement("div");
    titleEl.className = "mydownloader-title";
    titleEl.textContent = title;
    panel.appendChild(titleEl);

    const list = document.createElement("div");
    list.className = "mydownloader-options";

    if (!videoOptions || videoOptions.length === 0) {
      const empty = document.createElement("div");
      empty.className = "mydownloader-message";
      empty.textContent = "No video qualities found for this link.";
      list.appendChild(empty);
    } else {
      videoOptions.forEach((opt) => {
        const item = document.createElement("button");
        item.className = "mydownloader-option";
        item.textContent = opt.label;
        item.addEventListener("click", () => startDownload(title, opt.format_selector, false));
        list.appendChild(item);
      });
    }

    if (audioOption) {
      const audioItem = document.createElement("button");
      audioItem.className = "mydownloader-option mydownloader-audio";
      audioItem.textContent = audioOption.label;
      audioItem.addEventListener("click", () => startDownload(title, audioOption.format_selector, true));
      list.appendChild(audioItem);
    }

    panel.appendChild(list);

    const closeBtn = document.createElement("button");
    closeBtn.className = "mydownloader-close";
    closeBtn.textContent = "Close";
    closeBtn.addEventListener("click", closePanel);
    panel.appendChild(closeBtn);
  }

  function startDownload(title, formatSelector, isAudioOnly) {
    showPanel("Starting download — check your desktop app...", []);

    chrome.runtime.sendMessage(
      {
        action: "startYoutubeDownload",
        url: window.location.href,
        format_selector: formatSelector,
        is_audio_only: isAudioOnly,
        title: title
      },
      (response) => {
        if (!response || !response.ok || response.data.status !== "completed") {
          const errMsg = response && response.data ? response.data.error : "unknown error";
          showPanel(`Error: ${errMsg || "download failed"}`, []);
          return;
        }
        showPanel(`Done: saved as ${response.data.filename}`, []);
        setTimeout(closePanel, 3000);
      }
    );
  }

  function showPanel(message, options) {
    closePanel();
    panelOpen = true;

    const overlay = document.createElement("div");
    overlay.id = "mydownloader-overlay";
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closePanel();
    });

    const panel = document.createElement("div");
    panel.id = "mydownloader-panel";

    const msgEl = document.createElement("div");
    msgEl.className = "mydownloader-message";
    msgEl.textContent = message;
    panel.appendChild(msgEl);

    overlay.appendChild(panel);
    document.body.appendChild(overlay);
  }

  function closePanel() {
    const existing = document.getElementById("mydownloader-overlay");
    if (existing) existing.remove();
    panelOpen = false;
  }

  createButton();

  // YouTube, Instagram, and X are all single-page apps — re-inject button on navigation
  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      setTimeout(createButton, 1000);
    }
  }).observe(document.body, { childList: true, subtree: true });
})();