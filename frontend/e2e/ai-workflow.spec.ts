import { expect, test, type Page } from "@playwright/test";

const required = ["E2E_DEPARTMENT_ID", "E2E_ADMIN_USERNAME", "E2E_ADMIN_PASSWORD", "E2E_HEAD_NURSE_USERNAME", "E2E_HEAD_NURSE_PASSWORD"];
const enabled = required.every((name) => Boolean(process.env[name]));
const departmentId = process.env.E2E_DEPARTMENT_ID ?? "";
const year = process.env.E2E_YEAR ?? "2026";
const month = process.env.E2E_MONTH ?? "8";

async function login(page: Page, username: string, password: string): Promise<void> {
  await page.goto("/");
  await page.getByLabel("ชื่อผู้ใช้").fill(username);
  await page.getByLabel("รหัสผ่าน").fill(password);
  await page.getByRole("button", { name: "เข้าสู่ระบบ" }).click();
  await expect(page.getByRole("heading", { name: "ภาพรวมการจัดเวร" })).toBeVisible();
}

async function openSchedule(page: Page): Promise<void> {
  await page.getByRole("button", { name: "ตารางเวร" }).click();
  await page.locator(".toolbar select").first().selectOption(departmentId);
  await page.locator(".toolbar input[type=number]").fill(year);
  await page.locator(".toolbar select").nth(1).selectOption(month);
}

test.describe("AI workflow browser E2E", () => {
  test.skip(!enabled, "Set E2E_* credentials and a seeded isolated test environment to run browser E2E tests");

  test("admin can see generation controls while nurse cannot", async ({ page, browser }) => {
    await login(page, process.env.E2E_ADMIN_USERNAME!, process.env.E2E_ADMIN_PASSWORD!);
    await openSchedule(page);
    await expect(page.getByRole("button", { name: "Generate AI Draft" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve Draft" })).not.toBeVisible();

    const nurseContext = await browser.newContext();
    const nursePage = await nurseContext.newPage();
    await login(nursePage, "integration_nurse", "integration-password");
    await openSchedule(nursePage);
    await expect(nursePage.getByRole("button", { name: "Generate AI Draft" })).not.toBeVisible();
    await nurseContext.close();
  });

  test("head nurse can generate, validate, approve, convert, and publish an AI draft", async ({ page }) => {
    await login(page, process.env.E2E_HEAD_NURSE_USERNAME!, process.env.E2E_HEAD_NURSE_PASSWORD!);
    await openSchedule(page);
    const create = page.getByRole("button", { name: "สร้างตารางเดือนนี้" });
    await expect(create).toBeVisible();
    await create.click();
    await expect(page.locator("#schedule-editor")).toBeVisible();
    await page.getByRole("button", { name: "Generate AI Draft" }).click();
    await expect(page.getByText(/OPTIMAL|FEASIBLE/).first()).toBeVisible();
    await page.getByRole("button", { name: "Validate AI Draft" }).click();
    await expect(page.getByText(/ICU Rules Passed|Passed with warnings/)).toBeVisible();
    await page.getByRole("button", { name: "Submit for Approval" }).click();
    await expect(page.getByRole("button", { name: "Approve Draft" })).toBeVisible();
    await page.getByRole("button", { name: "Approve Draft" }).click();
    await page.getByRole("button", { name: "ส่ง AI Draft ลงตารางฉบับร่าง" }).click();
    await expect(page.getByText(/Manual Schedule Draft #[0-9]+ ถูกสร้างแล้ว/)).toBeVisible();
    await page.getByRole("button", { name: "ตรวจสอบและเผยแพร่ตาราง" }).click();
    await expect(page.locator("#schedule-editor")).toContainText("เผยแพร่แล้ว");
  });
});
