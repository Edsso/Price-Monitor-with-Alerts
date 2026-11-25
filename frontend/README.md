# Front-end

React, Vite, TypeScript, Tailwind CSS e Recharts. O Supabase é usado só para login; os dados
vêm da API.

## Rodar

Copie `.env.example` para `.env.local`, preencha e, com a API no ar:

```powershell
cd frontend
npm install
npm run dev
```

Abra <http://localhost:5173>. Use apenas a chave `sb_publishable_` do Supabase: tudo que começa
com `VITE_` fica visível no navegador.

## Qualidade

```powershell
npm run lint
npm test
npm run build
```

## Confirmação de e-mail

No Supabase, em Authentication > URL Configuration, defina o Site URL como
`http://localhost:5173` (e depois o endereço publicado) para o link de confirmação voltar ao site.
