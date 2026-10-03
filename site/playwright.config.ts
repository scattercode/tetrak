import { defineConfig } from "@playwright/test";

/**
 * Smoke tests against the built site, matching the approach on scattercode.dev
 * and velostevie: a handful of checks that the page a reader actually receives
 * is intact, rather than that the build exited zero.
 *
 * The server is started here rather than left to the reader. Relying on a
 * hand-started `npm run start` meant the suite would run against a stale server
 * -- or against none -- and still report green, which is the same silent
 * success these tests exist to catch.
 */
export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://localhost:1313/",
  },
  webServer: {
    command: "npm run start",
    url: "http://localhost:1313/",
    // A server already running locally is reused, so the usual edit-and-rerun
    // loop stays fast; CI has none and gets a fresh one.
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  reporter: [["list"]],
});
