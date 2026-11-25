import { type FormEvent, useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorMessage, Loading } from "../components/feedback";
import { PriceChart } from "../components/PriceChart";
import { PriceTag } from "../components/PriceTag";
import { useLoad } from "../hooks/useLoad";
import { api } from "../lib/api";
import {
  describeVariation,
  formatDate,
  formatPrice,
  lowestPoint,
  parsePriceInput,
  priceInputValue,
  reachedTarget,
  STORE_NAMES,
  variation,
} from "../lib/prices";
import type { PricePoint, Product, ProductChanges } from "../lib/types";

const LOWEST_DAYS = 90;
const PERIODS = [7, 30, 90] as const;

export default function ProductPage() {
  const { id = "" } = useParams();
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [product, history] = await Promise.all([
        api.getProduct(id, signal),
        api.getHistory(id, LOWEST_DAYS, signal),
      ]);
      return { product, history };
    },
    [id],
  );
  const { data, error, loading, reload, setData } = useLoad(load);

  return (
    <>
      <Link to="/" className="inline-flex min-h-11 items-center underline underline-offset-4">
        Voltar aos produtos
      </Link>
      {loading && <Loading />}
      {error && <ErrorMessage message={error.message} onRetry={reload} />}
      {data && (
        <Details
          product={data.product}
          history={data.history}
          onChange={(product) => setData({ ...data, product })}
        />
      )}
    </>
  );
}

interface DetailsProps {
  product: Product;
  history: PricePoint[];
  onChange: (product: Product) => void;
}

function Details({ product, history, onChange }: DetailsProps) {
  const lowest = lowestPoint(history);
  const atTarget = reachedTarget(product);

  return (
    <article className="mt-2 space-y-6">
      <section className="grid gap-6 rounded-md border border-line bg-surface p-4 sm:p-6 md:grid-cols-[14rem_1fr]">
        {product.image_url && (
          <img
            src={product.image_url}
            alt=""
            className="mx-auto max-h-56 max-w-full object-contain"
          />
        )}
        <div className="space-y-4">
          <div>
            <h1 className="max-w-prose text-xl font-bold text-balance sm:text-2xl">
              {product.title}
            </h1>
            <a
              href={product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center underline underline-offset-4"
            >
              Ver na loja {STORE_NAMES[product.store]}
            </a>
          </div>
          <PriceTag
            price={product.current_price}
            currency={product.currency}
            highlighted={atTarget}
            large
          />
          <dl className="grid gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-sm text-muted">Seu alvo</dt>
              <dd className={`font-bold ${atTarget ? "text-good" : ""}`}>
                {formatPrice(product.target_price, product.currency)}
                {atTarget && " (✓ atingido)"}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-muted">Menor preço em {LOWEST_DAYS} dias</dt>
              <dd className="font-bold">
                {lowest ? formatPrice(lowest.price, product.currency) : "Sem registros"}
              </dd>
              {lowest && <dd className="text-sm text-muted">{formatDate(lowest.checked_at)}</dd>}
            </div>
            <div>
              <dt className="text-sm text-muted">Última verificação</dt>
              <dd className="font-bold">
                {product.last_checked_at ? formatDate(product.last_checked_at) : "Ainda não houve"}
              </dd>
            </div>
          </dl>
          {product.last_error && (
            <p className="text-bad">A última verificação falhou: {product.last_error}</p>
          )}
        </div>
      </section>
      <History product={product} history={history} />
      <Settings product={product} onChange={onChange} />
    </article>
  );
}

function History({ product, history }: { product: Product; history: PricePoint[] }) {
  const [days, setDays] = useState<number>(30);
  // Momento de abertura da página: manter fixo evita recalcular o período a cada renderização.
  const [openedAt] = useState(() => Date.now());
  const since = openedAt - days * 86_400_000;
  const visible = history.filter((point) => new Date(point.checked_at).getTime() >= since);

  return (
    <section className="rounded-md border border-line bg-surface p-4 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Histórico de preços</h2>
          <p className="text-muted">
            {describeVariation(variation(product.current_price, visible), days)}
          </p>
        </div>
        <div role="group" aria-label="Período" className="flex gap-2">
          {PERIODS.map((period) => (
            <button
              key={period}
              type="button"
              aria-pressed={days === period}
              className={`button ${days === period ? "button-primary" : "button-quiet"}`}
              onClick={() => setDays(period)}
            >
              {period} dias
            </button>
          ))}
        </div>
      </div>
      {visible.length === 0 ? (
        <p className="py-12 text-center text-muted">Nenhum preço registrado neste período.</p>
      ) : (
        <>
          <PriceChart
            history={visible}
            targetPrice={product.target_price}
            currency={product.currency}
          />
          <details className="mt-4">
            <summary className="min-h-11 cursor-pointer py-2 font-semibold">Ver em tabela</summary>
            <div className="max-h-80 overflow-auto">
              <table className="w-full max-w-md text-left tabular-nums">
                <thead>
                  <tr>
                    <th className="py-1 pr-6">Data</th>
                    <th className="py-1">Preço</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.toReversed().map((point) => (
                    <tr key={point.checked_at} className="border-t border-line">
                      <td className="py-1 pr-6">{formatDate(point.checked_at)}</td>
                      <td className="py-1">{formatPrice(point.price, product.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  );
}

function Settings({ product, onChange }: Omit<DetailsProps, "history">) {
  const navigate = useNavigate();
  const [price, setPrice] = useState(priceInputValue(product.target_price));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  async function run(action: () => Promise<void>) {
    setError(null);
    setSaved(null);
    setBusy(true);
    try {
      await action();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Erro inesperado.");
    } finally {
      setBusy(false);
    }
  }

  const update = (changes: ProductChanges, message: string) =>
    run(async () => {
      onChange(await api.updateProduct(product.id, changes));
      setSaved(message);
    });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const target = parsePriceInput(price);
    if (!target) {
      setSaved(null);
      setError("Informe um valor, como 299,90");
      return;
    }
    void update({ target_price: target }, "Alvo salvo.");
  }

  const remove = () =>
    run(async () => {
      await api.deleteProduct(product.id);
      await navigate("/", { replace: true });
    });

  return (
    <section className="space-y-4 rounded-md border border-line bg-surface p-4 sm:p-6">
      <h2 className="text-lg font-bold">Ajustes</h2>
      <form onSubmit={handleSubmit} noValidate className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <label htmlFor="target" className="mb-1 block font-semibold">
            Preço-alvo (R$)
          </label>
          <input
            id="target"
            inputMode="decimal"
            className="field"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
        </div>
        <button type="submit" className="button button-primary" disabled={busy}>
          Salvar alvo
        </button>
      </form>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="button button-quiet"
          disabled={busy}
          onClick={() =>
            void update(
              { is_active: !product.is_active },
              product.is_active ? "Monitoramento pausado." : "Monitoramento retomado.",
            )
          }
        >
          {product.is_active ? "Pausar monitoramento" : "Retomar monitoramento"}
        </button>
        {confirming ? (
          <>
            <span>O histórico também será apagado.</span>
            <button
              type="button"
              className="button bg-bad text-white"
              disabled={busy}
              onClick={() => void remove()}
            >
              Excluir produto
            </button>
            <button
              type="button"
              className="button button-quiet"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              Cancelar
            </button>
          </>
        ) : (
          <button
            type="button"
            className="button button-quiet text-bad"
            onClick={() => setConfirming(true)}
          >
            Excluir produto
          </button>
        )}
      </div>
      {error && <ErrorMessage message={error} />}
      {saved && (
        <p role="status" className="text-good">
          {saved}
        </p>
      )}
    </section>
  );
}
