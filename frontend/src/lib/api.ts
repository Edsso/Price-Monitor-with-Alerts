import { env } from "./env";
import { supabase } from "./supabase";
import type { PricePoint, Product, ProductChanges } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${env.apiUrl}${path}`, { ...init, headers });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(0, "Não foi possível conectar ao servidor. Verifique sua internet.");
  }
  if (response.status === 401) {
    // A sessão não vale mais: sair leva o usuário de volta ao login.
    await supabase.auth.signOut({ scope: "local" });
    throw new ApiError(401, "Sua sessão expirou. Entre de novo.");
  }
  if (!response.ok) throw new ApiError(response.status, await readError(response));
  return (response.status === 204 ? undefined : await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
  // Em erros de validação, `detail` é uma lista técnica.
  if (typeof detail === "string") return detail;
  return response.status === 422
    ? "Confira os dados informados."
    : "O servidor não respondeu como esperado. Tente de novo.";
}

const json = (method: string, body: object): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export const api = {
  listProducts: (signal?: AbortSignal) => request<Product[]>("/products", { signal }),
  getProduct: (id: string, signal?: AbortSignal) =>
    request<Product>(`/products/${encodeURIComponent(id)}`, { signal }),
  getHistory: (id: string, days: number, signal?: AbortSignal) =>
    request<PricePoint[]>(`/products/${encodeURIComponent(id)}/history?days=${days}`, { signal }),
  createProduct: (url: string, targetPrice: string) =>
    request<Product>("/products", json("POST", { url, target_price: targetPrice })),
  updateProduct: (id: string, changes: ProductChanges) =>
    request<Product>(`/products/${encodeURIComponent(id)}`, json("PATCH", changes)),
  deleteProduct: (id: string) =>
    request<undefined>(`/products/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
