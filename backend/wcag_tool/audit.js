#!/usr/bin/env node
/**
 * Runs axe-core against a full HTML document, using jsdom instead of a real
 * browser — no Chromium/Puppeteer download needed, which matters on a
 * disk-constrained dev machine. axe-core's DOM-based ruleset runs fine
 * against jsdom's DOM implementation for the checks NoBar cares about
 * (headings, landmarks, alt text, labels, color-contrast is skipped since
 * jsdom has no real layout engine — that check is noted as skipped, not
 * silently passed).
 *
 * Usage: node audit.js <path-to-html-file>
 * Output: JSON on stdout: { violations: [...], passes_count, serious_or_critical_count }
 */

const fs = require("fs");
const { JSDOM } = require("jsdom");
const axeSource = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

async function main() {
  const htmlPath = process.argv[2];
  if (!htmlPath) {
    console.error("usage: node audit.js <html-file>");
    process.exit(2);
  }
  const html = fs.readFileSync(htmlPath, "utf8");

  const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true });
  dom.window.eval(axeSource);

  // color-contrast requires real rendering/layout, which jsdom does not do.
  // Rather than let it silently report a false pass, disable it explicitly
  // and record that it was skipped so the report is honest about coverage.
  const results = await dom.window.axe.run(dom.window.document, {
    rules: { "color-contrast": { enabled: false } },
  });

  const seriousOrCritical = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical"
  );

  console.log(
    JSON.stringify({
      violations: results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        help: v.help,
        nodes: v.nodes.length,
      })),
      passes_count: results.passes.length,
      violations_count: results.violations.length,
      serious_or_critical_count: seriousOrCritical.length,
      skipped_checks: ["color-contrast (requires real layout engine, not available under jsdom)"],
    })
  );
}

main().catch((err) => {
  console.error(String(err));
  process.exit(1);
});
