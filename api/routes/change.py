from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from ..database import get_db
from ..structs import Owner, Object, ObjectType


router = APIRouter(
    prefix="/change",
    tags=["change"]
)


@router.post("/create/object")
def create_object(object: Object):
    get_db().objects.insert_one(object.model_dump(by_alias=True))
    return {"status": "criado", "id": object.id}

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
    novo_item = Object(
        name=name,
        description=description,
        parent_id=container_id,
        original_parent_id=container_id,
        owner_id=request.session.get("usuario_logado"),
        type=ObjectType.ITEM
    )
    
    # 2. Salva no banco
    get_db().objects.insert_one(novo_item.model_dump(by_alias=True))
    
    # 3. Redireciona de volta para a visualização do container
    return RedirectResponse(url=f"/view/any/{container_id}", status_code=303)


@router.post("/object/{object_id}/move")
def move_item(object_id: str, new_container_id: str = Form(...), next: str = "/view/any/home"):
    """
    Move um objeto mudando apenas o 'container_id' dele.
    """
    # Verifica se o container destino existe
    destino = get_db().objects.find_one({"_id": new_container_id})
    if not destino:
        raise HTTPException(status_code=404, detail="Container destino não existe")

    # Atualiza o objeto
    result = get_db().objects.update_one(
        {"_id": object_id},
        {"$set": {"parent_id": new_container_id}}
    )
    
    if result.modified_count != 0:
        return RedirectResponse(url=next, status_code=303)
    return {"status": "nenhuma alteração feita"}
    

@router.post("/object/{object_id}/return")
def return_object_to_original(object_id: str, next: str = "/view/any/home"):
    """
    Retorna um objeto para seu container original.
    """
    # Busca o objeto
    object = get_db().objects.find_one({"_id": object_id})
    if not object:
        raise HTTPException(status_code=404, detail="Objeto não encontrado")
    
    original_parent_id = object.get("original_parent_id")
    if not original_parent_id:
        raise HTTPException(status_code=400, detail="Objeto não tem container original definido ou apagado")
    
    # Atualiza o objeto para voltar ao container original
    get_db().objects.update_one(
        {"_id": object_id},
        {"$set": {"parent_id": original_parent_id}}
    )
    
    return RedirectResponse(url=next, status_code=303)

@router.post("/object/{object_id}/lend")
def lend_object(request: Request, object_id: str, next: str = "/view/any/home"):
    """
    Empréstimo de um objeto: move o objeto para a mão do usuário logado.
    """
    # Busca o container do usuário logado
    user_id = request.session.get("usuario_logado")
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuário não autenticado")
    
    # Atualiza o objeto para o container do usuário
    result = get_db().objects.update_one(
        {"_id": object_id},
        {"$set": {"parent_id": user_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item não encontrado ou já está com o usuário")
    return RedirectResponse(url=next, status_code=303)
    

@router.delete("/object/{object_id}/delete")
def delete_object(object_id: str):
    """
    Deleta um objeto do inventário.
    """
    obj_raw = get_db().objects.find_one({"_id": object_id})
    if not obj_raw:
        raise HTTPException(status_code=404, detail="Objeto não encontrado")
    
    obj = Object(**obj_raw)
    if obj.type == ObjectType.CONTAINER:
        get_db().objects.update_many(
            {"parent_id": object_id},
            {"$set": {"parent_id": obj.parent_id}}
        )
    
    result = get_db().objects.delete_one({"_id": object_id})
    
    return {"status": "deletado", "id": object_id}

@router.post("/form/create/container")
async def web_create_container(
    request: Request,
    name: str = Form(...),
    parent_id: str = Form(None)):
    """
    Cria um container via formulário Web.
    """
    # 1. Cria o objeto Container
    novo_container = Object(
        name=name,
        parent_id=parent_id,
        original_parent_id=parent_id,
        owner_id=request.session.get("usuario_logado"),
        type=ObjectType.CONTAINER
    )
    
    # 2. Salva no banco
    get_db().objects.insert_one(novo_container.model_dump(by_alias=True))
    
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
        db.items.delete_many({"parent_id": cid})
        
        # Encontra subcontainers
        subcontainers = db.containers.find({"parent_id": cid})
        for sub in subcontainers:
            deletar_recursivamente(sub["_id"])
        
        # Deleta o container atual
        db.containers.delete_one({"_id": cid})
    
    # Inicia a deleção recursiva
    deletar_recursivamente(container_id)
    
    return {"status": "deletado_recursivamente", "id": container_id}

