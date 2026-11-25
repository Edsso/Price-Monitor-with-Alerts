"""Erros dos scrapers. Todos herdam de `ScraperError`, para o job tratá-los por produto."""


class ScraperError(Exception):
    """Erro esperado durante a coleta, com mensagem adequada para exibir ao usuário."""


class InvalidUrlError(ScraperError):
    """A URL não é um endereço HTTP(S) válido."""


class UnsupportedStoreError(ScraperError):
    """O domínio da URL não pertence a nenhuma loja suportada."""


class FetchError(ScraperError):
    """A página não pôde ser baixada (rede, timeout ou erro HTTP)."""


class ProductNotFoundError(FetchError):
    """A loja informou que a página não existe."""


class BlockedError(FetchError):
    """A loja recusou o acesso automático (captcha, login ou verificação)."""


class ParseError(ScraperError):
    """A página foi baixada, mas os dados do produto não foram encontrados."""
