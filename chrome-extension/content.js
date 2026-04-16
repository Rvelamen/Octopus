// Octopus Clip - Content Script
// Runs in the context of the active web page

function extractPage() {
  // 1. Priority: user text selection
  const selection = window.getSelection().toString().trim();
  if (selection.length > 30) {
    return {
      title: document.title,
      url: window.location.href,
      markdown: selection,
      excerpt: selection.slice(0, 200),
      method: "selection",
    };
  }

  // Helper: check if page is likely a video/image/special content
  const isVideoPage = document.querySelector("video") && !document.querySelector("article, [role='main'], main");
  const isYouTube = window.location.hostname.includes("youtube.com");
  const isPdf = document.contentType === "application/pdf" || window.location.pathname.endsWith(".pdf");

  if (isPdf) {
    return {
      title: document.title,
      url: window.location.href,
      markdown: "",
      excerpt: "PDF 文档",
      method: "pdf",
    };
  }

  // 2. Try Readability
  let article = null;
  try {
    const documentClone = document.cloneNode(true);
    article = new Readability(documentClone).parse();
  } catch (e) {
    // Readability failed
  }

  const hasGoodArticle = article && article.content && article.textContent.length > 200;

  if (hasGoodArticle && typeof TurndownService !== "undefined") {
    try {
      const turndownService = new TurndownService({
        headingStyle: "atx",
        bulletListMarker: "-",
        codeBlockStyle: "fenced",
        hr: "---",
      });

      // Remove unwanted elements before conversion
      turndownService.remove(["script", "style", "nav", "aside", "footer", "header", "noscript"]);

      // Custom rule for figures/captions
      turndownService.addRule("figcaption", {
        filter: "figcaption",
        replacement: (content) => `*${content}*\n`,
      });

      const markdown = turndownService.turndown(article.content);

      return {
        title: article.title || document.title,
        url: window.location.href,
        markdown: markdown,
        excerpt: article.excerpt || article.textContent.slice(0, 200),
        byline: article.byline,
        method: "readability",
      };
    } catch (e) {
      // Turndown failed, fall through
    }
  }

  // 3. Fallback: innerText (for SPA like Notion, Feishu, etc.)
  const bodyText = document.body ? document.body.innerText.trim() : "";

  // For video pages with very little text, return empty to trigger stub creation
  if ((isVideoPage || isYouTube) && bodyText.length < 300) {
    return {
      title: document.title,
      url: window.location.href,
      markdown: "",
      excerpt: document.title,
      method: "fallback",
    };
  }

  return {
    title: document.title,
    url: window.location.href,
    markdown: bodyText,
    excerpt: bodyText.slice(0, 200),
    method: "innerText",
  };
}

// Execute and return result to popup.js
extractPage();
