from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from ..database import db
from ..structs import Container, Item, Owner


router = APIRouter(
    prefix="/change",
    tags=["change"]
)


@router.post("/create/container")
def create_container(container: Container):
    db.containers.insert_one(container.model_dump(by_alias=True))
    return {"status": "criado", "id": container.id}

@router.post("/create/item")
def create_item(item: Item):
    db.items.insert_one(item.model_dump(by_alias=True))
    return {"status": "criado", "id": item.id}

@router.post("/create/owner")
def create_owner(owner: Owner):
    db.owners.insert_one(owner.model_dump(by_alias=True))
    return {"status": "criado", "id": owner.id}


@router.post("/form/create/item")
async def web_create_item(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    container_id: str = Form(...)):
    """
    Cria um item via formulário Web, definindo a origem e localização atual
    como o container onde o botão foi clicado.
    """
    # 1. Cria o objeto Item
    # Nota: Definimos tanto container_id quanto original_container_id
    novo_item = Item(
        name=name,
        description=description,
        container_id=container_id,
        original_container_id=container_id,
        owner_id=request.session.get("usuario_logado")
    )
    
    # 2. Salva no banco
    db.items.insert_one(novo_item.model_dump(by_alias=True))
    
    # 3. Redireciona de volta para a visualização do container
    return RedirectResponse(url=f"/access/{container_id}", status_code=303)


@router.put("/item/{item_id}/move")
def move_item(item_id: str, new_container_id: str):
    """
    Move um item mudando apenas o 'container_id' dele.
    """
    # Verifica se o container destino existe
    destino = db.containers.find_one({"_id": new_container_id})
    if not destino:
        raise HTTPException(status_code=404, detail="Container destino não existe")

    # Atualiza o item
    result = db.items.update_one(
        {"_id": item_id},
        {"$set": {"container_id": new_container_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item não encontrado ou já estava lá")
        
    return {"status": "movido", "novo_local": new_container_id}

@router.put("/item/{item_id}/return")
def return_item_to_original(item_id: str):
    """
    Retorna um item para seu container original.
    """
    # Busca o item
    item = db.items.find_one({"_id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    original_container_id = item.get("original_container_id")
    if not original_container_id:
        raise HTTPException(status_code=400, detail="Item não tem container original definido")
    
    # Atualiza o item para voltar ao container original
    result = db.items.update_one(
        {"_id": item_id},
        {"$set": {"container_id": original_container_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Item já está no container original")
        
    return {"status": "retornado", "container_original": original_container_id}
