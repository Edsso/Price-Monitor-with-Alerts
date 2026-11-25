import { useCallback } from "react";
import { Link } from "react-router-dom";
import { useLoad } from "../hooks/useLoad";
import { api } from "../lib/api";
import {
  describeVariation,
  formatPrice,
  reachedTarget,
  STORE_NAMES,
  variation,
} from "../lib/prices";
import type { Product } from "../lib/types";
import { PriceTag } from "./PriceTag";

const DAYS = 30;

export function ProductCard({ product }: { product: Product }) {
  const load = useCallback(
    (signal: AbortSignal) => api.getHistory(product.id, DAYS, signal),
    [product.id],
  );
  const { data: history } = useLoad(load);
  const atTarget = reachedTarget(product);

  return (
    <li className="relative flex flex-col rounded-md border border-line bg-surface focus-within:border-ink hover:border-ink">
      <div className="flex h-44 items-center justify-center p-4">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt=""
            loading="lazy"
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <span className="text-sm text-muted">Sem imagem</span>
        )}
      </div>
      {/* A borda grossa é a beirada da prateleira, onde a etiqueta fica presa. */}
      <div className="flex flex-1 flex-col gap-3 border-t-4 border-line p-4">
        <div>
          <h2 className="line-clamp-2 font-semibold">
            <Link to={`/products/${product.id}`} className="after:absolute after:inset-0">
              {product.title}
            </Link>
          </h2>
          <p className="text-sm text-muted">{STORE_NAMES[product.store]}</p>
        </div>
        <div className="mt-auto space-y-2">
          <PriceTag
            price={product.current_price}
            currency={product.currency}
            highlighted={atTarget}
          />
          <p className={atTarget ? "font-semibold text-good" : ""}>
            {atTarget ? "✓ Chegou ao alvo de " : "Alvo: "}
            {formatPrice(product.target_price, product.currency)}
          </p>
          <p className="min-h-5 text-sm text-muted">
            {history && describeVariation(variation(product.current_price, history), DAYS)}
          </p>
          {!product.is_active && <p className="text-sm font-semibold">Monitoramento pausado</p>}
          {product.last_error && <p className="text-sm text-bad">{product.last_error}</p>}
        </div>
      </div>
    </li>
  );
}
