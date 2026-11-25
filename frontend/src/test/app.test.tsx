import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { AuthContext, type AuthState } from "../auth/AuthContext";
import type { Product } from "../lib/types";

const auth = vi.hoisted(() => ({
  getSession: vi.fn(),
  signOut: vi.fn(),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
}));
vi.mock("../lib/supabase", () => ({ supabase: { auth } }));

const PRODUCT: Product = {
  id: "p1",
  url: "https://www.amazon.com.br/dp/1",
  store: "amazon_br",
  title: "Fone Exemplo",
  image_url: null,
  target_price: "90.00",
  current_price: "100.00",
  currency: "BRL",
  is_active: true,
  last_checked_at: null,
  last_error: null,
  created_at: "2026-11-25T12:00:00Z",
};
const LOGGED = {
  session: { access_token: "jwt", user: { id: "u1", email: "ana@exemplo.com" } },
  loading: false,
} as unknown as AuthState;
const LOGGED_OUT: AuthState = { session: null, loading: false };

type Reply = [status: number, body?: unknown];
let routes: Record<string, Reply[]>;
const calls: { key: string; init: RequestInit }[] = [];

function show(path = "/", state: AuthState = LOGGED) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthContext value={state}>
        <App />
      </AuthContext>
    </MemoryRouter>,
  );
}

async function fillForm(url: string, price: string) {
  await userEvent.type(screen.getByLabelText("Link do produto"), url);
  await userEvent.type(screen.getByLabelText("Preço-alvo (R$)"), price);
  await userEvent.click(screen.getByRole("button", { name: "Adicionar produto" }));
}

beforeEach(() => {
  calls.length = 0;
  routes = { "GET /products": [[200, []]], "GET /products/p1/history": [[200, []]] };
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: LOGGED.session } });
  vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
    const key = `${init.method ?? "GET"} ${new URL(url).pathname}`;
    calls.push({ key, init });
    const queue = routes[key] ?? [[500]];
    const [status, body] = (queue.length > 1 ? queue.shift() : queue[0]) ?? [500];
    return Promise.resolve(new Response(status === 204 ? null : JSON.stringify(body), { status }));
  });
});
afterEach(cleanup);

test("sem login, mostra a tela de entrada", () => {
  show("/", LOGGED_OUT);
  expect(screen.getByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  expect(calls).toHaveLength(0);
});

test("login com senha errada explica o problema", async () => {
  auth.signInWithPassword.mockResolvedValue({ data: {}, error: { code: "invalid_credentials" } });
  show("/login", LOGGED_OUT);
  await userEvent.type(screen.getByLabelText("E-mail"), "ana@exemplo.com");
  await userEvent.type(screen.getByLabelText("Senha"), "errada");
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
});

test("cadastro pede confirmação por e-mail", async () => {
  auth.signUp.mockResolvedValue({ data: { session: null }, error: null });
  show("/login", LOGGED_OUT);
  await userEvent.click(screen.getByRole("button", { name: "Quero criar uma conta" }));
  await userEvent.type(screen.getByLabelText("E-mail"), "ana@exemplo.com");
  await userEvent.type(screen.getByLabelText("Senha"), "senha-longa");
  await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
  expect(await screen.findByRole("status")).toHaveTextContent("ana@exemplo.com");
});

test("lista produtos com preço, alvo e variação", async () => {
  routes["GET /products"] = [[200, [PRODUCT]]];
  routes["GET /products/p1/history"] = [
    [200, ["125.00", "100.00"].map((price) => ({ price, checked_at: "2026-11-25T12:00:00Z" }))],
  ];
  show();
  expect(await screen.findByRole("link", { name: "Fone Exemplo" })).toHaveAttribute(
    "href",
    "/products/p1",
  );
  expect(screen.getByText(/Alvo:/)).toHaveTextContent("90,00");
  expect(await screen.findByText("Caiu 20% em 30 dias")).toBeInTheDocument();
  expect(new Headers(calls[0]?.init.headers).get("Authorization")).toBe("Bearer jwt");
});

test("lista vazia orienta o próximo passo", async () => {
  show();
  expect(await screen.findByText(/Nenhum produto ainda/)).toBeInTheDocument();
});

test("falha ao listar permite tentar de novo", async () => {
  routes["GET /products"] = [[503, { detail: "Serviço indisponível." }], [200, [PRODUCT]]];
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent("Serviço indisponível.");
  await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
  expect(await screen.findByText("Fone Exemplo")).toBeInTheDocument();
});

test("formulário valida antes de enviar", async () => {
  show();
  await fillForm("https://kabum.com.br/x", "abc");
  expect(screen.getByText(/Use um link da Amazon/)).toBeInTheDocument();
  expect(screen.getByText(/Informe um valor/)).toBeInTheDocument();
  expect(calls.some((call) => call.key === "POST /products")).toBe(false);
});

test("falha da loja permite repetir sem redigitar", async () => {
  routes["POST /products"] = [[502, { detail: "A loja recusou." }], [201, PRODUCT]];
  show();
  await screen.findByText(/Nenhum produto ainda/);
  await fillForm(PRODUCT.url, "90,00");
  expect(await screen.findByRole("alert")).toHaveTextContent("A loja recusou.");
  await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
  expect(await screen.findByText("Fone Exemplo")).toBeInTheDocument();
  const posts = calls.filter((call) => call.key === "POST /products");
  expect(posts).toHaveLength(2);
  expect(JSON.parse(posts[1]?.init.body as string)).toEqual({
    url: PRODUCT.url,
    target_price: "90.00",
  });
});

test("produto repetido não oferece nova tentativa", async () => {
  routes["POST /products"] = [[409, { detail: "Este produto já está cadastrado." }]];
  show();
  await fillForm(PRODUCT.url, "90");
  expect(await screen.findByRole("alert")).toHaveTextContent("já está cadastrado");
  expect(screen.queryByRole("button", { name: "Tentar de novo" })).not.toBeInTheDocument();
});

test("sessão expirada sai da conta", async () => {
  routes["GET /products"] = [[401, { detail: "x" }]];
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent("sessão expirou");
  expect(auth.signOut).toHaveBeenCalled();
});

test("página do produto altera o alvo e pede confirmação para excluir", async () => {
  routes["GET /products/p1"] = [[200, PRODUCT]];
  routes["PATCH /products/p1"] = [[200, { ...PRODUCT, target_price: "120.00" }]];
  routes["DELETE /products/p1"] = [[204]];
  show("/products/p1");
  const input = await screen.findByLabelText("Preço-alvo (R$)", {}, { timeout: 10_000 });
  await userEvent.clear(input);
  await userEvent.type(input, "120");
  await userEvent.click(screen.getByRole("button", { name: "Salvar alvo" }));
  expect(await screen.findByText("Alvo salvo.")).toBeInTheDocument();
  expect(screen.getByText(/✓ atingido/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Excluir produto" }));
  expect(calls.some((call) => call.key.startsWith("DELETE"))).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Excluir produto" }));
  expect(await screen.findByText("Seus produtos")).toBeInTheDocument();
}, 20_000);
