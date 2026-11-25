import { type FormEvent, useState } from "react";
import { api, ApiError } from "../lib/api";
import { parsePriceInput, validateProductUrl } from "../lib/prices";
import type { Product } from "../lib/types";
import { ErrorMessage } from "./feedback";

interface FieldErrors {
  url?: string;
  price?: string;
}

export function AddProductForm({ onCreated }: { onCreated: (product: Product) => void }) {
  const [url, setUrl] = useState("");
  const [price, setPrice] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    const urlError = validateProductUrl(url) ?? undefined;
    const target = parsePriceInput(price);
    setFailure(null);
    setFieldErrors({
      url: urlError,
      price: target ? undefined : "Informe um valor, como 299,90",
    });
    if (urlError || !target) return;

    setSaving(true);
    try {
      const product = await api.createProduct(url.trim(), target);
      setUrl("");
      setPrice("");
      onCreated(product);
    } catch (error) {
      setFailure(error instanceof ApiError ? error : new ApiError(0, "Erro inesperado."));
    } finally {
      setSaving(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void save();
  }

  // Repetir só ajuda em falhas temporárias da loja, do servidor ou da rede.
  const canRetry = failure !== null && (failure.status === 0 || failure.status >= 500);

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Adicionar produto" className="space-y-3">
      <div className="grid gap-3 md:grid-cols-[1fr_11rem_auto] md:items-start">
        <div>
          <label htmlFor="url" className="mb-1 block font-semibold">
            Link do produto
          </label>
          <input
            id="url"
            type="url"
            inputMode="url"
            className="field"
            placeholder="https://www.amazon.com.br/dp/…"
            value={url}
            disabled={saving}
            aria-invalid={Boolean(fieldErrors.url)}
            aria-describedby={fieldErrors.url ? "url-error" : undefined}
            onChange={(event) => setUrl(event.target.value)}
          />
          {fieldErrors.url && (
            <p id="url-error" className="mt-1 text-sm text-bad">
              {fieldErrors.url}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="price" className="mb-1 block font-semibold">
            Preço-alvo (R$)
          </label>
          <input
            id="price"
            inputMode="decimal"
            className="field"
            placeholder="299,90"
            value={price}
            disabled={saving}
            aria-invalid={Boolean(fieldErrors.price)}
            aria-describedby={fieldErrors.price ? "price-error" : undefined}
            onChange={(event) => setPrice(event.target.value)}
          />
          {fieldErrors.price && (
            <p id="price-error" className="mt-1 text-sm text-bad">
              {fieldErrors.price}
            </p>
          )}
        </div>
        <button type="submit" className="button button-primary md:mt-7" disabled={saving}>
          {saving ? "Adicionando…" : "Adicionar produto"}
        </button>
      </div>
      {saving && (
        <p role="status" className="text-sm text-muted">
          Buscando o preço na loja. Pode levar até um minuto.
        </p>
      )}
      {failure && (
        <ErrorMessage
          message={failure.message}
          onRetry={canRetry ? () => void save() : undefined}
        />
      )}
    </form>
  );
}
