import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { supabase } from "../lib/supabase";

export function Layout() {
  const { session } = useAuth();
  return (
    <>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-3">
          <Link to="/" className="price-figures text-2xl">
            Monitor de Preços
          </Link>
          <div className="flex min-w-0 items-center gap-4 text-sm">
            <span className="truncate text-muted">{session?.user.email}</span>
            <button
              type="button"
              className="min-h-11 font-semibold underline underline-offset-4"
              onClick={() => void supabase.auth.signOut({ scope: "local" })}
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </>
  );
}
