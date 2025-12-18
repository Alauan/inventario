from fastapi import Request, HTTPException
from .database import get_db
from .structs import EnrichedObject, Object

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
    

def get_breadcrumbs(object_id: str | None) -> list:
    if not object_id:
        return []
    
    caminho = []
    
    atual_id = object_id
    for _ in range(10):
        if not atual_id:
            break

        obj = get_db().objects.find_one({"_id": atual_id})
        if not obj:
            obj = get_db().owners.find_one({"_id": atual_id})
            if not obj:
                break
            caminho.insert(0, {"_id": obj["_id"], "name": obj["name"]})
            break
        
        caminho.insert(0, {"_id": obj["_id"], "name": obj["name"]}) 
        atual_id = obj.get("parent_id")
        
    return caminho


def enrich_object(object: Object) -> EnrichedObject:
    path = get_breadcrumbs(object.parent_id)
    original_path = get_breadcrumbs(object.original_parent_id)
    
    enriched = EnrichedObject(
        info=object,
        path=path,
        original_path=original_path
    )
    return enriched