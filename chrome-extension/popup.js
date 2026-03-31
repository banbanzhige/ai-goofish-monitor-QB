// Popup script for the Chrome extension

document.addEventListener("DOMContentLoaded", function () {
  const extractBtn = document.getElementById("extractBtn");
  const copyAccountBtn = document.getElementById("copyAccountBtn");
  const copySnapshotBtn = document.getElementById("copySnapshotBtn");
  const stateOutput = document.getElementById("stateOutput");
  const statusDiv = document.getElementById("status");
  const displayNameInput = document.getElementById("displayNameInput");

  let latestSnapshot = null;
  let latestAccountPayload = null;

  function nowSuffix() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
  }

  function sanitizeDisplayName(raw) {
    const base = String(raw || "").trim();
    if (!base) return `手动获取账号_${nowSuffix()}`;
    return base.slice(0, 50);
  }

  function stringify(obj) {
    try {
      return JSON.stringify(obj, null, 2);
    } catch (e) {
      return "";
    }
  }

  function setLoading(isLoading) {
    extractBtn.disabled = isLoading;
    copyAccountBtn.disabled = isLoading;
    if (copySnapshotBtn) {
      copySnapshotBtn.disabled = isLoading;
    }
    extractBtn.textContent = isLoading ? "采集中，请稍候..." : "1) 采集完整快照";
  }

  function updateStatus(message, ok = false) {
    statusDiv.textContent = message;
    statusDiv.className = `status ${ok ? "success" : "error"}`;
  }

  function buildAccountPayload(snapshot, displayName) {
    return {
      display_name: sanitizeDisplayName(displayName),
      created_at: new Date().toISOString(),
      last_used_at: null,
      risk_control_count: 0,
      risk_control_history: [],
      cookies: Array.isArray(snapshot?.cookies) ? snapshot.cookies : [],
      env: snapshot?.env || null,
      headers: snapshot?.headers || null,
      page: snapshot?.page || null,
      storage: snapshot?.storage || null,
    };
  }

  async function copyText(text) {
    if (!text) {
      updateStatus("没有可复制的内容");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      updateStatus("复制成功", true);
    } catch (err) {
      updateStatus(`复制失败: ${err?.message || err}`);
    }
  }

  function renderAccountPayload() {
    stateOutput.value = stringify(latestAccountPayload || {});
  }

  async function captureSnapshot() {
    setLoading(true);
    updateStatus("正在采集浏览器环境与登录状态...");
    stateOutput.value = "";

    chrome.runtime.sendMessage({ type: "captureSnapshot" }, (response) => {
      setLoading(false);

      if (chrome.runtime.lastError) {
        updateStatus(`通信失败: ${chrome.runtime.lastError.message}`);
        return;
      }
      if (!response || !response.ok) {
        updateStatus(`采集失败: ${response?.error || "未知错误"}`);
        return;
      }

      latestSnapshot = response.data;
      latestAccountPayload = buildAccountPayload(latestSnapshot, displayNameInput?.value);
      renderAccountPayload();

      const cookieCount = Array.isArray(latestSnapshot?.cookies) ? latestSnapshot.cookies.length : 0;
      const hasEnv = Boolean(latestSnapshot?.env);
      const hasHeaders = Boolean(latestSnapshot?.headers);
      const hasStorage = Boolean(latestSnapshot?.storage);
      updateStatus(
        `采集完成: cookies=${cookieCount}, env=${hasEnv}, headers=${hasHeaders}, storage=${hasStorage}`,
        true,
      );
    });
  }

  extractBtn.addEventListener("click", captureSnapshot);

  copyAccountBtn.addEventListener("click", async () => {
    if (!latestSnapshot) {
      updateStatus("请先采集完整快照");
      return;
    }
    latestAccountPayload = buildAccountPayload(latestSnapshot, displayNameInput?.value);
    renderAccountPayload();
    await copyText(stringify(latestAccountPayload));
  });

  if (copySnapshotBtn) {
    copySnapshotBtn.addEventListener("click", async () => {
      if (!latestSnapshot) {
        updateStatus("请先采集完整快照");
        return;
      }
      stateOutput.value = stringify(latestSnapshot);
      await copyText(stringify(latestSnapshot));
    });
  }
});
