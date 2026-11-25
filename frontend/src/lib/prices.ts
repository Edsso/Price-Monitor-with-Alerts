import type { PricePoint, Product } from "./types";

export const STORE_NAMES = { amazon_br: "Amazon", mercado_livre: "Mercado Livre" } as const;

const DOMAINS = ["mercadolivre.com.br", "amazon.com.br"];

export function formatPrice(price: string | number, currency: string): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(Number(price));
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/** Lê um preço digitado (`1.234,56`, `1234,56` ou `1234.56`) no formato da API. */
export function parsePriceInput(text: string): string | null {
  let value = text.replace(/R\$|\s/g, "");
  if (value.includes(",") || /^\d{1,3}(\.\d{3})+$/.test(value)) {
    if (!/^(\d+|\d{1,3}(\.\d{3})+)(,\d{1,2})?$/.test(value)) return null;
    value = value.replaceAll(".", "").replace(",", ".");
  }
  if (!/^\d{1,10}(\.\d{1,2})?$/.test(value) || Number(value) <= 0) return null;
  return value;
}

export function priceInputValue(price: string): string {
  return Number(price).toFixed(2).replace(".", ",");
}

export function reachedTarget(product: Product): boolean {
  return (
    product.current_price !== null && Number(product.current_price) <= Number(product.target_price)
  );
}

/** Variação percentual do preço atual em relação ao primeiro do período. */
export function variation(currentPrice: string | null, history: PricePoint[]): number | null {
  const first = history[0];
  if (currentPrice === null || !first || history.length < 2) return null;
  return ((Number(currentPrice) - Number(first.price)) / Number(first.price)) * 100;
}

export function describeVariation(percent: number | null, days: number): string {
  if (percent === null) return "Ainda sem variação para comparar";
  const rounded = Math.abs(percent).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  if (rounded === "0") return `Estável em ${days} dias`;
  return `${percent < 0 ? "Caiu" : "Subiu"} ${rounded}% em ${days} dias`;
}

export function lowestPoint(history: PricePoint[]): PricePoint | null {
  return history.reduce<PricePoint | null>(
    (lowest, point) => (!lowest || Number(point.price) < Number(lowest.price) ? point : lowest),
    null,
  );
}

/** Devolve a mensagem de erro da URL, ou `null` se ela for aceita. */
export function validateProductUrl(text: string): string | null {
  let url: URL;
  try {
    url = new URL(text.trim());
  } catch {
    return "Cole o endereço completo do produto, começando com https://";
  }
  const supported = DOMAINS.some(
    (domain) => url.hostname === domain || url.hostname.endsWith(`.${domain}`),
  );
  if (!/^https?:$/.test(url.protocol) || !supported) {
    return "Use um link da Amazon Brasil ou do Mercado Livre";
  }
  return null;
}
