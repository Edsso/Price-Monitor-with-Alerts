-- Mantém o preço atual e o histórico sempre consistentes, na mesma transação.

-- Primeira coleta: roda no cadastro. É security definer porque o usuário não escreve no histórico.
create function public.record_initial_price() returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
    insert into public.price_history (product_id, price) values (new.id, new.current_price);
    return new;
end;
$$;

revoke execute on function public.record_initial_price() from public, anon, authenticated;

create trigger products_record_initial_price
    after insert on public.products
    for each row when (new.current_price is not null)
    execute function public.record_initial_price();

-- Coletas seguintes: chamada apenas pelo job. Preço nulo significa produto esgotado.
create function public.record_price_check(
    p_product_id uuid,
    p_title text,
    p_image_url text,
    p_price numeric,
    p_currency text
) returns void
language plpgsql security invoker set search_path = ''
as $$
begin
    update public.products
    set title = p_title,
        image_url = coalesce(p_image_url, image_url),
        current_price = p_price,
        currency = p_currency,
        last_checked_at = now(),
        last_error = null
    where id = p_product_id;

    -- O produto pode ter sido excluído durante a coleta.
    if found and p_price is not null then
        insert into public.price_history (product_id, price) values (p_product_id, p_price);
    end if;
end;
$$;

revoke execute on function public.record_price_check(uuid, text, text, numeric, text)
    from public, anon, authenticated;
grant execute on function public.record_price_check(uuid, text, text, numeric, text)
    to service_role;
