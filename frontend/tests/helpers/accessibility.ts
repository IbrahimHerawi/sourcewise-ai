import axe, { type Result } from "axe-core";

export async function getAccessibilityViolations(
  container: Element,
): Promise<Result[]> {
  const results = await axe.run(container, {
    // jsdom does not calculate layout, so axe cannot evaluate color contrast.
    rules: { "color-contrast": { enabled: false } },
  });

  return results.violations;
}
