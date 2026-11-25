import { AddProductForm } from "../components/AddProductForm";
import { ErrorMessage, Loading } from "../components/feedback";
import { ProductCard } from "../components/ProductCard";
import { useLoad } from "../hooks/useLoad";
import { api } from "../lib/api";

export function ProductsPage() {
  const { data: products, error, loading, reload, setData } = useLoad(api.listProducts);

  return (
    <div className="space-y-8">
      <h1 className="price-figures text-4xl">Seus produtos</h1>
      <AddProductForm
        onCreated={(product) => (products ? setData([product, ...products]) : reload())}
      />
      {loading && <Loading />}
      {error && <ErrorMessage message={error.message} onRetry={reload} />}
      {products?.length === 0 && (
        <p className="rounded-md border border-dashed border-muted px-4 py-16 text-center">
          Nenhum produto ainda. Cole um link acima para começar a acompanhar.
        </p>
      )}
      {products && products.length > 0 && (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </ul>
      )}
    </div>
  );
}
