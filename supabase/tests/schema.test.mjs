// Aplica as migrations em um PostgreSQL embutido (PGlite) e testa RLS, privilégios e funções.
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { beforeEach, test } from "node:test";
import { PGlite } from "@electric-sql/pglite";

const ANA = "00000000-0000-0000-0000-00000000000a";
const BIA = "00000000-0000-0000-0000-00000000000b";
const MIGRATIONS = new URL("../migrations/", import.meta.url);

// Imita o mínimo do Supabase, inclusive os privilégios padrão mais permissivos.
const SUPABASE_STUB = `
  create role anon; create role authenticated; create role service_role bypassrls;
  create schema auth;
  create table auth.users (id uuid primary key);
  create function auth.uid() returns uuid language sql stable as
    $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
  grant usage on schema auth, public to anon, authenticated, service_role;
  alter default privileges in schema public
    grant all on tables to anon, authenticated, service_role;
  alter default privileges in schema public
    grant execute on functions to anon, authenticated, service_role;
  insert into auth.users values ('${ANA}'), ('${BIA}');
`;

let db;

async function as(role, sql, params = [], userId = "") {
  return db.transaction(async (tx) => {
    await tx.query("select set_config('request.jwt.claim.sub', $1, true)", [userId]);
    await tx.exec(`set local role ${role}`);
    return (await tx.query(sql, params)).rows;
  });
}
const asUser = (userId, sql, params) => as("authenticated", sql, params, userId);
const asService = (sql, params) => as("service_role", sql, params);

const INSERT = `insert into public.products
  (user_id, url, store, title, target_price, current_price)
  values ($1, $2, 'amazon_br', 'Fone', 90, $3) returning id`;

async function createProduct(userId, { url = "https://amazon.com.br/dp/1", price = 100 } = {}) {
  return (await asUser(userId, INSERT, [userId, url, price]))[0].id;
}

beforeEach(async () => {
  db = await PGlite.create();
  await db.exec(SUPABASE_STUB);
  for (const file of (await readdir(MIGRATIONS)).sort()) {
    await db.exec(await readFile(new URL(file, MIGRATIONS), "utf8"));
  }
});

test("usuário só enxerga os próprios produtos, histórico e alertas", async () => {
  const id = await createProduct(ANA);
  await asService("insert into public.alerts (product_id, price) values ($1, 80)", [id]);
  for (const table of ["products", "price_history", "alerts"]) {
    assert.equal((await asUser(ANA, `select * from public.${table}`)).length, 1, table);
    assert.equal((await asUser(BIA, `select * from public.${table}`)).length, 0, table);
  }
});

test("usuário não altera nem exclui produtos de outro", async () => {
  await createProduct(ANA);
  assert.equal(
    (await asUser(BIA, "update public.products set target_price = 1 returning id")).length, 0);
  assert.equal((await asUser(BIA, "delete from public.products returning id")).length, 0);
  assert.equal((await asUser(ANA, "select * from public.products")).length, 1);
});

test("usuário não cadastra produto em nome de outro", async () => {
  await assert.rejects(
    asUser(BIA, INSERT, [ANA, "https://amazon.com.br/dp/1", 100]), /row-level security/);
});

test("usuário altera preço-alvo, mas não os dados da coleta", async () => {
  await createProduct(ANA);
  const rows = await asUser(
    ANA, "update public.products set target_price = 50, is_active = false returning target_price");
  assert.equal(rows[0].target_price, "50.00");
  for (const change of ["current_price = 1", `user_id = '${BIA}'`, "url = 'https://x'"]) {
    await assert.rejects(
      asUser(ANA, `update public.products set ${change}`), /permission denied/, change);
  }
});

test("usuário não escreve em histórico nem alertas", async () => {
  const id = await createProduct(ANA);
  for (const table of ["price_history", "alerts"]) {
    await assert.rejects(
      asUser(ANA, `insert into public.${table} (product_id, price) values ($1, 1)`, [id]),
      /permission denied/);
    await assert.rejects(asUser(ANA, `delete from public.${table}`), /permission denied/);
  }
});

test("visitante não acessa nada", async () => {
  for (const table of ["products", "price_history", "alerts"]) {
    await assert.rejects(as("anon", `select * from public.${table}`), /permission denied/);
  }
});

test("cadastro registra o primeiro preço, exceto se esgotado", async () => {
  await createProduct(ANA);
  await createProduct(ANA, { url: "https://amazon.com.br/dp/2", price: null });
  const rows = await asUser(ANA, "select price from public.price_history");
  assert.deepEqual(rows, [{ price: "100.00" }]);
});

const CHECK = "select public.record_price_check($1, 'Novo', null, $2, 'BRL')";

test("record_price_check atualiza o produto e o histórico", async () => {
  const id = await createProduct(ANA);
  await asService("update public.products set last_error = 'falhou', image_url = 'img'");
  await asService(CHECK, [id, 79.9]);
  const [product] = await asUser(ANA, "select * from public.products");
  assert.equal(product.current_price, "79.90");
  assert.equal(product.title, "Novo");
  assert.equal(product.image_url, "img");
  assert.equal(product.last_error, null);
  assert.ok(product.last_checked_at);
  assert.equal((await asUser(ANA, "select * from public.price_history")).length, 2);
});

test("record_price_check sem preço não gera histórico", async () => {
  const id = await createProduct(ANA);
  await asService(CHECK, [id, null]);
  assert.equal((await asUser(ANA, "select * from public.products"))[0].current_price, null);
  assert.equal((await asUser(ANA, "select * from public.price_history")).length, 1);
});

test("record_price_check ignora produto excluído", async () => {
  await asService(CHECK, [ANA, 10]);
  assert.equal((await asService("select * from public.price_history")).length, 0);
});

test("usuário não executa record_price_check", async () => {
  const id = await createProduct(ANA);
  await assert.rejects(asUser(ANA, CHECK, [id, 1]), /permission denied/);
});

test("excluir o produto apaga histórico e alertas", async () => {
  const id = await createProduct(ANA);
  await asService("insert into public.alerts (product_id, price) values ($1, 80)", [id]);
  await asUser(ANA, "delete from public.products");
  for (const table of ["price_history", "alerts"]) {
    assert.equal((await asService(`select * from public.${table}`)).length, 0, table);
  }
});

test("restrições rejeitam dados inválidos e URL repetida", async () => {
  await createProduct(ANA);
  await createProduct(BIA);
  await assert.rejects(createProduct(ANA), /duplicate key/);
  await assert.rejects(createProduct(ANA, { url: "ftp://x" }), /check constraint/);
  await assert.rejects(createProduct(ANA, { url: "https://y", price: 0 }), /check constraint/);
});
