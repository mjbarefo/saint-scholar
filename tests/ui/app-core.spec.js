const { test, expect } = require("@playwright/test");

const FIGURES = {
  buddha: {
    name: "Buddha",
    tradition: "Buddhist",
    tagline: "Observe clearly",
    icon: "lotus",
    color: "#E8A735",
  },
  aurelius: {
    name: "Marcus Aurelius",
    tradition: "Stoic",
    tagline: "Practice discipline",
    icon: "laurel",
    color: "#8B2E2E",
  },
};

const ASK_SUCCESS = {
  answer:
    "Neuroplasticity remains experience-dependent. **Attention** and deliberate practice reinforce adaptive pathways.",
  citations: [
    {
      id: "knowledge-1",
      type: "knowledge",
      score: 0.91,
      title: "Attention and cortical plasticity",
      authors: "A. Researcher, B. Scientist",
      journal: "Journal of Brain Studies",
      year: "2025",
      pmid: "12345678",
      url: "https://pubmed.ncbi.nlm.nih.gov/12345678/",
      abstract_preview: "Focused attention is associated with measurable cortical adaptation.",
    },
    {
      id: "style-1",
      type: "style",
      score: 0.77,
      work: "Meditations on Awareness",
      figure: "Buddha",
      tradition: "Buddhist",
      url: "https://example.com/style-source",
      abstract_preview: "Train the mind and the mind will train perception.",
    },
  ],
  meta: {
    request_id: "req_ui_suite_123456",
    model: "claude-test",
    input_tokens: 111,
    output_tokens: 222,
    latency_ms: 345,
    figure: "buddha",
    knowledge_count: 1,
    style_count: 1,
    generated_at: "2026-03-10T00:00:00Z",
  },
};

async function mockBootstrap(page, options = {}) {
  const {
    health = { status: "ok", service: "saint-scholar-api", checks: {} },
    figures = { figures: FIGURES },
  } = options;

  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(health),
    });
  });

  await page.route("**/v1/figures", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(figures),
    });
  });
}

async function gotoHome(page, options = {}) {
  await mockBootstrap(page, options);
  await page.goto("/");
  await expect(page.locator(".figure-card")).toHaveCount(2);
}

test.describe("core app flows", () => {
  test("renders the landing state and disables submit until the form is valid", async ({
    page,
  }) => {
    await gotoHome(page);

    await expect(page.locator(".brand-title")).toContainText("Saint");
    await expect(page.getByText("Begin Your Inquiry")).toBeVisible();
    await expect(page.locator("#health-badge")).toHaveClass(/status-ok/);
    await expect(page.locator(".figure-card.active")).toContainText("Buddha");
    await expect(page.locator("#prompt-list .prompt-chip")).toHaveCount(4);
    await expect(page.locator("#chat-messages")).toBeHidden();
    await expect(page.locator("#ask-btn")).toBeDisabled();

    await page.locator("#question-input").fill("What changes with deliberate practice?");
    await expect(page.locator("#ask-btn")).toBeEnabled();
    await expect(page.locator("#char-count")).toHaveText("38 / 1200");
  });

  test("toggles theme and restores the saved preference on reload", async ({ page }) => {
    await gotoHome(page);

    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.locator("#theme-toggle").click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });

  test("opens and closes the info drawer", async ({ page }) => {
    await gotoHome(page);

    await page.locator("#info-toggle").click();
    await expect(page.locator("#info-drawer")).toHaveClass(/open/);
    await expect(page.locator("#info-overlay")).toHaveClass(/visible/);
    await expect(page.getByRole("heading", { name: "About Saint & Scholar" })).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.locator("#info-drawer")).not.toHaveClass(/open/);
  });

  test("clicking a suggested prompt hydrates the composer", async ({ page }) => {
    await gotoHome(page);

    const firstPrompt = page.locator("#prompt-list .prompt-chip").first();
    const promptText = await firstPrompt.textContent();

    await firstPrompt.click();
    await expect(page.locator("#question-input")).toHaveValue(promptText || "");
    await expect(page.locator("#ask-btn")).toBeEnabled();
  });

  test("submits a question, renders the response, and stores request metadata", async ({
    page,
  }) => {
    await mockBootstrap(page);

    let capturedPayload = null;
    await page.route("**/v1/ask", async (route) => {
      capturedPayload = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(ASK_SUCCESS),
      });
    });

    await page.goto("/");
    await expect(page.locator(".figure-card")).toHaveCount(2);

    await page.locator("#question-input").fill("How does attention shape neuroplasticity?");
    await page.locator("#ask-btn").click();

    await expect(page.locator("#chat-messages")).toBeVisible();
    await expect(page.locator(".message.user")).toContainText(
      "How does attention shape neuroplasticity?"
    );
    await expect(page.locator(".message.assistant")).toContainText(
      "Neuroplasticity remains experience-dependent."
    );
    await expect(page.locator(".citations-panel")).toBeVisible();
    await expect(page.locator("#request-id")).toHaveText("req_ui_suite_123456");
    await expect(page.locator("#error-banner")).toBeHidden();

    expect(capturedPayload).toEqual({
      question: "How does attention shape neuroplasticity?",
      figure: "buddha",
    });

    const storedConversation = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("saint-scholar-conversation") || "{}")
    );
    expect(storedConversation.selectedFigure).toBe("buddha");
    expect(storedConversation.messages).toHaveLength(2);
    expect(storedConversation.messages[1].citations).toHaveLength(2);
  });

  test("surfaces API errors without leaving a loading message behind", async ({ page }) => {
    await mockBootstrap(page);

    await page.route("**/v1/ask", async (route) => {
      await route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Rate limit exceeded. Please wait before trying again." }),
      });
    });

    await page.goto("/");
    await expect(page.locator(".figure-card")).toHaveCount(2);

    await page.locator("#question-input").fill("Trigger an error path");
    await page.locator("#ask-btn").click();

    await expect(page.locator("#error-banner")).toContainText("Rate limit exceeded");
    await expect(page.locator(".loading-dot")).toHaveCount(0);
    await expect(page.locator(".message.assistant")).toHaveCount(0);
    await expect(page.locator(".message.user")).toHaveCount(1);
  });

  test("new chat clears the persisted conversation after confirmation", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        "saint-scholar-conversation",
        JSON.stringify({
          selectedFigure: "buddha",
          messages: [
            {
              role: "user",
              content: "Saved prompt",
              timestamp: 1,
            },
            {
              role: "assistant",
              content: "Saved answer",
              figure: "buddha",
              timestamp: 2,
            },
          ],
        })
      );
    });

    await gotoHome(page);
    await expect(page.locator(".message")).toHaveCount(2);

    page.once("dialog", async (dialog) => {
      expect(dialog.message()).toContain("Commence a new scholarly discourse?");
      await dialog.accept();
    });

    await page.locator("#new-chat-btn").click();
    await expect(page.locator(".message")).toHaveCount(0);
    await expect(page.getByText("Begin Your Inquiry")).toBeVisible();

    const storedConversation = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("saint-scholar-conversation") || "{}")
    );
    expect(storedConversation.messages).toEqual([]);
  });
});
