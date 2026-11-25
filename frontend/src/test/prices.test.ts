import { describe, expect, it, test } from "vitest";
import {
  describeVariation,
  lowestPoint,
  parsePriceInput,
  validateProductUrl,
  variation,
} from "../lib/prices";

const points = (...prices: string[]) =>
  prices.map((price) => ({ price, checked_at: "2026-11-25T12:00:00Z" }));

describe("parsePriceInput", () => {
  test.each([
    ["299,90", "299.90"],
    ["R$ 1.234,56", "1234.56"],
    ["1234.56", "1234.56"],
    ["1.234", "1234"],
    ["300", "300"],
    ["0", null],
    ["-5", null],
    ["1,999", null],
    ["1.2.3", null],
    ["abc", null],
    ["", null],
  ])("%s", (text, expected) => expect(parsePriceInput(text)).toBe(expected));
});

describe("validateProductUrl", () => {
  test.each(["https://www.amazon.com.br/dp/1", " https://produto.mercadolivre.com.br/MLB-1 "])(
    "aceita %s",
    (url) => expect(validateProductUrl(url)).toBeNull(),
  );
  test.each([
    "",
    "amazon.com.br/dp/1",
    "https://amazon.com/dp/1",
    "https://amazon.com.br.evil.com",
    "javascript://amazon.com.br/%0aalert(1)",
  ])("rejeita %s", (url) => expect(validateProductUrl(url)).not.toBeNull());
});

describe("variação", () => {
  it("compara o preço atual com o primeiro do período", () => {
    expect(variation("90", points("100", "120"))).toBe(-10);
  });
  it("não existe com menos de dois registros ou sem preço", () => {
    expect(variation("90", points("100"))).toBeNull();
    expect(variation(null, points("100", "90"))).toBeNull();
  });
  test.each([
    [-10.04, "Caiu 10% em 30 dias"],
    [5.26, "Subiu 5,3% em 30 dias"],
    [0.01, "Estável em 30 dias"],
  ])("%d", (value, text) => expect(describeVariation(value, 30)).toBe(text));
});

test("menor preço compara números, não texto", () => {
  expect(lowestPoint(points("100", "99.5", "1000"))?.price).toBe("99.5");
  expect(lowestPoint([])).toBeNull();
});
