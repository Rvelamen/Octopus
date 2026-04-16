// Octopus Clip - Popup Script

const DEFAULT_API_URL = "http://127.0.0.1:18791/api/knowledge/clip";

let currentTab = null;
let extractedData = null;

// DOM refs
const els = {
  title: document.getElementById("title"),
  fileName: document.getElementById("file-name"),
  fileNameRow: document.getElementById("file-name-row"),
  tags: document.getElementById("tags"),
  userNote: document.getElementById("user-note"),
  noteLabel: document.getElementById("note-label"),
  extractMethod: document.getElementById("extract-method"),
  togglePreview: document.getElementById("toggle-preview"),
  previewBox: document.getElementById("preview-box"),
  previewContent: document.getElementById("preview-content"),
  previewRow: document.getElementById("preview-row"),
  saveBtn: document.getElementById("save-btn"),
  toast: document.getElementById("toast"),
  tabs: document.querySelectorAll(".tab-btn"),
  tabHint: document.getElementById("tab-hint"),
};

// Helpers
function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.style.background = isError ? "#c0392b" : "#333";
  els.toast.classList.remove("hidden");
  setTimeout(() => els.toast.classList.add("hidden"), 3000);
}

function getSelectedAction() {
  return document.querySelector(".tab-btn.active").dataset.action;
}

function formatTags(raw) {
  return raw
    .split(/[\s,，]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

async function getApiUrl() {
  const stored = await chrome.storage.sync.get("octopus_api_url");
  return stored.octopus_api_url || DEFAULT_API_URL;
}

function updateUIForAction(action) {
  const config = {
    clip: {
      btnText: "收藏到 Documents",
      noteLabel: "备注 / 感想",
      notePlaceholder: "这篇讲得很清楚，特别是...",
      showPreview: true,
      hint: "将当前网页保存为原始文档，供日后查看或手动提取。",
    },
    clip_and_distill: {
      btnText: "收藏并提取到 Notes",
      noteLabel: "备注 / 感想",
      notePlaceholder: "关注这几个核心观点...",
      showPreview: true,
      hint: "保存原始文档，并自动调用 AI 提炼成结构化知识笔记。",
    },
    note: {
      btnText: "保存到 Notes",
      noteLabel: "笔记内容",
      notePlaceholder: "记录下你的想法、摘抄或启发...",
      showPreview: false,
      hint: "直接创建一条笔记，引用当前网页链接。",
    },
  };

  const cfg = config[action] || config.clip;
  els.saveBtn.textContent = cfg.btnText;
  els.noteLabel.textContent = cfg.noteLabel;
  els.userNote.placeholder = cfg.notePlaceholder;
  els.tabHint.textContent = cfg.hint;

  if (cfg.showPreview) {
    els.previewRow.style.display = "flex";
  } else {
    els.previewRow.style.display = "none";
    els.previewBox.classList.add("hidden");
    els.togglePreview.textContent = "查看内容";
  }
}

// Tab switching
els.tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    els.tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    updateUIForAction(tab.dataset.action);
  });
});

// Preview toggle
els.togglePreview.addEventListener("click", () => {
  els.previewBox.classList.toggle("hidden");
  els.togglePreview.textContent = els.previewBox.classList.contains("hidden")
    ? "查看内容"
    : "隐藏内容";
});

// Extract page content via content script
async function extractPage() {
  if (!currentTab?.id) return;

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: currentTab.id },
      files: ["lib/readability.js", "lib/turndown.js", "content.js"],
    });

    extractedData = results?.[0]?.result || null;

    if (!extractedData) {
      throw new Error("未能提取页面内容");
    }

    // Populate UI
    els.title.value = extractedData.title || "";
    const isPdf = extractedData.method === "pdf";
    if (isPdf) {
      els.fileNameRow.classList.remove("hidden");
      els.fileName.value = extractedData.title ? extractedData.title.replace(/[^\w\u4e00-\u9fa5\-]+/g, "_").slice(0, 60) : "";
    } else {
      els.fileNameRow.classList.add("hidden");
    }
    const methodText = {
      selection: "已提取：用户选中内容",
      readability: "已提取：正文内容",
      innerText: "已提取：页面文本（备用模式）",
      fallback: "已提取：页面文本（内容较少）",
      pdf: "已识别：PDF 文档",
    };
    els.extractMethod.textContent = methodText[extractedData.method] || "已提取页面内容";

    const preview = extractedData.markdown || "";
    els.previewContent.textContent =
      preview.length > 800 ? preview.slice(0, 800) + "\n\n..." : preview;

    if (extractedData.method === "fallback") {
      showToast("当前页面内容较少，将保存为链接引用", false);
    }
  } catch (err) {
    console.error("Extract error:", err);
    els.extractMethod.textContent = "提取失败";
    showToast("页面提取失败：" + err.message, true);
    extractedData = {
      title: currentTab.title || "",
      url: currentTab.url || "",
      markdown: "",
      method: "fallback",
    };
    els.title.value = extractedData.title;
    els.previewContent.textContent = "（无内容）";
  }
}

// Save to Octopus
async function saveClip() {
  if (!extractedData) return;

  const action = getSelectedAction();
  const payload = {
    url: extractedData.url || currentTab.url,
    title: els.title.value.trim() || extractedData.title || "Untitled",
    content: extractedData.markdown || "",
    tags: formatTags(els.tags.value),
    user_note: els.userNote.value.trim(),
    action: action,
    is_pdf: extractedData?.method === "pdf",
    file_name: els.fileName.value.trim() || undefined,
  };

  els.saveBtn.disabled = true;
  els.saveBtn.textContent = "保存中...";

  try {
    const apiUrl = await getApiUrl();
    const res = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || errData.error || `HTTP ${res.status}`);
    }

    const data = await res.json();
    showToast(data.message || "保存成功");

    // Auto close popup after success
    setTimeout(() => window.close(), 1200);
  } catch (err) {
    console.error("Save error:", err);
    showToast("保存失败：" + err.message, true);
  } finally {
    els.saveBtn.disabled = false;
    els.saveBtn.textContent = "保存到 Octopus";
  }
}

els.saveBtn.addEventListener("click", saveClip);

// Init
async function init() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentTab = tab;
    await extractPage();
    updateUIForAction(getSelectedAction());
  } catch (err) {
    showToast("初始化失败：" + err.message, true);
  }
}

init();
