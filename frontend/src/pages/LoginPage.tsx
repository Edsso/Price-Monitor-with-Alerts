import { type FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ErrorMessage, Loading } from "../components/feedback";
import { PriceTag } from "../components/PriceTag";
import { supabase } from "../lib/supabase";

const MIN_PASSWORD = 8;

const MESSAGES: Record<string, string> = {
  invalid_credentials: "E-mail ou senha incorretos.",
  email_not_confirmed: "Confirme seu e-mail pelo link que enviamos antes de entrar.",
  user_already_exists: "Já existe uma conta com esse e-mail. Entre com sua senha.",
  weak_password: "Escolha uma senha mais forte.",
  email_address_invalid: "Confira o endereço de e-mail.",
  over_email_send_rate_limit: "Muitos e-mails enviados. Espere alguns minutos e tente de novo.",
  over_request_rate_limit: "Muitas tentativas. Espere um pouco e tente de novo.",
};

export function LoginPage() {
  const { session, loading } = useAuth();
  const location = useLocation();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  if (loading) return <Loading />;
  if (session) {
    const from: unknown = (location.state as { from?: unknown } | null)?.from;
    return <Navigate to={typeof from === "string" ? from : "/"} replace />;
  }

  async function send() {
    setError(null);
    setNotice(null);
    if (!email.trim()) return setError("Informe seu e-mail.");
    if (!password) return setError("Informe sua senha.");
    if (isSignUp && password.length < MIN_PASSWORD) {
      return setError(`A senha precisa ter pelo menos ${MIN_PASSWORD} caracteres.`);
    }
    setSending(true);
    try {
      const credentials = { email: email.trim(), password };
      const result = isSignUp
        ? await supabase.auth.signUp({
            ...credentials,
            options: { emailRedirectTo: window.location.origin },
          })
        : await supabase.auth.signInWithPassword(credentials);
      if (result.error) {
        setError(MESSAGES[result.error.code ?? ""] ?? "Não foi possível continuar. Tente de novo.");
      } else if (!result.data.session) {
        setNotice(`Enviamos um link de confirmação para ${credentials.email}.`);
        setIsSignUp(false);
        setPassword("");
      }
    } catch {
      setError("Não foi possível conectar. Verifique sua internet.");
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void send();
  }

  return (
    <main className="mx-auto grid min-h-svh max-w-6xl items-center gap-12 px-4 py-10 md:grid-cols-[1.2fr_1fr]">
      <section>
        <h1 className="price-figures text-5xl leading-[0.95] text-balance sm:text-7xl">
          Diga quanto quer pagar. O aviso chega por e-mail.
        </h1>
        <p className="mt-6 max-w-md text-lg text-muted">
          Cadastre o link de um produto da Amazon ou do Mercado Livre. A etiqueta fica amarela quando
          o preço chega ao seu alvo.
        </p>
        <figure className="mt-8">
          <PriceTag price="289" currency="BRL" highlighted large />
          <figcaption className="mt-2 text-sm text-muted">Exemplo com alvo de R$ 300,00</figcaption>
        </figure>
      </section>
      <section className="rounded-md border border-line bg-surface p-6 sm:p-8">
        <h2 className="text-2xl font-bold">{isSignUp ? "Criar conta" : "Entrar"}</h2>
        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          {notice && (
            <p role="status" className="rounded-md border border-good px-4 py-3 text-good">
              {notice}
            </p>
          )}
          {error && <ErrorMessage message={error} />}
          <div>
            <label htmlFor="email" className="mb-1 block font-semibold">
              E-mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              className="field"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block font-semibold">
              Senha
            </label>
            <input
              id="password"
              type="password"
              autoComplete={isSignUp ? "new-password" : "current-password"}
              className="field"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <button type="submit" className="button button-primary w-full" disabled={sending}>
            {sending ? "Aguarde…" : isSignUp ? "Criar conta" : "Entrar"}
          </button>
        </form>
        <button
          type="button"
          className="mt-4 min-h-11 underline underline-offset-4"
          onClick={() => {
            setIsSignUp(!isSignUp);
            setError(null);
          }}
        >
          {isSignUp ? "Já tenho uma conta" : "Quero criar uma conta"}
        </button>
      </section>
    </main>
  );
}
