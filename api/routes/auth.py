from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware # cookies autenticados
import os
from ..structs import ContainerView, ItemView, Owner
from ..database import get_db, templates
from fastapi import APIRouter, Request

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/login")
async def login(request: Request, nome_usuario: str = Form(...), senha: str = Form(...), cpf_usuario: str = Form(...), proximo_passo: str = Form(...)):
    """
    Recebe o nome do formulário e cria o Cookie.
    """
    # Cria o redirecionamento de volta para o QR Code que ele tentou ler
    SYSTEM_PASSWORD = os.getenv("SYSTEM_PASSWORD", "senha123")

    if senha != SYSTEM_PASSWORD:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "codigo_alvo": proximo_passo, "erro": "Senha incorreta!"}
        )
    
    # Verifica se o usuário já existe pelo CPF
    usuario = get_db().owners.find_one({"cpf": cpf_usuario})
    
    if usuario:
        # Atualiza o nome se o CPF já existe
        get_db().owners.update_one(
            {"cpf": cpf_usuario},
            {"$set": {"name": nome_usuario}}
        )
    else:
        # Cria um novo usuário se o CPF não existe
        usuario_novo = Owner(name=nome_usuario, cpf=cpf_usuario)
        get_db().owners.insert_one(usuario_novo.model_dump(by_alias=True))
        usuario = usuario_novo.model_dump()

    request.session["usuario_logado"] = usuario["_id"]
    proximo_passo = proximo_passo if proximo_passo else "home"
    url_destino = f"/view/any/{proximo_passo}"

    return RedirectResponse(url=url_destino, status_code=303)

@router.get("/login", response_class=HTMLResponse)
def pagina_login(request: Request):
    return templates.TemplateResponse(
        "login.html", 
        context={"request": request, "codigo_alvo": "home", "erro": None}
    )