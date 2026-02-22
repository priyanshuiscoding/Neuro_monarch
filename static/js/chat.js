const chatForm = document.getElementById("chatForm");
const chatWindow = document.getElementById("chatWindow");
const optionTray = document.getElementById("optionTray");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const historyList = document.getElementById("historyList");
const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");

async function parseApiResponse(res) {
  const contentType = (res.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    const payload = await res.json();
    return { payload, rawText: "" };
  }

  const rawText = await res.text();
  return { payload: null, rawText };
}

function appendBubble(role, text) {
  const article = document.createElement("article");
  article.className = `bubble ${role === "user" ? "bubble-user" : "bubble-bot"}`;

  const p = document.createElement("p");
  p.textContent = text;
  article.appendChild(p);

  chatWindow.appendChild(article);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return article;
}

function appendQuestion(text) {
  return appendBubble("bot", text);
}

function setField(name, value) {
  const input = chatForm.querySelector(`[name="${name}"]`);
  if (input) input.value = value;
}

function getField(name) {
  const input = chatForm.querySelector(`[name="${name}"]`);
  return input ? input.value : "";
}

function clearOptions() {
  optionTray.innerHTML = "";
}

function enableTextInput(placeholder) {
  chatInput.disabled = false;
  chatInput.placeholder = placeholder || "Type your message...";
  sendBtn.disabled = false;
  chatInput.focus();
}

function disableTextInput() {
  chatInput.disabled = true;
  sendBtn.disabled = true;
}

function renderOptions(options, onPick) {
  clearOptions();
  options.forEach((item) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "option-chip";
    btn.textContent = item.label;
    btn.addEventListener("click", () => onPick(item));
    optionTray.appendChild(btn);
  });
}

function appendResultCard(host, payload) {
  const card = document.createElement("div");
  card.className = "result-card";

  const suggestionsTitle = document.createElement("p");
  suggestionsTitle.textContent = "Design suggestions:";
  card.appendChild(suggestionsTitle);

  const ul = document.createElement("ul");
  (payload.suggestions || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  });
  card.appendChild(ul);

  const meta = document.createElement("div");
  meta.className = "result-meta";
  meta.innerHTML = `
    <span class="result-pill">${payload.garment_type} | ${payload.print_side}</span>
    <span class="result-pill">Audience: ${payload.audience || "-"}</span>
    <span class="result-pill">Color: ${payload.color || "-"}</span>
    <span class="result-pill">Size: ${payload.size || "-"}</span>
    <span class="result-pill">Style: ${payload.print_style || "-"}</span>
    <span class="result-pill">Cost: INR ${payload.cost_price}</span>
    <span class="result-pill">Sell: INR ${payload.selling_price}</span>
  `;
  card.appendChild(meta);

  if (payload.print_ready_url) {
    const download = document.createElement("a");
    download.href = payload.print_ready_url;
    download.download = "print-ready.png";
    download.textContent = "Download Print-Ready PNG";
    download.className = "print-ready-link";
    card.appendChild(download);
  }

  const images = document.createElement("div");
  images.className = "result-images";

  if (payload.design_url) {
    const designImg = document.createElement("img");
    designImg.src = payload.design_url;
    designImg.alt = "Generated design";
    images.appendChild(designImg);
  }

  if (payload.mockup_url) {
    const mockupImg = document.createElement("img");
    mockupImg.src = payload.mockup_url;
    mockupImg.alt = "Generated t-shirt mockup";
    images.appendChild(mockupImg);
  }

  if (payload.animation_url) {
    const animImg = document.createElement("img");
    animImg.src = payload.animation_url;
    animImg.alt = "Animated mockup preview";
    images.appendChild(animImg);
  }

  card.appendChild(images);
  host.appendChild(card);
}

function renderHistory(items) {
  historyList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "history-empty";
    empty.textContent = "No saved work yet.";
    historyList.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-card";

    const title = document.createElement("p");
    title.className = "history-title";
    title.textContent = `${item.garment_type || "-"} | ${item.print_side || "-"} | ${item.color || "-"}`;
    card.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "history-meta";
    meta.textContent = `${item.created_at || ""} | Size ${item.size || "-"} | ${item.print_style || "-"}`;
    card.appendChild(meta);

    const prompt = document.createElement("p");
    prompt.className = "history-prompt";
    prompt.textContent = item.prompt || "";
    card.appendChild(prompt);

    const images = document.createElement("div");
    images.className = "history-images";

    if (item.mockup_url) {
      const img = document.createElement("img");
      img.src = item.mockup_url;
      img.alt = "History mockup";
      images.appendChild(img);
    }

    if (item.animation_url) {
      const gif = document.createElement("img");
      gif.src = item.animation_url;
      gif.alt = "History animation";
      images.appendChild(gif);
    }

    card.appendChild(images);
    historyList.appendChild(card);
  });
}

async function loadHistory() {
  try {
    const res = await fetch("/history");
    const { payload } = await parseApiResponse(res);
    if (!res.ok || !payload) {
      renderHistory([]);
      return;
    }
    renderHistory(payload.items || []);
  } catch (_) {
    renderHistory([]);
  }
}

async function requestGeneration(messageText) {
  setField("message", messageText);
  const formData = new FormData(chatForm);
  sendBtn.disabled = true;
  sendBtn.textContent = "Generating...";
  try {
    const res = await fetch("/chat", {
      method: "POST",
      body: formData,
    });

    const { payload, rawText } = await parseApiResponse(res);
    if (!res.ok) {
      const msg =
        (payload && payload.error) ||
        `Generation failed (${res.status}). ${rawText ? rawText.slice(0, 220) : "Non-JSON response from server."}`;
      appendBubble("bot", msg);
      return;
    }

    if (!payload) {
      appendBubble("bot", `Generation failed (${res.status}). Server returned non-JSON response.`);
      return;
    }

    const botBubble = appendBubble("bot", payload.assistant_message || "Done.");
    appendResultCard(botBubble, payload);
    await loadHistory();
    askRevisionChoice();
  } catch (err) {
    appendBubble("bot", `Request failed: ${err.message}`);
  } finally {
    sendBtn.textContent = "Send";
  }
}

const flow = [
  {
    id: "audience",
    question: "Who are we designing this item for?",
    options: ["Male", "Female", "Business"],
    apply: (value) => setField("audience", value),
  },
  {
    id: "garment_type",
    question: "What are we designing today?",
    options: ["T-Shirt", "Hoodie"],
    apply: (value) => {
      setField("garment_type", value);
      return true;
    },
  },
  {
    id: "color",
    question: "Pick garment color:",
    options: ["Black", "White"],
    apply: (value) => setField("color", value),
  },
  {
    id: "print_side",
    question: "Print side preference?",
    options: ["Front", "Back"],
    apply: (value) => setField("print_side", value),
  },
  {
    id: "fit",
    question: "What fit would you like?",
    options: ["Regular", "Oversized", "Compressed"],
    apply: (value) => {
      if (value === "Regular") setField("tshirt_type", "Crew Neck");
      if (value === "Oversized") setField("tshirt_type", "Oversized");
      if (value === "Compressed") setField("tshirt_type", "V Neck");
    },
  },
  {
    id: "size",
    question: "Choose a size:",
    options: ["S", "M", "L", "XL", "XXL"],
    apply: (value) => setField("size", value),
  },
  {
    id: "material",
    question: "Select material:",
    options: ["Cotton", "Polyester", "Blend"],
    apply: (value) => setField("material", value),
  },
  {
    id: "print_style",
    question: "Select print style:",
    options: ["Artwork", "Typography"],
    apply: (value) => setField("print_style", value),
  },
];

let flowIndex = 0;
let basePrompt = "";

function askCurrentStep() {
  disableTextInput();
  clearOptions();
  if (flowIndex >= flow.length) {
    appendQuestion("Let's bring your thoughts to reality. Describe your design idea.");
    enableTextInput("Example: Anime couple passionately kissing, dramatic lighting, premium style");
    return;
  }

  const step = flow[flowIndex];
  appendQuestion(`${step.question} Options: ${step.options.join(", ")}`);
  renderOptions(
    step.options.map((label) => ({ label })),
    (item) => {
      appendBubble("user", item.label);
      const result = step.apply(item.label);
      if (result === false) return;
      flowIndex += 1;
      askCurrentStep();
    }
  );
}

function askRevisionChoice() {
  disableTextInput();
  appendQuestion("Would you like to make changes? Options: Yes, No");
  renderOptions(
    [{ label: "Yes" }, { label: "No" }],
    (item) => {
      appendBubble("user", item.label);
      if (item.label === "Yes") {
        appendQuestion("What changes would you like to make?");
        enableTextInput("Example: Make character base form, reduce glow, increase chest coverage");
      } else {
        clearOptions();
        disableTextInput();
        appendQuestion("Great. Final design is ready. You can start a new request by refreshing the page.");
      }
    }
  );
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = (chatInput.value || "").trim();
  if (!text) return;

  appendBubble("user", text);
  chatInput.value = "";
  clearOptions();

  if (flowIndex < flow.length) {
    return;
  }

  if (!basePrompt) {
    basePrompt = text;
    await requestGeneration(basePrompt);
    return;
  }

  // Revision pass.
  const revisedPrompt = `${basePrompt}. Revision request: ${text}`;
  basePrompt = revisedPrompt;
  await requestGeneration(revisedPrompt);
});

askCurrentStep();
loadHistory();

if (refreshHistoryBtn) {
  refreshHistoryBtn.addEventListener("click", loadHistory);
}
