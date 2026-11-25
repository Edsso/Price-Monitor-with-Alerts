export type Store = "mercado_livre" | "amazon_br";

/** Produto como a API envia. Os preços vêm como texto, para não perder precisão. */
export interface Product {
  id: string;
  url: string;
  store: Store;
  title: string;
  image_url: string | null;
  target_price: string;
  current_price: string | null;
  currency: string;
  is_active: boolean;
  last_checked_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface PricePoint {
  price: string;
  checked_at: string;
}

export interface ProductChanges {
  target_price?: string;
  is_active?: boolean;
}
