// Service worker for capturing browser environment, headers, storage, and cookies

const GOOFISH_HOST_PATTERN = "*://*.goofish.com/*";
const MAX_STORAGE_ENTRY_LENGTH = 4096; // bytes limit to drop oversized values

function mapSameSiteValue(chromeSameSite) {
  if (chromeSameSite === undefined || chromeSameSite === null) return "Lax";
  const sameSiteMap = {
    no_restriction: "None",
    lax: "Lax",
    strict: "Strict",
    unspecified: "Lax",
  };
  return sameSiteMap[chromeSameSite] || "Lax";
}

function headersArrayToObject(headers = []) {
  const result = {};
  headers.forEach((item) => {
    if (item && item.name) {
      result[item.name] = item.value || "";
    }
  });
  return result;
}

async function getActiveGoofishTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs?.[0];
  if (!tab || !tab.id || !tab.url) {
    throw new Error("未找到活动标签页");
  }
  if (!tab.url.includes("goofish.com")) {
    throw new Error("请先打开 goofish.com 页面");
  }
  return tab;
}

async function capturePageData(tabId) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const safeEntries = (storage) => {
        try {
          const obj = {};
          for (let i = 0; i < storage.length; i += 1) {
            const key = storage.key(i);
            if (key !== null) {
              obj[key] = storage.getItem(key);
            }
          }
          return obj;
        } catch (e) {
          return {};
        }
      };

      const intl = (() => {
        try {
          return Intl.DateTimeFormat().resolvedOptions();
        } catch (e) {
          return {};
        }
      })();

      const uaData = (() => {
        try {
          return navigator.userAgentData ? navigator.userAgentData.toJSON() : null;
        } catch (e) {
          return null;
        }
      })();

      return {
        page: {
          pageUrl: location.href,
          referrer: document.referrer || null,
          visibilityState: document.visibilityState,
        },
        env: {
          navigator: {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            vendor: navigator.vendor,
            language: navigator.language,
            languages: navigator.languages,
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory,
            webdriver: navigator.webdriver,
            doNotTrack: navigator.doNotTrack,
            maxTouchPoints: navigator.maxTouchPoints,
            userAgentData: uaData,
          },
          screen: {
            width: screen.width,
            height: screen.height,
            availWidth: screen.availWidth,
            availHeight: screen.availHeight,
            colorDepth: screen.colorDepth,
            pixelDepth: screen.pixelDepth,
            devicePixelRatio: window.devicePixelRatio,
          },
          intl,
        },
        storage: {
          local: safeEntries(localStorage),
          session: safeEntries(sessionStorage),
        },
      };
    },
  });

  if (!result || !result.result) {
    throw new Error("无法获取页面信息");
  }

  return result.result;
}

function filterEnvData(env = {}) {
  const nav = env.navigator || {};
  const screen = env.screen || {};
  const intl = env.intl || {};

  return {
    navigator: {
      userAgent: nav.userAgent,
      platform: nav.platform,
      language: nav.language,
      languages: nav.languages,
      hardwareConcurrency: nav.hardwareConcurrency,
      deviceMemory: nav.deviceMemory,
      maxTouchPoints: nav.maxTouchPoints,
      webdriver: nav.webdriver,
      doNotTrack: nav.doNotTrack,
      userAgentData: nav.userAgentData || null,
    },
    screen: {
      width: screen.width,
      height: screen.height,
      devicePixelRatio: screen.devicePixelRatio,
      colorDepth: screen.colorDepth,
    },
    intl: {
      timeZone: intl.timeZone,
      locale: intl.locale,
    },
  };
}

function pruneStorageEntries(entries = {}) {
  const data = {};
  const dropped = [];
  Object.entries(entries).forEach(([key, value]) => {
    const str = value == null ? "" : String(value);
    if (str.length <= MAX_STORAGE_ENTRY_LENGTH) {
      data[key] = value;
    } else {
      dropped.push(key);
    }
  });
  return { data, dropped };
}

function filterHeaders(rawHeaders = {}) {
  const allowList = [
    "user-agent",
    "accept",
    "accept-language",
    "accept-encoding",
    "referer",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "sec-fetch-site",
    "sec-fetch-mode",
    "sec-fetch-dest",
    "sec-fetch-user",
    "origin",
    "cache-control",
    "pragma",
    "upgrade-insecure-requests",
    "content-type",
  ];
  const normalized = {};
  Object.entries(rawHeaders).forEach(([k, v]) => {
    const lower = k.toLowerCase();
    if (allowList.includes(lower)) {
      normalized[k] = v;
    }
  });
  return normalized;
}

function buildAutoLikeHeaders(env = {}, page = {}) {
  const navigator = env.navigator || {};
  const language = String(navigator.language || "zh-CN").trim() || "zh-CN";
  const userAgent = String(navigator.userAgent || "").trim();
  const referer = String(page.pageUrl || page.referrer || "https://www.goofish.com/").trim();

  const headers = {
    "User-Agent": userAgent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": language,
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": referer || "https://www.goofish.com/",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?1",
    "Sec-Ch-Ua-Platform": '"Android"',
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
  };
  return Object.fromEntries(Object.entries(headers).filter(([, value]) => value));
}

function looksLikeProbeHeaders(headers = {}) {
  const lowered = {};
  Object.entries(headers).forEach(([key, value]) => {
    lowered[String(key).toLowerCase()] = String(value || "").trim().toLowerCase();
  });
  return lowered["sec-fetch-mode"] === "cors" || lowered["sec-fetch-dest"] === "empty" || lowered.accept === "*/*";
}

function normalizeSnapshotHeaders(rawHeaders = {}, env = {}, page = {}) {
  const filtered = filterHeaders(rawHeaders);
  const fallback = buildAutoLikeHeaders(env, page);
  if (!Object.keys(filtered).length || looksLikeProbeHeaders(filtered)) {
    return fallback;
  }

  const merged = { ...filtered };
  const existingLower = new Set(Object.keys(merged).map((key) => key.toLowerCase()));
  Object.entries(fallback).forEach(([key, value]) => {
    if (!existingLower.has(key.toLowerCase())) {
      merged[key] = value;
    }
  });
  return merged;
}

async function captureHeaders(tabId) {
  return new Promise((resolve) => {
    let resolved = false;

    const cleanup = (headers) => {
      if (resolved) return;
      resolved = true;
      chrome.webRequest.onBeforeSendHeaders.removeListener(listener);
      clearTimeout(timer);
      resolve(headersArrayToObject(headers || []));
    };

    const listener = (details) => {
      if (details.tabId !== tabId) return;
      cleanup(details.requestHeaders || []);
    };

    const extraInfo = ["requestHeaders"];
    // extraHeaders 提供更完整的 header 视图，在新版本 Chrome 需要显式声明
    extraInfo.push("extraHeaders");

    chrome.webRequest.onBeforeSendHeaders.addListener(
      listener,
      { urls: [GOOFISH_HOST_PATTERN], tabId },
      extraInfo,
    );

    const timer = setTimeout(() => cleanup(null), 2000);

    // 触发一次轻量请求以获取真实请求头
    chrome.scripting
      .executeScript({
        target: { tabId },
        func: () => {
          try {
            fetch(`${window.location.origin}/__codex_probe?ts=${Date.now()}`, {
              credentials: "include",
              cache: "no-store",
              redirect: "follow",
            }).catch(() => {});
          } catch (e) {
            /* ignore */
          }
        },
      })
      .catch(() => {
        // 如果注入失败，继续等待可能已有的请求
      });
  });
}

async function captureCookies(url) {
  const cookies = await chrome.cookies.getAll({ url });
  return cookies.map((cookie) => ({
    name: cookie.name,
    value: cookie.value,
    domain: cookie.domain,
    path: cookie.path,
    expires: cookie.expirationDate,
    httpOnly: cookie.httpOnly,
    secure: cookie.secure,
    sameSite: mapSameSiteValue(cookie.sameSite),
  }));
}

async function buildSnapshot() {
  const tab = await getActiveGoofishTab();
  const pageData = await capturePageData(tab.id);
  const capturedHeaders = await captureHeaders(tab.id);
  const cookies = await captureCookies(new URL(tab.url).origin);

  const filteredEnv = filterEnvData(pageData.env);
  const localPruned = pruneStorageEntries(pageData.storage.local);
  const sessionPruned = pruneStorageEntries(pageData.storage.session);
  const filteredStorage = {
    local: localPruned.data,
    session: sessionPruned.data,
  };
  const normalizedEnv = { ...filteredEnv, storage: filteredStorage };
  const normalizedHeaders = normalizeSnapshotHeaders(capturedHeaders, normalizedEnv, pageData.page || {});

  return {
    capturedAt: new Date().toISOString(),
    pageUrl: tab.url,
    page: pageData.page,
    env: normalizedEnv,
    storage: filteredStorage,
    meta: {
      droppedStorageKeys: {
        local: localPruned.dropped,
        session: sessionPruned.dropped,
      },
    },
    headers: normalizedHeaders,
    cookies,
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "captureSnapshot") {
    return false;
  }

  buildSnapshot()
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});
