const handledDownloads = new Set();

const YT_DLP_SITES = ["youtube.com", "instagram.com", "x.com", "twitter.com"];

function isYtDlpSite(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return YT_DLP_SITES.some((site) => host === site || host.endsWith("." + site));
  } catch {
    return false;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "download-with-my-downloader",
    title: "Download with Network Download Administration",
    contexts: ["image", "link", "video", "audio"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "download-with-my-downloader") return;

  const pageUrl = tab && tab.url ? tab.url : "";
  if (isYtDlpSite(pageUrl)) {
    chrome.action.openPopup().catch(() => {
      // openPopup requires user gesture context in some Chrome versions;
      // fall back to at least notifying the user via console.
      console.warn("Use the extension icon popup for YouTube/Instagram/X downloads.");
    });
    return;
  }

  const targetUrl = info.srcUrl || info.linkUrl;
  if (!targetUrl) return;
  if (targetUrl.startsWith("blob:")) {
    console.warn("Blob URL detected — right-click download won't work here. Use the extension popup instead.");
    return;
  }
  sendToServer(targetUrl, "", pageUrl);
});

chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
  if (handledDownloads.has(downloadItem.id)) {
    suggest();
    return;
  }
  handledDownloads.add(downloadItem.id);

  if (isYtDlpSite(downloadItem.referrer || "") || downloadItem.url.startsWith("blob:")) {
    // Let the browser handle it normally instead of intercepting into a broken .bin file
    suggest();
    handledDownloads.delete(downloadItem.id);
    return;
  }

  sendToServer(downloadItem.url, downloadItem.filename || "", downloadItem.referrer || "");
  suggest();

  // Only attempt to cancel if the download is still actually in progress —
  // avoids the "Download must be in progress" error when Chrome has already
  // moved it to "complete"/"interrupted" by the time this callback runs.
  chrome.downloads.search({ id: downloadItem.id }, (results) => {
    if (chrome.runtime.lastError) {
      handledDownloads.delete(downloadItem.id);
      return;
    }
    const current = results && results[0];
    if (!current || current.state !== "in_progress") {
      handledDownloads.delete(downloadItem.id);
      return;
    }

    chrome.downloads.cancel(downloadItem.id, () => {
      if (chrome.runtime.lastError) {
        // Already finished/cancelled between our check and this call — harmless race, ignore.
      }
      chrome.downloads.erase({ id: downloadItem.id }, () => {
        if (chrome.runtime.lastError) {
          // Already erased — harmless, ignore.
        }
        handledDownloads.delete(downloadItem.id);
      });
    });
  });
});

function sendToServer(url, filename, referrer) {
  fetch("http://127.0.0.1:5000/new-download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, filename, referrer })
  }).catch((err) => {
    console.error("Failed to reach desktop app:", err);
  });
}

// ---- YouTube/Instagram/X popup support ----

async function hasCookiePermission() {
  try {
    return await chrome.permissions.contains({
      permissions: ["cookies"],
      origins: ["<all_urls>"]
    });
  } catch {
    return false;
  }
}

function toNetscapeCookieFile(cookies) {
  const lines = ["# Netscape HTTP Cookie File"];
  for (const c of cookies) {
    // Leading dot on the domain tells yt-dlp/curl the cookie applies to subdomains too.
    const domain = c.domain.startsWith(".") ? c.domain : (c.hostOnly ? c.domain : "." + c.domain);
    const includeSubdomains = domain.startsWith(".") ? "TRUE" : "FALSE";
    const path = c.path || "/";
    const secure = c.secure ? "TRUE" : "FALSE";
    // Session cookies have no expirationDate — Netscape format uses 0 for those.
    const expiration = c.expirationDate ? Math.round(c.expirationDate) : 0;
    lines.push([domain, includeSubdomains, path, secure, expiration, c.name, c.value].join("\t"));
  }
  return lines.join("\n") + "\n";
}

async function getCookiesForUrl(url) {
  const granted = await hasCookiePermission();
  if (!granted) return "";
  try {
    const cookies = await chrome.cookies.getAll({ url });
    if (!cookies || cookies.length === 0) return "";
    return toNetscapeCookieFile(cookies);
  } catch (err) {
    console.warn("Failed to read cookies:", err);
    return "";
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "extractFormats") {
    (async () => {
      const cookies = await getCookiesForUrl(message.url);
      fetch("http://127.0.0.1:5000/extract-formats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: message.url, cookies })
      })
        .then((res) => res.json())
        .then((data) => sendResponse({ ok: true, data }))
        .catch((err) => sendResponse({ ok: false, error: String(err) }));
    })();
    return true;
  }

  if (message.action === "startYoutubeDownload") {
    (async () => {
      const cookies = await getCookiesForUrl(message.url);
      fetch("http://127.0.0.1:5000/new-youtube-download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: message.url,
          format_selector: message.format_selector,
          is_audio_only: message.is_audio_only,
          title: message.title,
          cookies
        })
      })
        .then((res) => res.json())
        .then((data) => sendResponse({ ok: true, data }))
        .catch((err) => sendResponse({ ok: false, error: String(err) }));
    })();
    return true;
  }
});