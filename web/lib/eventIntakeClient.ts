export const ANNOTATE_LOCATION_FIELDS = ["location_name", "location_address"] as const;

// Localized name/description fields that, once human-confirmed, must be locked
// against AI re-annotation (written to field_corrections by the server).
export const TRANSLATION_LOCK_FIELDS = [
  "name_ja",
  "name_zh",
  "name_en",
  "description_ja",
  "description_zh",
  "description_en",
] as const;

type FormShape = Record<string, unknown>;

export function getActionErrorMessage(error: unknown, fallbackMessage: string) {
  if (
    error instanceof DOMException &&
    (error.name === "AbortError" || error.name === "TimeoutError")
  ) {
    return fallbackMessage;
  }

  if (error instanceof Error) {
    if (error.message.startsWith("Unexpected token")) {
      return fallbackMessage;
    }
    return error.message || fallbackMessage;
  }

  return fallbackMessage;
}

export async function readJsonResponse(res: Response) {
  const responseText = await res.text();
  if (!responseText) return {} as Record<string, unknown>;

  try {
    return JSON.parse(responseText) as Record<string, unknown>;
  } catch {
    return {} as Record<string, unknown>;
  }
}

export function pickReturnedFormFields<T extends FormShape>(
  shape: T,
  fields: Record<string, unknown>,
  ignoreKeys?: readonly string[],
): Partial<T> {
  const ignore = ignoreKeys && ignoreKeys.length ? new Set(ignoreKeys) : null;
  return Object.fromEntries(
    Object.entries(fields).filter(
      ([key, value]) =>
        key in shape &&
        value !== null &&
        value !== undefined &&
        value !== "" &&
        !ignore?.has(key),
    ),
  ) as Partial<T>;
}