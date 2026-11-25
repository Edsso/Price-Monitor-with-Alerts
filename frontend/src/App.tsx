import { lazy, Suspense } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Loading } from "./components/feedback";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { ProductsPage } from "./pages/ProductsPage";

// Separada por causa da biblioteca de gráficos.
const ProductPage = lazy(() => import("./pages/ProductPage"));

function RequireLogin() {
  const { session, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  // A chave descarta os dados em tela quando o usuário muda.
  return <Layout key={session.user.id} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireLogin />}>
        <Route index element={<ProductsPage />} />
        <Route
          path="/products/:id"
          element={
            <Suspense fallback={<Loading />}>
              <ProductPage />
            </Suspense>
          }
        />
        <Route
          path="*"
          element={
            <p>
              Página não encontrada.{" "}
              <Link to="/" className="underline">
                Ver seus produtos
              </Link>
            </p>
          }
        />
      </Route>
    </Routes>
  );
}
