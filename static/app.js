const state = {
  sourceFilter: "all",
  history: [],
  kbDocs: [],
  kbFilter: "all",
  isSending: false,
};

const els = {
  sidebar: document.getElementById("sidebar"),
  sidebarBackdrop: document.getElementById("sidebarBackdrop"),
  openSidebarBtn: document.getElementById("openSidebarBtn"),
  closeSidebarBtn: document.getElementById("closeSidebarBtn"),
  newChatBtn: document.getElementById("newChatBtn"),
  sourceTabs: document.querySelectorAll(".source-tab"),
  modelSelect: document.getElementById("modelSelect"),
  statusDot: document.getElementById("statusDot"),
  statDg: document.getElementById("statDg"),
  statWasalt: document.getElementById("statWasalt"),
  statMeta: document.getElementById("statMeta"),
  apiKeySection: document.getElementById("apiKeySection"),
  apiKeyInput: document.getElementById("apiKeyInput"),
  activeScopeBadge: document.getElementById("activeScopeBadge"),
  welcomeState: document.getElementById("welcomeState"),
  messagesList: document.getElementById("messagesList"),
  chatContainer: document.getElementById("chatContainer"),
  chatForm: document.getElementById("chatForm"),
  messageInput: document.getElementById("messageInput"),
  sendBtn: document.getElementById("sendBtn"),
  promptCards: document.querySelectorAll(".prompt-card"),
  openKbBtn: document.getElementById("openKbBtn"),
  kbModal: document.getElementById("kbModal"),
  kbModalBackdrop: document.getElementById("kbModalBackdrop"),
  closeKbBtn: document.getElementById("closeKbBtn"),
  kbModalSubtitle: document.getElementById("kbModalSubtitle"),
  kbSearchInput: document.getElementById("kbSearchInput"),
  kbFilters: document.querySelectorAll(".kb-filter"),
  kbDocsList: document.getElementById("kbDocsList"),
};

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdown(md) {
  const escaped = escapeHtml(md || "");
  const lines = escaped.split("\n");
  let html = "";
  let inList = false;
  let inTable = false;

  const formatInline = (text) =>
    text
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i].trim();

    if (!raw) {
      if (inList) { html += "</ul>"; inList = false; }
      if (inTable) { html += "</tbody></table>"; inTable = false; }
      continue;
    }

    // Markdown table
    if (raw.startsWith("|") && raw.endsWith("|")) {
      const cells = raw.slice(1, -1).split("|").map((c) => c.trim());
      const isSeparator = cells.every((c) => /^[-:]+$/.test(c));
      if (isSeparator) continue;
      if (!inTable) {
        if (inList) { html += "</ul>"; inList = false; }
        html += "<table><thead><tr>" + cells.map((c) => `<th>${formatInline(c)}</th>`).join("") + "</tr></thead><tbody>";
        inTable = true;
      } else {
        html += "<tr>" + cells.map((c) => `<td>${formatInline(c)}</td>`).join("") + "</tr>";
      }
      continue;
    } else if (inTable) {
      html += "</tbody></table>";
      inTable = false;
    }

    // Headings
    if (raw.startsWith("### ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h4>${formatInline(raw.slice(4))}</h4>`;
      continue;
    }
    if (raw.startsWith("## ") || raw.startsWith("# ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h3>${formatInline(raw.replace(/^#+\s+/, ""))}</h3>`;
      continue;
    }

    // Bullet lists
    if (/^[-*•]\s+/.test(raw) || /^\d+\.\s+/.test(raw)) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${formatInline(raw.replace(/^([-*•]|\d+\.)\s+/, ""))}</li>`;
      continue;
    }

    if (inList) { html += "</ul>"; inList = false; }
    html += `<p>${formatInline(raw)}</p>`;
  }

  if (inList) html += "</ul>";
  if (inTable) html += "</tbody></table>";
  return html;
}

function scrollToBottom() {
  els.chatContainer.scrollTop = els.chatContainer.scrollHeight;
}

function appendMessage(role, content, meta = null, isError = false) {
  els.welcomeState.classList.add("hidden");

  const row = document.createElement("div");
  row.className = `msg-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "You" : "AI";

  const bubble = document.createElement("div");
  bubble.className = `msg-bubble${isError ? " error" : ""}`;

  if (role === "user") {
    bubble.textContent = content;
  } else {
    const body = document.createElement("div");
    body.className = "md-body";
    body.innerHTML = renderMarkdown(content);
    bubble.appendChild(body);

    if (meta && !isError) {
      const metaEl = document.createElement("div");
      metaEl.className = "msg-meta";

      if (meta.citations && meta.citations.length > 0) {
        const citesRow = document.createElement("div");
        citesRow.className = "citations-row";
        meta.citations.forEach((c) => {
          const a = document.createElement("a");
          a.className = "citation-chip";
          a.href = c.url || "#";
          a.target = "_blank";
          a.rel = "noopener";
          a.title = `${c.category} — ${c.snippet}`;
          a.innerHTML = `<span class="citation-dot ${c.source}"></span><span>${escapeHtml(c.title)}</span>`;
          citesRow.appendChild(a);
        });
        metaEl.appendChild(citesRow);
      }

      const modelLine = document.createElement("div");
      modelLine.className = "model-pill";
      modelLine.textContent = `Model: ${meta.model_used} · Grounded in ${meta.retrieved_count} scraped passages`;
      metaEl.appendChild(modelLine);

      bubble.appendChild(metaEl);
    }
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  els.messagesList.appendChild(row);
  scrollToBottom();
  return row;
}

function appendTypingIndicator() {
  els.welcomeState.classList.add("hidden");
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  row.innerHTML = `
    <div class="msg-avatar">AI</div>
    <div class="msg-bubble">
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>
  `;
  els.messagesList.appendChild(row);
  scrollToBottom();
  return row;
}

async function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed || state.isSending) return;

  state.isSending = true;
  els.sendBtn.disabled = true;
  els.messageInput.value = "";
  els.messageInput.style.height = "auto";

  appendMessage("user", trimmed);
  const loader = appendTypingIndicator();

  const headers = { "Content-Type": "application/json" };
  const manualKey = els.apiKeyInput.value.trim();
  if (manualKey) {
    headers["X-OpenRouter-Key"] = manualKey;
  }

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers,
      body: JSON.stringify({
        message: trimmed,
        history: state.history.slice(-12),
        source_filter: state.sourceFilter,
        model: els.modelSelect.value || "openrouter/free",
      }),
    });

    const data = await resp.json();
    loader.remove();

    if (!resp.ok) {
      appendMessage("assistant", data.detail || "Something went wrong calling OpenRouter.", null, true);
    } else {
      appendMessage("assistant", data.answer, data, false);
      state.history.push({ role: "user", content: trimmed });
      state.history.push({ role: "assistant", content: data.answer });
    }
  } catch (err) {
    loader.remove();
    appendMessage("assistant", `Network error: ${err.message}`, null, true);
  } finally {
    state.isSending = false;
    els.sendBtn.disabled = false;
    els.messageInput.focus();
  }
}

function renderKbDocs() {
  const q = els.kbSearchInput.value.trim().toLowerCase();
  const filtered = state.kbDocs.filter((doc) => {
    if (state.kbFilter !== "all" && doc.source !== state.kbFilter) return false;
    if (!q) return true;
    const hay = `${doc.title} ${doc.category} ${doc.location || ""} ${doc.brand || ""} ${doc.summary}`.toLowerCase();
    return hay.includes(q);
  });

  if (!filtered.length) {
    els.kbDocsList.innerHTML = `<p class="helper-text">No scraped documents match your filter.</p>`;
    return;
  }

  els.kbDocsList.innerHTML = filtered
    .map((doc) => {
      const badgeClass = doc.source === "darglobal" ? "tag-dg" : "tag-ws";
      const label = doc.source === "darglobal" ? "DarGlobal" : "Wasalt";
      const extras = [doc.category, doc.location, doc.brand].filter(Boolean).join(" · ");
      return `
        <article class="kb-card">
          <div class="kb-card-top">
            <span class="prompt-tag ${badgeClass}">${label}</span>
            <span class="kb-card-meta">${escapeHtml(doc.category)}</span>
          </div>
          <div class="kb-card-title">${escapeHtml(doc.title)}</div>
          ${extras ? `<div class="kb-card-meta">${escapeHtml(extras)}</div>` : ""}
          <p class="kb-card-summary">${escapeHtml(doc.summary)}</p>
          <a href="${escapeHtml(doc.url)}" target="_blank" rel="noopener">View Source &nearr;</a>
        </article>
      `;
    })
    .join("");
}

async function initApp() {
  try {
    const [healthRes, modelsRes, kbRes] = await Promise.all([
      fetch("/api/health"),
      fetch("/api/models"),
      fetch("/api/knowledge"),
    ]);

    if (healthRes.ok) {
      const health = await healthRes.json();
      if (health.openrouter_configured) {
        els.statusDot.textContent = "Ready";
        els.statusDot.classList.remove("warn");
      } else {
        els.statusDot.textContent = "API Key Needed";
        els.statusDot.classList.add("warn");
        els.apiKeySection.classList.remove("hidden");
      }
    }

    if (modelsRes.ok) {
      const models = await modelsRes.json();
      if (models.length) {
        els.modelSelect.innerHTML = models
          .map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.name)}</option>`)
          .join("");
      }
    }

    if (kbRes.ok) {
      const kb = await kbRes.json();
      state.kbDocs = kb.documents || [];
      els.statDg.textContent = kb.darglobal_documents;
      els.statWasalt.textContent = kb.wasalt_documents;
      els.statMeta.textContent = `${kb.total_chunks} indexed RAG chunks · Updated ${kb.scraped_at.slice(0, 10)}`;
      els.kbModalSubtitle.textContent = `${kb.total_documents} scraped documents (${kb.darglobal_documents} DarGlobal, ${kb.wasalt_documents} Wasalt)`;
    }
  } catch (err) {
    els.statusDot.textContent = "Offline";
    els.statusDot.classList.add("warn");
    console.error("Init error:", err);
  }
}

// Event bindings
els.chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(els.messageInput.value);
});

els.messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(els.messageInput.value);
  }
});

els.messageInput.addEventListener("input", () => {
  els.messageInput.style.height = "auto";
  els.messageInput.style.height = `${Math.min(els.messageInput.scrollHeight, 150)}px`;
});

els.promptCards.forEach((btn) => {
  btn.addEventListener("click", () => {
    const prompt = btn.getAttribute("data-prompt");
    if (prompt) sendMessage(prompt);
  });
});

els.sourceTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    els.sourceTabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.sourceFilter = tab.getAttribute("data-source") || "all";
    const labels = {
      all: "Searching: DarGlobal + Wasalt",
      darglobal: "Searching: DarGlobal Only",
      wasalt: "Searching: Wasalt Only",
    };
    els.activeScopeBadge.textContent = labels[state.sourceFilter];
  });
});

els.newChatBtn.addEventListener("click", () => {
  state.history = [];
  els.messagesList.innerHTML = "";
  els.welcomeState.classList.remove("hidden");
  closeMobileSidebar();
});

// Mobile sidebar
function openMobileSidebar() {
  els.sidebar.classList.add("open");
  els.sidebarBackdrop.classList.remove("hidden");
}
function closeMobileSidebar() {
  els.sidebar.classList.remove("open");
  els.sidebarBackdrop.classList.add("hidden");
}
els.openSidebarBtn.addEventListener("click", openMobileSidebar);
els.closeSidebarBtn.addEventListener("click", closeMobileSidebar);
els.sidebarBackdrop.addEventListener("click", closeMobileSidebar);

// Knowledge base modal
els.openKbBtn.addEventListener("click", () => {
  renderKbDocs();
  els.kbModal.classList.remove("hidden");
  closeMobileSidebar();
});
const closeModal = () => els.kbModal.classList.add("hidden");
els.closeKbBtn.addEventListener("click", closeModal);
els.kbModalBackdrop.addEventListener("click", closeModal);
els.kbSearchInput.addEventListener("input", renderKbDocs);

els.kbFilters.forEach((btn) => {
  btn.addEventListener("click", () => {
    els.kbFilters.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.kbFilter = btn.getAttribute("data-kb-source") || "all";
    renderKbDocs();
  });
});

initApp();
