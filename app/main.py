# Este módulo representa o ponto de entrada da aplicação.
# Ele realiza a configuração da API, integra o banco de dados, registra as rotas do sistema, disponibiliza os recursos visuais do dashboard e renderiza a interface principal utilizada para gerenciamento das cobranças automatizadas.

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import Base, engine
from app.routes import cobrancas


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="W Cobranças",
    description="Sistema de leitura de boletos por OCR e envio de cobranças.",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(cobrancas.router)


@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={}
    )