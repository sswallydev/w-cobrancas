# Este módulo é responsável por configurar e gerenciar a conexão entre a aplicação e o banco de dados MySQL utilizando SQLAlchemy.
# Ele cria o mecanismo de conexão (engine) a partir da URL definida nas configurações do sistema.
# Também configura a fábrica de sessões (SessionLocal), que permite realizar consultas, inserções, atualizações e exclusões no banco de dados.
# A classe Base serve como modelo base para todas as tabelas da aplicação.
# A função get_db() controla a abertura e o fechamento das conexões, garantindo o uso adequado dos recursos do banco de dados.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings


engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()