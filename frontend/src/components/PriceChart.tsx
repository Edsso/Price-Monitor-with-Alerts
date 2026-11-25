import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDate, formatPrice } from "../lib/prices";
import type { PricePoint } from "../lib/types";

interface Props {
  history: PricePoint[];
  targetPrice: string;
  currency: string;
}

const AXIS = { fill: "var(--color-muted)", fontSize: 13 };

export function PriceChart({ history, targetPrice, currency }: Props) {
  const points = history.map((point) => ({
    time: new Date(point.checked_at).getTime(),
    price: Number(point.price),
  }));
  const target = Number(targetPrice);
  const prices = points.map((point) => point.price);
  const minimum = Math.min(...prices, target);
  const maximum = Math.max(...prices, target);
  const shortDate = (time: number) =>
    new Date(time).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  const wholePrice = (price: number) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency,
      maximumFractionDigits: maximum - minimum < 10 ? 2 : 0,
    }).format(price);

  return (
    <div className="h-72" role="img" aria-label="Gráfico do histórico de preços">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--color-line)" />
          <XAxis
            dataKey="time"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={shortDate}
            tick={AXIS}
            tickLine={false}
            axisLine={{ stroke: "var(--color-line)" }}
            minTickGap={40}
          />
          <YAxis
            domain={["auto", "auto"]}
            tickFormatter={wholePrice}
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            width={84}
          />
          <Tooltip
            cursor={{ stroke: "var(--color-muted)" }}
            content={({ active, payload }) => {
              const point = payload?.[0]?.payload as (typeof points)[number] | undefined;
              if (!active || !point) return null;
              return (
                <div className="rounded-md border border-line bg-surface px-3 py-2 text-sm">
                  <p className="font-bold">{formatPrice(point.price, currency)}</p>
                  <p className="text-muted">{formatDate(new Date(point.time).toISOString())}</p>
                </div>
              );
            }}
          />
          <ReferenceLine
            y={target}
            ifOverflow="extendDomain"
            stroke="var(--color-good)"
            strokeDasharray="6 4"
            label={{
              value: `Alvo: ${formatPrice(target, currency)}`,
              position: "insideBottomLeft",
              fill: "var(--color-ink)",
              fontSize: 13,
            }}
          />
          {/* Em degraus: o preço vale até a próxima mudança. */}
          <Line
            type="stepAfter"
            dataKey="price"
            stroke="var(--color-series)"
            strokeWidth={2}
            dot={points.length <= 2 ? { r: 4, fill: "var(--color-series)" } : false}
            activeDot={{ r: 5, stroke: "var(--color-surface)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
