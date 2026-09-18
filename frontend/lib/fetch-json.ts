export async function json<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>;
  const detail = await responseDetail(response);
  throw new Error(`API ${response.status} ${detail}`);
}

async function responseDetail(response: Response) {
  try {
    return detailFromBody(await response.json()) || response.statusText;
  } catch {
    return response.statusText;
  }
}

function detailFromBody(body: unknown) {
  const detail = (Object(body) as { detail?: unknown }).detail;
  if (!detail) return "";
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}
