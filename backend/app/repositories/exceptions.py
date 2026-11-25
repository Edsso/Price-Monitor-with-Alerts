"""Erros do acesso a dados, independentes da biblioteca usada."""


class RepositoryError(Exception):
    """O banco recusou a operação ou está inacessível."""


class DuplicateProductError(RepositoryError):
    """O usuário já monitora essa URL."""
