const statusEl = document.getElementById("status");
const optionsEl = document.getElementById("options");
const enableCookiesBtn = document.getElementById("enable-cookies-btn");

let currentUrl = "";
let currentTitle = "";

function setStatus(text) {
  statusEl.textContent = text;
}

async function refreshCookieButtonLabel() {
  const hasPermission = await chrome.permissions.contains({
    permissions: ["cookies"],
    origins: ["<all_urls>"]
  });
  enableCookiesBtn.textContent = hasPermission
    ? "✓ High-quality downloads enabled"
    : "Enable high-quality downloads (use my login)";
  enableCookiesBtn.disabled = hasPermission;
}

enableCookiesBtn.addEventListener("click", () => {
  // This click IS the user gesture Chrome requires — request must be called
  // synchronously inside this handler, no awaits before it.
  chrome.permissions.request(
    { permissions: ["cookies"], origins: ["<all_urls>"] },
    (granted) => {
      if (chrome.runtime.lastError) {
        console.warn("Permission request error:", chrome.runtime.lastError.message);
      }
      refreshCookieButtonLabel();
    }
  );
});

function renderOptions(data) {
  optionsEl.innerHTML = "";
  currentTitle = data.title || currentTitle || "video";

  if (!data.video_options || data.video_options.length === 0) {
    setStatus("No downloadable video found on this page.");
    return;
  }

  setStatus(data.title || "Choose a quality:");

  data.video_options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.className = "option";
    btn.textContent = opt.label;
    btn.addEventListener("click", () => startDownload(opt.format_selector, false));
    optionsEl.appendChild(btn);
  });

  if (data.audio_option) {
    const audioBtn = document.createElement("button");
    audioBtn.className = "option audio";
    audioBtn.textContent = data.audio_option.label;
    audioBtn.addEventListener("click", () => startDownload(data.audio_option.format_selector, true));
    optionsEl.appendChild(audioBtn);
  }
}

function startDownload(formatSelector, isAudioOnly) {
  setStatus("Starting download — check your desktop app...");
  optionsEl.innerHTML = "";

  chrome.runtime.sendMessage(
    {
      action: "startYoutubeDownload",
      url: currentUrl,
      format_selector: formatSelector,
      is_audio_only: isAudioOnly,
      title: currentTitle
    },
    (response) => {
      if (!response || !response.ok || response.data.status !== "completed") {
        const errMsg = response && response.data ? response.data.error : "unknown error";
        setStatus(`Error: ${errMsg || "download failed"}`);
        return;
      }
      setStatus(`Done — check the desktop app for progress.`);
    }
  );
}

function loadCurrentTab() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs || !tabs[0] || !tabs[0].url) {
      setStatus("Could not read this tab's URL.");
      return;
    }
    currentUrl = tabs[0].url;
    currentTitle = tabs[0].title || "";

    if (!currentUrl.startsWith("http")) {
      setStatus("Open a video page (YouTube, Instagram, X, etc.) to use this.");
      return;
    }

    setStatus("Checking for downloadable video...");

    chrome.runtime.sendMessage(
      { action: "extractFormats", url: currentUrl },
      (response) => {
        if (!response || !response.ok) {
          setStatus("Error: could not reach desktop app. Is it running?");
          return;
        }
        const data = response.data;
        if (data.status !== "ok") {
          setStatus("Couldn't extract this page. It may be a feed/timeline (not a single post), private, login-required, or unsupported.");
          return;
        }
        renderOptions(data);
      }
    );
  });
}

refreshCookieButtonLabel();
loadCurrentTab();