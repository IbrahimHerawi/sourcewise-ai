import { ApiError } from "@/lib/api";

type ApiObject = Record<string, unknown>;

export function invalidApiResponse(contract: string): never {
  throw new ApiError(
    `The server returned an invalid ${contract} response.`,
    "invalid_response",
    0,
  );
}

export function readApiObject(value: unknown, contract: string): ApiObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidApiResponse(contract);
  }
  return value as ApiObject;
}

export function readApiArray(
  object: ApiObject,
  key: string,
  contract: string,
): unknown[] {
  const value = object[key];
  if (!Array.isArray(value)) return invalidApiResponse(contract);
  return value;
}

export function readApiString(
  object: ApiObject,
  key: string,
  contract: string,
): string {
  const value = object[key];
  if (typeof value !== "string" || value.length === 0) {
    return invalidApiResponse(contract);
  }
  return value;
}

export function readApiText(
  object: ApiObject,
  key: string,
  contract: string,
): string {
  const value = object[key];
  if (typeof value !== "string") return invalidApiResponse(contract);
  return value;
}

export function readApiNullableString(
  object: ApiObject,
  key: string,
  contract: string,
): string | null {
  const value = object[key];
  if (value === null) return null;
  if (typeof value !== "string") return invalidApiResponse(contract);
  return value;
}

export function readApiNumber(
  object: ApiObject,
  key: string,
  contract: string,
): number {
  const value = object[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return invalidApiResponse(contract);
  }
  return value;
}

export function readApiInteger(
  object: ApiObject,
  key: string,
  contract: string,
  minimum = 0,
): number {
  const value = object[key];
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < minimum
  ) {
    return invalidApiResponse(contract);
  }
  return value;
}

export function readApiUuid(
  object: ApiObject,
  key: string,
  contract: string,
): string {
  const value = readApiString(object, key, contract);
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      value,
    )
  ) {
    return invalidApiResponse(contract);
  }
  return value;
}

export function readApiNullableUuid(
  object: ApiObject,
  key: string,
  contract: string,
): string | null {
  if (object[key] === null) return null;
  return readApiUuid(object, key, contract);
}

export function readApiDateTime(
  object: ApiObject,
  key: string,
  contract: string,
): string {
  const value = readApiString(object, key, contract);
  if (Number.isNaN(Date.parse(value))) return invalidApiResponse(contract);
  return value;
}
