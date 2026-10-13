class UserError(Exception):
    """Erro causado pela entrada do usuario; a mensagem e exibida na interface."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SessionNotFound(UserError):
    def __init__(self):
        super().__init__(
            "Sessao expirada por inatividade. Adicione os PDFs novamente.", status_code=404
        )
