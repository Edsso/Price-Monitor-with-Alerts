export function Loading({ label = "Carregando" }: { label?: string }) {
  return (
    <p role="status" className="py-16 text-center text-muted">
      {label}…
    </p>
  );
}

export function ErrorMessage({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-bad bg-surface px-4 py-3"
    >
      <p className="text-bad">{message}</p>
      {onRetry && (
        <button type="button" className="button button-quiet" onClick={onRetry}>
          Tentar de novo
        </button>
      )}
    </div>
  );
}
