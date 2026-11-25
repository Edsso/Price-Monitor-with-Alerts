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
  create schema extensions; create schema vault; create schema cron; create schema net;
  create table vault.decrypted_secrets (name text, decrypted_secret text);
  create table cron.job (jobname text, schedule text, command text);
  create function cron.schedule(text, text, text) returns bigint language sql as
    $$ insert into cron.job values ($1, $2, $3); select 1::bigint $$;
  create table net.calls (url text, headers jsonb, timeout_ms int);
  create function net.http_post(
    url text, body jsonb, headers jsonb, timeout_milliseconds int
  ) returns bigint language sql as
    $$ insert into net.calls values (url, headers, timeout_milliseconds); select 1::bigint $$;
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
    const sql = await readFile(new URL(file, MIGRATIONS), "utf8");
    // pg_cron e pg_net não existem no PGlite; o stub acima simula as funções usadas.
    await db.exec(sql.replace(/^create extension [^;]+;/gm, ""));
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

test("cron agenda a verificação e chama a API com o segredo", async () => {
  const [job] = (await db.query("select * from cron.job")).rows;
  assert.equal(job.schedule, "17 */6 * * *");
  await db.exec(`insert into vault.decrypted_secrets values
    ('price_monitor_api_url', 'https://api.exemplo.com/'),
    ('price_monitor_cron_secret', 'segredo')`);
  await db.exec(job.command);
  const [call] = (await db.query("select * from net.calls")).rows;
  assert.equal(call.url, "https://api.exemplo.com/jobs/check-prices");
  assert.equal(call.headers["X-Cron-Secret"], "segredo");
});

test("cron não chama a API sem os segredos configurados", async () => {
  await db.exec("select private.request_price_check()");
  assert.equal((await db.query("select * from net.calls")).rows.length, 0);
});

test("usuário não dispara a verificação", async () => {
  for (const role of ["anon", "authenticated"]) {
    await assert.rejects(as(role, "select private.request_price_check()"), /permission denied/);
  }
});
