// Octopus Clip - Background Service Worker

chrome.commands.onCommand.addListener(async (command) => {
  if (command === "quick-clip") {
    // Quick clip: save current page as "clip" (documents only)
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return;

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["lib/readability.js", "lib/turndown.js", "content.js"],
      });

      const data = results?.[0]?.result;
      if (!data) {
        console.error("[Octopus Clip] Failed to extract page");
        return;
      }

      const payload = {
        url: data.url || tab.url,
        title: data.title || tab.title || "Untitled",
        content: data.markdown || "",
        tags: ["quick-clip"],
        user_note: "",
        action: "clip",
      };

      const apiUrl = await getApiUrl();
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await res.json();
      console.log("[Octopus Clip] Quick clip result:", result);

      // Show a native notification
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon48.png",
        title: "Octopus Clip",
        message: result.message || "页面已收藏到 Documents",
      });
    } catch (err) {
      console.error("[Octopus Clip] Quick clip error:", err);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon48.png",
        title: "Octopus Clip - 失败",
        message: err.message || "保存失败",
      });
    }
  }
});

async function getApiUrl() {
  const stored = await chrome.storage.sync.get("octopus_api_url");
  return stored.octopus_api_url || "http://127.0.0.1:18791/api/knowledge/clip";
}
