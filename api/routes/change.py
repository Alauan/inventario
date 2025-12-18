from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from ..database import get_db
from ..structs import Container, Item, Owner


router = APIRouter(
    prefix="/change",
    tags=["change"]
)


@router.post("/create/container")
def create_container(container: Container):
    get_db().containers.insert_one(container.model_dump(by_alias=True))
    return {"status": "criado", "id": container.id}

@router.post("/create/item")
def create_item(item: Item):
    get_db().items.insert_one(item.model_dump(by_alias=True))
    return {"status": "criado", "id": item.id}

@router.post("/create/owner")
def create_owner(owner: Owner):
    get_db().owners.insert_one(owner.model_dump(by_alias=True))
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
    get_db().items.insert_one(novo_item.model_dump(by_alias=True))
    
    # 3. Redireciona de volta para a visualização do container
    return RedirectResponse(url=f"/view/any/{container_id}", status_code=303)


@router.put("/item/{item_id}/move")
def move_item(item_id: str, new_container_id: str):
    """
    Move um item mudando apenas o 'container_id' dele.
    """
    # Verifica se o container destino existe
    destino = get_db().containers.find_one({"_id": new_container_id})
    if not destino:
        raise HTTPException(status_code=404, detail="Container destino não existe")

    # Atualiza o item
    result = get_db().items.update_one(
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
    item = get_db().items.find_one({"_id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    original_container_id = item.get("original_container_id")
    if not original_container_id:
        raise HTTPException(status_code=400, detail="Item não tem container original definido")
    
    # Atualiza o item para voltar ao container original
    result = get_db().items.update_one(
        {"_id": item_id},
        {"$set": {"container_id": original_container_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Item já está no container original")
        
    return {"status": "retornado", "container_original": original_container_id}

@router.put("/item/{item_id}/lend")
def lend_item(request: Request, item_id: str):
    """
    Empréstimo de um item: move o item para o container do usuário logado.
    """
    # Busca o container do usuário logado
    user_id = request.session.get("usuario_logado")
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuário não autenticado")
    
    # Atualiza o item para o container do usuário
    result = get_db().items.update_one(
        {"_id": item_id},
        {"$set": {"container_id": user_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item não encontrado ou já está com o usuário")
    return {"status": "emprestado", "novo_container": user_id}
    

@router.delete("/item/{item_id}/delete")
def delete_item(item_id: str):
    """
    Deleta um item do inventário.
    """
    result = get_db().items.delete_one({"_id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    return {"status": "deletado", "id": item_id}


@router.post("/container/form/create")
async def web_create_container(
    request: Request,
    name: str = Form(...),
    parent_id: str = Form(None)):
    """
    Cria um container via formulário Web.
    """
    # 1. Cria o objeto Container
    novo_container = Container(
        name=name,
        parent_id=parent_id
    )
    
    # 2. Salva no banco
    get_db().containers.insert_one(novo_container.model_dump(by_alias=True))
    
    # 3. Redireciona de volta para a visualização do container pai ou raiz
    destino = parent_id if parent_id else "home"
    return RedirectResponse(url=f"/view/any/{destino}", status_code=303)

@router.delete("/container/{container_id}/delete_recursive")
def delete_container_recursive(container_id: str):
    """
    Deleta um container e todos os seus itens e subcontainers recursivamente.
    """
    db = get_db()
    
    # Função recursiva para deletar containers e seus conteúdos
    def deletar_recursivamente(cid: str):
        # Deleta todos os itens dentro deste container
        db.items.delete_many({"container_id": cid})
        
        # Encontra subcontainers
        subcontainers = db.containers.find({"parent_id": cid})
        for sub in subcontainers:
            deletar_recursivamente(sub["_id"])
        
        # Deleta o container atual
        db.containers.delete_one({"_id": cid})
    
    # Inicia a deleção recursiva
    deletar_recursivamente(container_id)
    
    return {"status": "deletado_recursivamente", "id": container_id}

@router.delete("/container/{container_id}/delete")
def delete_container(container_id: str):
    """
    Deleta um container e coloca todos os seus itens e subcontainers no container pai.
    """
    db = get_db()
    
    # Busca o container alvo
    container = db.containers.find_one({"_id": container_id})
    if not container:
        raise HTTPException(status_code=404, detail="Container não encontrado")
    
    parent_id = container.get("parent_id")
    
    # Move itens para o container pai (ou raiz se não houver pai)
    db.items.update_many(
        {"container_id": container_id},
        {"$set": {"container_id": parent_id}}
    )
    
    # Move subcontainers para o container pai (ou raiz se não houver pai)
    db.containers.update_many(
        {"parent_id": container_id},
        {"$set": {"parent_id": parent_id}}
    )
    
    # Deleta o container alvo
    db.containers.delete_one({"_id": container_id})
    
    return {"status": "deletado", "id": container_id}


