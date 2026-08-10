import { setAuthSession } from "@/lib/api";

export function installTestAuthSession(accessToken = "test-token"): void {
  setAuthSession({
    access_token: accessToken,
    refresh_token: "test-refresh-token-with-at-least-thirty-two-characters",
    access_token_expires_in: 3_600,
    refresh_token_expires_in: 86_400,
  });
}
