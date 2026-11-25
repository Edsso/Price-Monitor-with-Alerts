interface Props {
  price: string | null;
  currency: string;
  highlighted?: boolean;
  large?: boolean;
}

/** Etiqueta de gôndola: fica amarela quando o preço chega ao alvo. */
export function PriceTag({ price, currency, highlighted = false, large = false }: Props) {
  if (price === null) {
    return (
      <p className="w-fit rounded-sm bg-page px-3 py-2 font-semibold text-muted">Esgotado</p>
    );
  }
  const parts = new Intl.NumberFormat("pt-BR", { style: "currency", currency }).formatToParts(
    Number(price),
  );
  const pick = (...types: string[]) =>
    parts
      .filter((part) => types.includes(part.type))
      .map((part) => part.value)
      .join("");
  return (
    <p
      className={`price-figures flex w-fit items-start rounded-sm px-3 py-2 leading-none ${
        highlighted ? "bg-tag" : "bg-page"
      } ${large ? "text-7xl" : "text-5xl"}`}
    >
      <span className="sr-only">{parts.map((part) => part.value).join("")}</span>
      <span aria-hidden className="mt-[0.15em] mr-1 text-[0.4em]">
        {pick("currency")}
      </span>
      <span aria-hidden>{pick("integer", "group")}</span>
      <span aria-hidden className="mt-[0.1em] ml-0.5 text-[0.45em]">
        {pick("decimal", "fraction")}
      </span>
    </p>
  );
}
