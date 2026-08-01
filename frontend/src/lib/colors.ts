/** Public SourceWise semantic color tokens available to UI code. */
export type SemanticColorToken =
  | "--sw-color-background-canvas"
  | "--sw-color-background-selected"
  | "--sw-color-background-surface"
  | "--sw-color-background-surface-subtle"
  | "--sw-color-background-upload-halo"
  | "--sw-color-border-default"
  | "--sw-color-border-divider"
  | "--sw-color-border-dropzone"
  | "--sw-color-brand-default"
  | "--sw-color-brand-hover"
  | "--sw-color-focus-ring"
  | "--sw-color-status-destructive-background"
  | "--sw-color-status-destructive-foreground"
  | "--sw-color-status-pending-background"
  | "--sw-color-status-pending-foreground"
  | "--sw-color-status-processing-background"
  | "--sw-color-status-processing-foreground"
  | "--sw-color-status-success-background"
  | "--sw-color-status-success-foreground"
  | "--sw-color-text-disabled"
  | "--sw-color-text-muted-navigation"
  | "--sw-color-text-primary"
  | "--sw-color-text-secondary"
  | "--sw-color-validation-body"
  | "--sw-color-validation-border"
  | "--sw-color-validation-dismiss"
  | "--sw-color-validation-icon";

/** Resolve a semantic CSS token for APIs such as Canvas that cannot consume var(). */
export function resolveSemanticColor(
  element: HTMLElement,
  token: SemanticColorToken,
): string {
  const previousColor = element.style.color;
  element.style.color = `var(${token})`;
  const resolvedColor = getComputedStyle(element).color;
  element.style.color = previousColor;
  return resolvedColor;
}

/** Apply opacity without copying a token's color channels into component code. */
export function colorWithAlpha(color: string, alpha: number): string {
  return `color-mix(in srgb, ${color} ${alpha * 100}%, transparent)`;
}
