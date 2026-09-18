import { createHash, randomBytes } from "node:crypto";

export const DEVICE_LINK_TTL_SECONDS = 300;
export const DEVICE_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60;

export function digest(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function newSecret(): string {
  return randomBytes(32).toString("base64url");
}

export function validSecret(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]{32,128}$/.test(value);
}

export function sameOriginPost(request: Request): boolean {
  const origin = request.headers.get("origin");
  return !origin || origin === new URL(request.url).origin;
}
