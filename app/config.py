# Este módulo centraliza todas as configurações da aplicação em um único local.
# Ele carrega automaticamente as variáveis de ambiente armazenadas no arquivo .env.
# Armazena as configurações de conexão com o banco de dados MySQL utilizadas pelo sistema.
# Também gerencia as credenciais e parâmetros necessários para o envio de e-mails via SMTP.
# Dessa forma, facilita a manutenção, aumenta a segurança das informações sensíveis e evita configurações fixas no código.

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str

    class Config:
        env_file = ".env"


settings = Settings()