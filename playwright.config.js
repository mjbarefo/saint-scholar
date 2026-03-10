const { defineConfig } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const repoPython =
  process.platform === "win32"
    ? path.join(__dirname, ".venv", "Scripts", "python.exe")
    : path.join(__dirname, ".venv", "bin", "python");
const pythonCommand =
  process.env.PLAYWRIGHT_PYTHON || (fs.existsSync(repoPython) ? repoPython : "python");
module.exports = defineConfig({
  testDir: "./tests/ui",
  timeout: 30_000,
  fullyParallel: false,
  outputDir: "output/playwright/test-results",
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "output/playwright/report" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `${pythonCommand} -m uvicorn saint_scholar.api.main:app --app-dir src --host 127.0.0.1 --port 8000`,
    url: "http://127.0.0.1:8000/health",
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    {
      name: "mobile-375",
      use: {
        browserName: "chromium",
        viewport: { width: 375, height: 812 },
      },
    },
    {
      name: "mobile-414",
      use: {
        browserName: "chromium",
        viewport: { width: 414, height: 896 },
      },
    },
  ],
});
