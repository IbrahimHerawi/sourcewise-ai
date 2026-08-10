import type { User } from "@/lib/api";

type DashboardUserProfile = Pick<User, "first_name" | "last_name">;

function normalizeNamePart(namePart: string): string[] {
  return namePart
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => `${word.charAt(0).toLocaleUpperCase()}${word.slice(1).toLocaleLowerCase()}`);
}

function getNameWords(user: DashboardUserProfile): string[] {
  return [
    ...normalizeNamePart(user.first_name),
    ...normalizeNamePart(user.last_name),
  ];
}

export function formatDashboardUserName(user: DashboardUserProfile): string {
  return getNameWords(user).join(" ");
}

export function getDashboardUserInitials(user: DashboardUserProfile): string {
  const nameWords = getNameWords(user);

  if (nameWords.length === 0) {
    return "";
  }

  const firstInitial = nameWords[0].charAt(0);
  const lastInitial = nameWords.at(-1)?.charAt(0) ?? "";

  return `${firstInitial}${nameWords.length > 1 ? lastInitial : ""}`;
}
