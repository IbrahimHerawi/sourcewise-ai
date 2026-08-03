export const QUESTION_MAX_LENGTH = 4_000;

export function normalizeQuestion(value: string): string {
  return value.trim();
}

export function validateQuestion(value: string): string | undefined {
  const normalized = normalizeQuestion(value);
  if (!normalized) return "Enter a question.";
  if (normalized.length > QUESTION_MAX_LENGTH) {
    return `Question must be ${QUESTION_MAX_LENGTH.toLocaleString()} characters or fewer.`;
  }
  return undefined;
}
