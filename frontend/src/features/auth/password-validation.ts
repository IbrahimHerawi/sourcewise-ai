const MIN_PASSWORD_CHARACTERS = 12;
const MAX_PASSWORD_BYTES = 72;

const LOWERCASE_CHARACTER = /\p{Ll}/u;
const UPPERCASE_CHARACTER = /\p{Lu}/u;
const NUMBER_CHARACTER = /\p{Nd}/u;
const SYMBOL_CHARACTER = /[^\p{L}\p{N}]/u;

export function validatePassword(password: string): string | null {
  const characterCount = Array.from(password).length;
  const byteCount = new TextEncoder().encode(password).length;

  if (characterCount < MIN_PASSWORD_CHARACTERS) {
    return "Password must be at least 12 characters.";
  }
  if (byteCount > MAX_PASSWORD_BYTES) {
    return "Password must be at most 72 bytes.";
  }
  if (
    !LOWERCASE_CHARACTER.test(password) ||
    !UPPERCASE_CHARACTER.test(password) ||
    !NUMBER_CHARACTER.test(password) ||
    !SYMBOL_CHARACTER.test(password)
  ) {
    return "Password must include uppercase, lowercase, number, and symbol characters.";
  }
  return null;
}
