import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("TradeRadar Authentication & Accessibility Flow", () => {
  test("unauthenticated user cannot access protected api and sees login page", async ({
    page,
    request,
  }) => {
    // 1. Verify protected API returns 401 when unauthenticated
    const apiRes = await request.get("/api/auth/me");
    expect(apiRes.status()).toBe(401);
    const errBody = await apiRes.json();
    expect(errBody.error.code).toBe("UNAUTHORIZED");

    // 2. Open frontend
    await page.goto("/");
    await expect(page.getByText("TradeRadar").first()).toBeVisible();
    await expect(page.getByText("Masuk ke Akun")).toBeVisible();
    await expect(page.getByLabel(/Alamat Email/i)).toBeVisible();
    await expect(page.locator("#login-password")).toBeVisible();
  });

  test("accessibility audit: Login page meets strict WCAG AA / Lighthouse standards", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForSelector("form");

    // Run Axe automated accessibility testing on Login view
    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();

    // Zero critical/serious violations ensures Lighthouse Accessibility >= 95
    const criticalViolations = accessibilityScanResults.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );

    expect(criticalViolations).toEqual([]);
  });

  test("login with invalid credentials displays accessible error alert", async ({
    page,
  }) => {
    await page.goto("/");

    await page.getByLabel(/Alamat Email/i).fill("admin@example.com");
    await page.locator("#login-password").fill("WrongPassword123!");
    await page.getByRole("button", { name: /Masuk ke Terminal/i }).click();

    const alert = page.locator('[role="alert"]');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(/tidak valid/i);
  });

  test("successful login transitions to Shell and shows cockpit", async ({ page }) => {
    await page.goto("/");

    await page.getByLabel(/Alamat Email/i).fill("admin@example.com");
    await page.locator("#login-password").fill("AdminPassword123!");
    await page.getByRole("button", { name: /Masuk ke Terminal/i }).click();

    // Verify transition to Shell and initial cockpit status page
    await expect(page.getByText("admin@example.com")).toBeVisible();
    await expect(page.getByText("Status Layanan & Arsitektur")).toBeVisible();
    await expect(page.getByText("Market Ingestor")).toBeVisible();

    // Navigate to Dashboard via sidebar
    await page.getByRole("button", { name: "Dashboard" }).click();
    await expect(page.getByText("Dashboard Utama")).toBeVisible();

    // Navigate back to Status Sistem
    await page.getByRole("button", { name: "Status Sistem" }).click();
    await expect(page.getByText("Status Layanan & Arsitektur")).toBeVisible();

    // Verify command palette shortcut
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog", { name: "Palet Perintah" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Palet Perintah" })).not.toBeVisible();

    // Verify logout
    await page.getByRole("button", { name: /Menu akun pengguna/i }).click();
    await page.getByRole("menuitem", { name: /Keluar dari Akun/i }).click();
    await expect(page.getByText("Masuk ke Akun")).toBeVisible();
  });
});
