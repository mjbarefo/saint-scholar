const { test, expect } = require("@playwright/test");

const LONG_REQUEST_ID = `req_${"A".repeat(160)}`;
const LONG_TOKEN = `Neuroplasticity${"X".repeat(220)}`;
const LONG_URL = `https://example.com/${"very-long-segment/".repeat(12)}`;

test("mobile layout does not introduce horizontal overflow with long content", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  await page.evaluate(
    ({ requestId, longToken, longUrl }) => {
      const requestIdEl = document.getElementById("request-id");
      if (requestIdEl) {
        requestIdEl.textContent = requestId;
      }

      const promptList = document.getElementById("prompt-list");
      if (promptList) {
        promptList.innerHTML = `
          <button class="prompt-chip" type="button">${longToken}</button>
          <button class="prompt-chip" type="button">${longUrl}</button>
        `;
      }

      const welcomeState = document.getElementById("welcome-state");
      const chatMessages = document.getElementById("chat-messages");
      if (welcomeState) {
        welcomeState.classList.add("hidden");
      }
      if (chatMessages) {
        chatMessages.classList.remove("hidden");
        chatMessages.innerHTML = `
          <div class="message assistant">
            <div class="message-avatar">S</div>
            <div class="message-content">
              <div class="message-header">
                <span class="message-author">Saint Scholar</span>
                <span class="message-time">10:45 PM</span>
              </div>
              <div class="message-body">
                <p>${longToken}</p>
                <p>${longUrl}</p>
              </div>
              <div class="message-citations">
                <details class="citations-panel" open>
                  <summary class="citations-toggle">
                    <span class="citations-count">1 Citation</span>
                  </summary>
                  <div class="citations-section">
                    <div class="citations-list">
                      <div class="citation-item">
                        <div class="citation-title">${longToken}</div>
                        <div class="citation-meta">${longUrl}</div>
                      </div>
                    </div>
                  </div>
                </details>
              </div>
            </div>
          </div>
        `;
      }
    },
    { requestId: LONG_REQUEST_ID, longToken: LONG_TOKEN, longUrl: LONG_URL }
  );

  const overflow = await page.evaluate(() => {
    const viewportWidth = window.innerWidth;
    const rootWidth = document.documentElement.scrollWidth;
    const bodyWidth = document.body.scrollWidth;
    const appWidth = document.querySelector(".app")?.scrollWidth ?? 0;
    const offenders = [
      document.getElementById("request-id"),
      document.querySelector(".prompt-chip"),
      document.querySelector(".message-body"),
      document.querySelector(".citation-title"),
      document.querySelector(".citation-meta"),
    ]
      .filter(Boolean)
      .map((el) => ({
        className: el.className,
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
      }));

    return {
      viewportWidth,
      rootWidth,
      bodyWidth,
      appWidth,
      offenders,
    };
  });

  expect(overflow.rootWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(
    overflow.viewportWidth + 1
  );
  expect(overflow.bodyWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(
    overflow.viewportWidth + 1
  );
  expect(overflow.appWidth, JSON.stringify(overflow)).toBeLessThanOrEqual(
    overflow.viewportWidth + 1
  );

  await page.screenshot({
    path: `output/playwright/mobile-overflow-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
