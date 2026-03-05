// State management
const state = {
  health: "checking",
  figures: {},
  selectedFigure: "",
  messages: [], // Chat history: [{role: 'user'|'assistant', content: '...', citations: [], timestamp: Date}]
  loading: false,
  error: "",
  shouldAutoScroll: false,
  _lastRenderedMessageVersion: 0,
  _messageVersion: 0,
};

// Persist conversation to localStorage
function saveConversation() {
  try {
    const data = { messages: state.messages, selectedFigure: state.selectedFigure };
    localStorage.setItem("saint-scholar-conversation", JSON.stringify(data));
  } catch (_) { /* quota exceeded or private mode — ignore */ }
}

function loadConversation() {
  try {
    const raw = localStorage.getItem("saint-scholar-conversation");
    if (!raw) return;
    const data = JSON.parse(raw);
    if (Array.isArray(data.messages)) {
      state.messages = data.messages.filter((m) => !m.loading);
      state._messageVersion++;
    }
    if (data.selectedFigure) {
      state.selectedFigure = data.selectedFigure;
    }
  } catch (_) { /* corrupt data — ignore */ }
}

const promptStarters = [
  "What are the neurobiological mechanisms underlying chronic stress-induced structural changes in the hippocampus and prefrontal cortex?",
  "How does sleep architecture influence synaptic consolidation and memory formation across different stages of the sleep cycle?",
  "What is the relationship between contemplative practice and experience-dependent neuroplasticity in attention networks?",
  "How does aerobic exercise modulate neurotrophic factors and cognitive reserve across the lifespan?",
];

// Element references
const el = {
  healthBadge: document.getElementById("health-badge"),
  requestId: document.getElementById("request-id"),
  figureList: document.getElementById("figure-list"),
  promptList: document.getElementById("prompt-list"),
  welcomeState: document.getElementById("welcome-state"),
  chatMessages: document.getElementById("chat-messages"),
  askForm: document.getElementById("ask-form"),
  questionInput: document.getElementById("question-input"),
  charCount: document.getElementById("char-count"),
  askBtn: document.getElementById("ask-btn"),
  errorBanner: document.getElementById("error-banner"),
  metaStrip: document.getElementById("meta-strip"),
  newChatBtn: document.getElementById("new-chat-btn"),
  themeToggle: document.getElementById("theme-toggle"),
  infoToggle: document.getElementById("info-toggle"),
  infoDrawer: document.getElementById("info-drawer"),
  infoOverlay: document.getElementById("info-overlay"),
  infoClose: document.getElementById("info-close"),
};

// Theme management
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
  const icon = el.themeToggle.querySelector('.theme-icon');
  if (icon) {
    // Use SVG icons instead of emoji for consistent rendering
    if (theme === 'light') {
      icon.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
    } else {
      icon.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
  }
}

// Utility functions
function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sanitizeUrl(rawUrl) {
  const trimmed = String(rawUrl || "").trim();
  if (!trimmed) return "";

  try {
    const parsed = new URL(trimmed, window.location.origin);
    if (parsed.protocol === "http:" || parsed.protocol === "https:" || parsed.protocol === "mailto:") {
      return parsed.href;
    }
  } catch (_) {}
  return "";
}

function parseInlineMarkdown(text) {
  const escaped = escapeHtml(text);
  const tokenized = [];
  let working = escaped;

  const pushToken = (html) => {
    const key = `@@MD_TOKEN_${tokenized.length}@@`;
    tokenized.push({ key, html });
    return key;
  };

  // Inline code first to avoid styling markers inside code spans.
  working = working.replace(/`([^`\n]+)`/g, (_, code) => pushToken(`<code>${code}</code>`));

  // Links — label is already escaped (from the initial escapeHtml pass on the full text),
  // but re-escape to guard against any edge cases where tokens could inject HTML.
  working = working.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => {
    const safeHref = sanitizeUrl(href);
    if (!safeHref) return `[${escapeHtml(label)}](${escapeHtml(href)})`;
    return pushToken(
      `<a href="${escapeHtml(safeHref)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`
    );
  });

  // Strong, emphasis, strike
  working = working
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
    .replace(/~~([^~\n]+)~~/g, "<del>$1</del>");

  // Hard line breaks from single newlines inside paragraphs.
  working = working.replace(/\n/g, "<br>");

  return tokenized.reduce((acc, token) => acc.replaceAll(token.key, token.html), working);
}

function setError(message) {
  state.error = message || "";
  el.errorBanner.textContent = state.error;
  el.errorBanner.classList.toggle("hidden", !state.error);
}

async function http(path, init) {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string" && body.detail.trim()) {
        detail = body.detail.trim();
      }
    } catch (_) {}
    throw new Error(detail);
  }

  try {
    return await response.json();
  } catch (_) {
    throw new Error("Received an invalid response from the server.");
  }
}

// Custom distinctive icons for each character - simplified for better rendering
const CHARACTER_ICONS = {
  buddha: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="18" r="8" fill="#FFB74D"/>
    <circle cx="20" cy="18" r="6" fill="#FFD54F"/>
    <circle cx="20" cy="10" r="3" fill="#4A148C"/>
    <circle cx="17" cy="17" r="1.2" fill="#5D4037"/>
    <circle cx="23" cy="17" r="1.2" fill="#5D4037"/>
    <ellipse cx="20" cy="28" rx="8" ry="3" fill="#FF6F00" opacity="0.6"/>
    <ellipse cx="20" cy="30" rx="10" ry="4" fill="#FF8F00" opacity="0.5"/>
  </svg>`,

  aurelius: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="20" cy="14" rx="8" ry="3" fill="#4CAF50"/>
    <circle cx="12" cy="14" r="2" fill="#2E7D32"/>
    <circle cx="28" cy="14" r="2" fill="#2E7D32"/>
    <circle cx="20" cy="19" r="7" fill="#8D6E63"/>
    <rect x="17" y="18" width="2" height="2" fill="#424242"/>
    <rect x="24" y="18" width="2" height="2" fill="#424242"/>
    <rect x="13" y="26" width="14" height="10" rx="2" fill="#B71C1C"/>
    <rect x="15" y="28" width="10" height="6" fill="#D32F2F"/>
    <circle cx="20" cy="28" r="2" fill="#FFD700"/>
  </svg>`,

  rumi: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="20" cy="12" rx="9" ry="4" fill="#1B5E20"/>
    <ellipse cx="20" cy="11" rx="8" ry="3" fill="#2E7D32"/>
    <circle cx="20" cy="11" r="2" fill="#4CAF50"/>
    <circle cx="20" cy="19" r="5.5" fill="#BCAAA4"/>
    <rect x="18" y="23" width="4" height="3" rx="2" fill="#4E342E"/>
    <circle cx="18" cy="19" r="1" fill="#424242"/>
    <circle cx="25" cy="19" r="1" fill="#424242"/>
    <rect x="13" y="26" width="14" height="10" rx="3" fill="#004D40"/>
    <rect x="15" y="27" width="10" height="8" rx="2" fill="#00695C" opacity="0.8"/>
    <line x1="10" y1="28" x2="12" y2="30" stroke="#26A69A" stroke-width="2" opacity="0.5"/>
    <line x1="30" y1="28" x2="28" y2="30" stroke="#26A69A" stroke-width="2" opacity="0.5"/>
  </svg>`,

  solomon: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="17" r="7" fill="#FFCCBC"/>
    <rect x="13" y="10" width="14" height="3" rx="1" fill="#FFD700"/>
    <polygon points="14,10 16,7 18,10" fill="#FFD700"/>
    <polygon points="19,10 20,6 21,10" fill="#FFA000"/>
    <polygon points="22,10 24,7 26,10" fill="#FFD700"/>
    <circle cx="20" cy="8" r="1.5" fill="#FF6F00"/>
    <circle cx="17" cy="17" r="1.3" fill="#424242"/>
    <circle cx="26" cy="17" r="1.3" fill="#424242"/>
    <circle cx="17.4" cy="16.6" r="0.5" fill="#FFFFFF"/>
    <circle cx="26.4" cy="16.6" r="0.5" fill="#FFFFFF"/>
    <ellipse cx="20" cy="22" rx="5" ry="3" fill="#8D6E63"/>
    <ellipse cx="20" cy="24" rx="4" ry="2" fill="#6D4C41"/>
    <rect x="13" y="28" width="14" height="9" rx="2" fill="#4A148C"/>
    <rect x="15" y="29" width="10" height="7" fill="#6A1B9A" opacity="0.8"/>
    <rect x="13" y="28" width="14" height="1.5" fill="#FFD700"/>
  </svg>`,

  laotzu: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="16" r="7" fill="#BCAAA4"/>
    <ellipse cx="20" cy="12" rx="8" ry="5" fill="#E0E0E0"/>
    <ellipse cx="20" cy="11" rx="6" ry="3" fill="#F5F5F5"/>
    <circle cx="17" cy="16" r="1" fill="#424242"/>
    <circle cx="23" cy="16" r="1" fill="#424242"/>
    <ellipse cx="20" cy="23" rx="4" ry="3" fill="#E0E0E0"/>
    <ellipse cx="20" cy="26" rx="3" ry="4" fill="#BDBDBD"/>
    <rect x="13" y="28" width="14" height="9" rx="3" fill="#2E7D32"/>
    <rect x="15" y="29" width="10" height="7" rx="2" fill="#388E3C" opacity="0.8"/>
    <circle cx="18" cy="32" r="3" fill="#FAFAFA"/>
    <circle cx="18" cy="32" r="1.5" fill="#212121"/>
    <circle cx="22" cy="32" r="3" fill="#212121"/>
    <circle cx="22" cy="32" r="1.5" fill="#FAFAFA"/>
  </svg>`,

  epictetus: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="17" r="7" fill="#D7CCC8"/>
    <circle cx="17" cy="16" r="1.2" fill="#424242"/>
    <circle cx="23" cy="16" r="1.2" fill="#424242"/>
    <ellipse cx="20" cy="22" rx="3" ry="2" fill="#A1887F"/>
    <rect x="13" y="26" width="14" height="10" rx="2" fill="#5C6BC0"/>
    <rect x="15" y="27" width="10" height="8" rx="1" fill="#7986CB" opacity="0.8"/>
    <circle cx="14" cy="30" r="2" fill="#9E9E9E"/>
    <circle cx="26" cy="30" r="2" fill="#9E9E9E"/>
    <line x1="11" y1="30" x2="14" y2="30" stroke="#757575" stroke-width="1.5"/>
    <line x1="26" y1="30" x2="29" y2="30" stroke="#757575" stroke-width="1.5"/>
  </svg>`,

  seneca: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="16" r="7" fill="#BCAAA4"/>
    <ellipse cx="20" cy="11" rx="7" ry="3" fill="#E0E0E0"/>
    <circle cx="17" cy="16" r="1.2" fill="#424242"/>
    <circle cx="23" cy="16" r="1.2" fill="#424242"/>
    <ellipse cx="20" cy="22" rx="3" ry="2" fill="#8D6E63"/>
    <rect x="13" y="26" width="14" height="10" rx="2" fill="#7B1FA2"/>
    <rect x="15" y="27" width="10" height="8" fill="#9C27B0" opacity="0.7"/>
    <rect x="28" y="24" width="3" height="8" rx="1" fill="#5D4037"/>
    <circle cx="29.5" cy="23" r="2" fill="#F5F5DC"/>
    <line x1="29" y1="22" x2="31" y2="20" stroke="#5D4037" stroke-width="1"/>
  </svg>`,

  confucius: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="17" r="7" fill="#FFCCBC"/>
    <rect x="13" y="10" width="14" height="4" rx="1" fill="#212121"/>
    <rect x="12" y="13" width="16" height="2" fill="#424242"/>
    <circle cx="17" cy="17" r="1.2" fill="#424242"/>
    <circle cx="23" cy="17" r="1.2" fill="#424242"/>
    <ellipse cx="20" cy="23" rx="3" ry="3" fill="#E0E0E0"/>
    <ellipse cx="20" cy="26" rx="2.5" ry="4" fill="#BDBDBD"/>
    <rect x="13" y="28" width="14" height="9" rx="2" fill="#C62828"/>
    <rect x="15" y="29" width="10" height="7" fill="#D32F2F" opacity="0.8"/>
    <line x1="20" y1="28" x2="20" y2="36" stroke="#FFD700" stroke-width="1.5"/>
  </svg>`,

  krishna: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="16" r="7" fill="#42A5F5"/>
    <circle cx="20" cy="16" r="5.5" fill="#64B5F6"/>
    <circle cx="17" cy="15" r="1.2" fill="#1A237E"/>
    <circle cx="23" cy="15" r="1.2" fill="#1A237E"/>
    <polygon points="16,8 20,4 24,8" fill="#FFD700"/>
    <circle cx="20" cy="6" r="1.5" fill="#FF6F00"/>
    <circle cx="17" cy="7" r="1" fill="#4CAF50"/>
    <circle cx="23" cy="7" r="1" fill="#4CAF50"/>
    <rect x="13" y="26" width="14" height="10" rx="2" fill="#FDD835"/>
    <rect x="15" y="27" width="10" height="8" fill="#FFEE58" opacity="0.8"/>
    <line x1="8" y1="22" x2="13" y2="26" stroke="#8D6E63" stroke-width="2"/>
    <circle cx="7" cy="21" r="2" fill="#8D6E63"/>
  </svg>`,

  upanishads: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="20" r="12" fill="#FF8F00" opacity="0.3"/>
    <circle cx="20" cy="20" r="8" fill="#FF8F00" opacity="0.5"/>
    <circle cx="20" cy="20" r="5" fill="#FFB74D"/>
    <circle cx="20" cy="20" r="3" fill="#FFF8E1"/>
    <line x1="20" y1="6" x2="20" y2="10" stroke="#FF6F00" stroke-width="1.5"/>
    <line x1="20" y1="30" x2="20" y2="34" stroke="#FF6F00" stroke-width="1.5"/>
    <line x1="6" y1="20" x2="10" y2="20" stroke="#FF6F00" stroke-width="1.5"/>
    <line x1="30" y1="20" x2="34" y2="20" stroke="#FF6F00" stroke-width="1.5"/>
    <line x1="10" y1="10" x2="13" y2="13" stroke="#FF6F00" stroke-width="1"/>
    <line x1="27" y1="27" x2="30" y2="30" stroke="#FF6F00" stroke-width="1"/>
    <line x1="30" y1="10" x2="27" y2="13" stroke="#FF6F00" stroke-width="1"/>
    <line x1="13" y1="27" x2="10" y2="30" stroke="#FF6F00" stroke-width="1"/>
  </svg>`,

  Default: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="20" r="10" fill="#90CAF9"/>
    <circle cx="20" cy="20" r="8" fill="#42A5F5"/>
    <circle cx="17" cy="19" r="2" fill="#1976D2"/>
    <circle cx="26" cy="19" r="2" fill="#1976D2"/>
  </svg>`
};

// Get pixel art icon for character
function getCharacterIcon(figureId) {
  return CHARACTER_ICONS[figureId] || CHARACTER_ICONS.Default;
}

// Render functions
function renderHealth() {
  const statusClass = {
    ok: "status-ok",
    checking: "status-warn",
    down: "status-bad",
  }[state.health] || "status-warn";

  el.healthBadge.className = `health-badge ${statusClass}`;
}

function renderFigures() {
  const keys = Object.keys(state.figures);
  if (!keys.length) {
    el.figureList.innerHTML = "<p style='text-align: center; color: var(--ink-tertiary); font-family: Source Sans 3, sans-serif; font-size: 0.8125rem;'>No voices available.</p>";
    return;
  }

  const html = keys
    .map((id) => {
      const figure = state.figures[id];
      const activeClass = state.selectedFigure === id ? "active" : "";
      const icon = getCharacterIcon(id);

      return `
        <button class="figure-card ${activeClass}" data-figure="${id}">
          <div class="figure-avatar" data-figure="${id}">${icon}</div>
          <div class="figure-text">
            <div class="figure-name">${figure.name || id}</div>
            <div class="figure-meta">${figure.tradition || ""}</div>
          </div>
        </button>
      `;
    })
    .join("");

  el.figureList.innerHTML = html;
}

function renderPromptStarters() {
  el.promptList.innerHTML = promptStarters
    .map((prompt) => `<button class="prompt-chip" data-prompt="${escapeHtml(prompt)}">${escapeHtml(prompt)}</button>`)
    .join("");
}

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function renderMessageContent(content) {
  const normalized = String(content || "").replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const html = [];
  let i = 0;

  const consumeList = (startIndex, ordered) => {
    const items = [];
    let idx = startIndex;
    const pattern = ordered ? /^\d+\.\s+(.+)$/ : /^[-*+]\s+(.+)$/;
    while (idx < lines.length) {
      const line = lines[idx].trim();
      if (!line) break;
      const match = line.match(pattern);
      if (!match) break;
      items.push(`<li>${parseInlineMarkdown(match[1])}</li>`);
      idx += 1;
    }
    if (!items.length) return { html: "", next: startIndex };
    return {
      html: ordered ? `<ol>${items.join("")}</ol>` : `<ul>${items.join("")}</ul>`,
      next: idx,
    };
  };

  while (i < lines.length) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    // Fenced code blocks
    const codeFence = trimmed.match(/^```([a-zA-Z0-9_-]+)?$/);
    if (codeFence) {
      const lang = codeFence[1] ? ` class="language-${escapeHtml(codeFence[1])}"` : "";
      i += 1;
      const codeLines = [];
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) i += 1; // Consume closing fence.
      html.push(`<pre><code${lang}>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      continue;
    }

    // Headings
    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      html.push(`<h${level}>${parseInlineMarkdown(headingMatch[2])}</h${level}>`);
      i += 1;
      continue;
    }

    // Blockquotes
    if (trimmed.startsWith(">")) {
      const quoteLines = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      html.push(`<blockquote>${parseInlineMarkdown(quoteLines.join("\n"))}</blockquote>`);
      continue;
    }

    // Unordered list
    if (/^[-*+]\s+/.test(trimmed)) {
      const list = consumeList(i, false);
      if (list.html) {
        html.push(list.html);
        i = list.next;
        continue;
      }
    }

    // Ordered list
    if (/^\d+\.\s+/.test(trimmed)) {
      const list = consumeList(i, true);
      if (list.html) {
        html.push(list.html);
        i = list.next;
        continue;
      }
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      html.push("<hr>");
      i += 1;
      continue;
    }

    // Paragraph (consume until blank line or block delimiter)
    const paragraphLines = [];
    while (i < lines.length) {
      const candidate = lines[i];
      const candidateTrimmed = candidate.trim();
      if (!candidateTrimmed) break;
      if (/^```/.test(candidateTrimmed)) break;
      if (/^(#{1,4})\s+/.test(candidateTrimmed)) break;
      if (/^>/.test(candidateTrimmed)) break;
      if (/^[-*+]\s+/.test(candidateTrimmed)) break;
      if (/^\d+\.\s+/.test(candidateTrimmed)) break;
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(candidateTrimmed)) break;
      paragraphLines.push(candidate);
      i += 1;
    }
    html.push(`<p>${parseInlineMarkdown(paragraphLines.join("\n"))}</p>`);
  }

  return html.join("") || `<p>${escapeHtml(content)}</p>`;
}

function renderScoreBar(score) {
  const pct = Math.round(score * 100);
  return `<div class="citation-score" title="Relevance: ${pct}%">
    <div class="citation-score-bar" style="width: ${pct}%"></div>
  </div>`;
}

function renderCitations(citations) {
  if (!citations || !citations.length) {
    return "";
  }

  const knowledgeCitations = citations.filter((c) => c.type === "knowledge");
  const styleCitations = citations.filter((c) => c.type === "style");

  let html = '<div class="message-citations">';
  html += '<details class="citations-panel" open>';
  html += `<summary class="citations-toggle">
    <svg class="citations-toggle-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
    Sources &amp; Citations
    <span class="citations-count">${citations.length}</span>
  </summary>`;

  // Knowledge sources
  if (knowledgeCitations.length > 0) {
    html += '<div class="citations-section">';
    html += `<p class="citations-label">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
      Knowledge Sources
    </p>`;
    html += '<div class="citations-list">';

    knowledgeCitations.forEach((c) => {
      html += `
        <div class="citation-item citation-knowledge">
          <div class="citation-title">${escapeHtml(c.title || "Untitled")}</div>
          ${c.authors ? `<div class="citation-authors">${escapeHtml(c.authors)}</div>` : ""}
          <div class="citation-meta">
            ${c.journal ? escapeHtml(c.journal) + " &middot; " : ""}
            ${c.year ? escapeHtml(c.year) : ""}
            ${c.pmid ? " &middot; PMID: " + escapeHtml(c.pmid) : ""}
          </div>
          ${renderScoreBar(c.score)}
          ${c.abstract_preview ? `<div class="citation-preview">${escapeHtml(c.abstract_preview)}</div>` : ""}
          ${c.url ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noreferrer" class="citation-link">View source &rarr;</a>` : ""}
        </div>
      `;
    });

    html += '</div></div>';
  }

  // Style sources
  if (styleCitations.length > 0) {
    html += '<div class="citations-section" style="margin-top: 0.75rem;">';
    html += `<p class="citations-label">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"/><line x1="16" y1="8" x2="2" y2="22"/><line x1="17.5" y1="15" x2="9" y2="15"/></svg>
      Style Sources
    </p>`;
    html += '<div class="citations-list">';

    styleCitations.forEach((c) => {
      html += `
        <div class="citation-item citation-style">
          <div class="citation-title">${escapeHtml(c.work || c.figure || "Style source")}</div>
          <div class="citation-meta">
            ${c.figure ? "From " + escapeHtml(c.figure) : ""}
            ${c.tradition ? " &middot; " + escapeHtml(c.tradition) : ""}
          </div>
          ${renderScoreBar(c.score)}
          ${c.abstract_preview ? `<div class="citation-preview">${escapeHtml(c.abstract_preview)}</div>` : ""}
          ${c.url ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noreferrer" class="citation-link">Read original &rarr;</a>` : ""}
        </div>
      `;
    });

    html += '</div></div>';
  }

  html += '</details></div>';
  return html;
}

function renderMessages() {
  // Skip re-render if messages haven't changed
  if (state._messageVersion === state._lastRenderedMessageVersion) return;
  state._lastRenderedMessageVersion = state._messageVersion;

  // Show/hide welcome state
  const hasMessages = state.messages.length > 0;
  el.welcomeState.classList.toggle("hidden", hasMessages);
  el.chatMessages.classList.toggle("hidden", !hasMessages);

  if (!hasMessages) {
    return;
  }

  // Render all messages
  const html = state.messages
    .map((msg) => {
      const isUser = msg.role === "user";
      const isLoading = msg.loading === true;
      const figureName = msg.figure ? state.figures[msg.figure]?.name || msg.figure : "Assistant";
      const authorName = isUser ? "You" : figureName;

      // Get avatar icon
      let avatarContent;
      if (isUser) {
        avatarContent = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" width="18" height="18"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
      } else if (msg.figure) {
        avatarContent = getCharacterIcon(msg.figure);
      } else {
        avatarContent = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>`;
      }

      let contentHtml = "";
      if (isLoading) {
        contentHtml = `
          <div class="loading-dot"></div>
          <div class="loading-dot"></div>
          <div class="loading-dot"></div>
        `;
      } else {
        contentHtml = renderMessageContent(msg.content);
        if (msg.citations && msg.citations.length > 0) {
          contentHtml += renderCitations(msg.citations);
        }
      }

      return `
        <div class="message ${msg.role}">
          <div class="message-avatar">${avatarContent}</div>
          <div class="message-content">
            <div class="message-header">
              <span class="message-author">${escapeHtml(authorName)}</span>
              ${msg.timestamp ? `<span class="message-time">${formatTime(msg.timestamp)}</span>` : ""}
            </div>
            <div class="message-body ${isLoading ? "loading" : ""}">
              ${contentHtml}
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  el.chatMessages.innerHTML = html;

  // Auto-scroll only when a new message is added or user is already near bottom.
  const chatWrapper = document.querySelector(".chat-wrapper");
  if (!chatWrapper) return;

  const distanceFromBottom = chatWrapper.scrollHeight - (chatWrapper.scrollTop + chatWrapper.clientHeight);
  const isNearBottom = distanceFromBottom <= 96;
  if (!state.shouldAutoScroll && !isNearBottom) return;

  state.shouldAutoScroll = false;
  setTimeout(() => {
    chatWrapper.scrollTo({
      top: chatWrapper.scrollHeight,
      behavior: "smooth",
    });
  }, 50);
}

function updateInput() {
  const question = el.questionInput.value;
  const charCount = question.length;
  el.charCount.textContent = `${charCount} / 1200`;

  const isValid = question.trim().length > 0 && charCount <= 1200;
  const canSubmit = !state.loading && state.selectedFigure && isValid;
  el.askBtn.disabled = !canSubmit;
}

function autoResizeTextarea() {
  el.questionInput.style.height = "auto";
  const newHeight = Math.min(Math.max(el.questionInput.scrollHeight, 24), 200);
  el.questionInput.style.height = `${newHeight}px`;
}

function render() {
  renderHealth();
  renderFigures();
  renderMessages();
  updateInput();
}

// API functions
async function checkHealth() {
  try {
    await http("/health");
    state.health = "ok";
  } catch (_) {
    state.health = "down";
  }
  renderHealth();
}

async function loadFigures() {
  try {
    const data = await http("/v1/figures");
    state.figures = data.figures || {};

    // Auto-select first figure if none selected
    if (!state.selectedFigure && Object.keys(state.figures).length > 0) {
      state.selectedFigure = Object.keys(state.figures)[0];
    }

    render();
  } catch (err) {
    setError(err.message || "Could not load figures.");
    render();
  }
}

async function submitQuestion() {
  const question = el.questionInput.value.trim();
  if (!question || !state.selectedFigure) return;

  setError("");

  // Add user message
  state.messages.push({
    role: "user",
    content: question,
    timestamp: Date.now(),
  });
  state.shouldAutoScroll = true;

  // Add loading message
  state.messages.push({
    role: "assistant",
    loading: true,
    content: "",
    figure: state.selectedFigure,
    timestamp: Date.now(),
  });
  state.shouldAutoScroll = true;
  state._messageVersion++;

  // Clear input
  el.questionInput.value = "";
  state.loading = true;
  render();

  try {
    const payload = {
      question: question,
      figure: state.selectedFigure,
    };

    const data = await http("/v1/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    // Remove loading message
    state.messages = state.messages.filter((m) => m.loading !== true);

    // Add assistant response
    state.messages.push({
      role: "assistant",
      content: data.answer || "No response received.",
      citations: data.citations || [],
      figure: state.selectedFigure,
      timestamp: Date.now(),
      meta: data.meta,
    });
    state.shouldAutoScroll = true;
    state._messageVersion++;

    // Update request ID in header
    if (data.meta?.request_id) {
      el.requestId.textContent = data.meta.request_id;
    }

    saveConversation();

  } catch (err) {
    // Remove loading message
    state.messages = state.messages.filter((m) => m.loading !== true);
    state._messageVersion++;
    setError(err.message || "Unable to generate response.");
  } finally {
    state.loading = false;
    render();
  }
}

// Clear conversation
function clearConversation() {
  state.messages = [];
  state._messageVersion++;
  state.error = "";
  el.questionInput.value = "";
  saveConversation();
  render();
  el.questionInput.focus();
}

// Info panel
function openInfoPanel() {
  el.infoDrawer.classList.add("open");
  el.infoDrawer.setAttribute("aria-hidden", "false");
  el.infoOverlay.classList.remove("hidden");
  // Force reflow before adding visible class for transition
  void el.infoOverlay.offsetWidth;
  el.infoOverlay.classList.add("visible");
  el.infoOverlay.setAttribute("aria-hidden", "false");
}

function closeInfoPanel() {
  el.infoDrawer.classList.remove("open");
  el.infoDrawer.setAttribute("aria-hidden", "true");
  el.infoOverlay.classList.remove("visible");
  el.infoOverlay.setAttribute("aria-hidden", "true");
  // Remove hidden after transition completes
  setTimeout(() => {
    if (!el.infoOverlay.classList.contains("visible")) {
      el.infoOverlay.classList.add("hidden");
    }
  }, 400);
}

// Event handlers
function bindEvents() {
  // Info panel
  el.infoToggle.addEventListener("click", openInfoPanel);
  el.infoClose.addEventListener("click", closeInfoPanel);
  el.infoOverlay.addEventListener("click", closeInfoPanel);

  // Theme toggle
  el.themeToggle.addEventListener("click", toggleTheme);

  // New chat button
  el.newChatBtn.addEventListener("click", () => {
    if (state.messages.length > 0) {
      if (confirm("Commence a new scholarly discourse? Current conversation will be archived.")) {
        clearConversation();
      }
    }
  });

  // Figure selection
  el.figureList.addEventListener("click", (event) => {
    const target = event.target.closest("[data-figure]");
    if (!target) return;
    state.selectedFigure = target.getAttribute("data-figure") || "";
    render();
  });

  // Prompt starters
  el.promptList.addEventListener("click", (event) => {
    const target = event.target.closest("[data-prompt]");
    if (!target) return;
    const prompt = target.getAttribute("data-prompt");
    if (prompt) {
      el.questionInput.value = prompt;
      el.questionInput.focus();
      autoResizeTextarea();
      updateInput();
    }
  });

  // Input handling
  el.questionInput.addEventListener("input", () => {
    autoResizeTextarea();
    updateInput();
  });

  // Submit on Enter (without Shift)
  el.questionInput.addEventListener("keydown", async (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!state.loading && !el.askBtn.disabled) {
        await submitQuestion();
      }
    }
  });

  // Form submission
  el.askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.loading || el.askBtn.disabled) return;
    await submitQuestion();
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", (event) => {
    // Cmd/Ctrl + K for new chat
    if ((event.metaKey || event.ctrlKey) && event.key === "k") {
      event.preventDefault();
      if (state.messages.length > 0) {
        clearConversation();
      }
    }
    // Escape to close info panel or focus input
    if (event.key === "Escape") {
      if (el.infoDrawer.classList.contains("open")) {
        closeInfoPanel();
      } else {
        el.questionInput.focus();
      }
    }
  });
}

// Initialize
async function init() {
  initTheme();
  loadConversation();
  renderPromptStarters();
  bindEvents();
  render();

  await Promise.all([checkHealth(), loadFigures()]);

  // Health check interval
  setInterval(checkHealth, 30000);
}

// Start the app
init();
