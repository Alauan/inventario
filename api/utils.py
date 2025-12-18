from fastapi import Request, HTTPException
from .database import db

async def verificar_login_global(request: Request):
    # Lista de rotas que são PÚBLICAS (não precisam de login)
    rotas_publicas = [
        "/auth/login",       # A página de login
        "/favicon.ico"    # O ícone do site
    ]
    
    # Se a rota atual for pública, deixa passar
    if request.url.path in rotas_publicas:
        return

    # Verifica se o usuário está na sessão
    usuario = request.session.get("usuario_logado")
    
    if not usuario:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    

def get_breadcrumbs(container_id: str) -> list:
    caminho = []
    atual_id = container_id
    
    for _ in range(10):
        if not atual_id:
            break
        container = db.containers.find_one({"_id": atual_id})
        if not container:
            break
        
        caminho.insert(0, {"id": container["_id"], "nome": container["nome"]}) 
        atual_id = container.get("parent_id")
        
    return caminho
