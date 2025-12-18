from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from ..database import get_db, templates
from ..structs import ContainerView, ItemView, OwnerView, EnrichedItem
from ..utils import get_breadcrumbs

router = APIRouter(
    prefix="/view",
    tags=["view"]
)



# 2. VISUALIZAR (O "Lazy Loading")
# É aqui que seu App vai chamar quando ler o QR Code ou clicar numa pasta.
@router.get("/container/{container_id}", response_model=ContainerView)
def view_container_contents(container_id: str):
    
    # A. Busca os dados do container atual
    container_data = get_db().containers.find_one({"_id": container_id})
    if not container_data:
        raise HTTPException(status_code=404, detail="Container não encontrado")
    
    # B. Busca QUEM ESTÁ DENTRO (Filhos imediatos)
    # Isso é muito rápido porque o MongoDB indexa o campo 'parent_id' e 'container_id'
    subcontainers = list(get_db().containers.find({"parent_id": container_id}))
    items = list(get_db().items.find({"container_id": container_id}))
    
    # C. Gera o caminho (Breadcrumbs) para o usuário saber onde está
    breadcrumbs = get_breadcrumbs(container_id)

    # D. Monta o pacote de resposta
    return {
        "info": container_data,
        "subcontainers": subcontainers,
        "current_items": items,
        "path": breadcrumbs
    }

@router.get(path="/item/{item_id}", response_model=ItemView)
def view_item_contents(item_id: str):
    # A. Busca os dados do item atual
    item_data = get_db().items.find_one({"_id": item_id})
    if not item_data:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    # B. Gera o caminho (Breadcrumbs) do container atual
    container_path = get_breadcrumbs(item_data.get("container_id"))
    
    # C. Gera o caminho (Breadcrumbs) do container original
    original_container_path = get_breadcrumbs(item_data.get("original_container_id"))
    
    # D. Busca o nome do proprietário, se houver
    owner_name = None
    owner_id = item_data.get("owner_id")
    if owner_id:
        owner = get_db().owners.find_one({"_id": owner_id}, {"_id": 0, "nome": 1})
        if owner:
            owner_name = owner["nome"]
    
    # E. Monta o pacote de resposta
    return {
        "info": item_data,
        "container_path": container_path,
        "original_container_path": original_container_path,
        "owner_name": owner_name
    }

@router.get("/owner/{owner_id}", response_model=OwnerView)
def view_owner_contents(owner_id: str):
    # A. Busca os dados do owner atual
    owner_data = get_db().owners.find_one({"_id": owner_id})
    if not owner_data:
        raise HTTPException(status_code=404, detail="Owner não encontrado")
    
    # B. Itens que estão FISICAMENTE com o owner
    held_items = list(get_db().items.find({"container_id": owner_id}))
    
    # C. Itens que PERTENCEM ao owner (com dados extras)
    owned_items_raw = list(get_db().items.find({"owner_id": owner_id}))
    owned_items = []
    for item in owned_items_raw:
        path = get_breadcrumbs(item.get("container_id"))
        is_lent = (item.get("container_id") != item.get("original_container_id"))
        enriched_item = EnrichedItem(**item, path=path, is_lent=is_lent)
        owned_items.append(enriched_item)
    # D. Containers raiz (sem pai)
    root_containers = list(get_db().containers.find({"parent_id": None}))
    # E. Monta o pacote de resposta
    return {
        "info": owner_data,
        "held_items": held_items,
        "owned_items": owned_items,
        "root_containers": root_containers
    }



@router.get("/any/{codigo}", response_class=HTMLResponse)
async def ler_qr_code(request: Request, codigo: str):
    if codigo == "home":
        owner_id = request.session.get("usuario_logado")
        if not owner_id:
            return RedirectResponse(url="/auth/login", status_code=303)
        data = view_owner_contents(owner_id)
        return templates.TemplateResponse("owner.html", {"request": request, "owner_view": data})

    # 1. Tenta achar como ITEM
    item_check = get_db().items.find_one({"_id": codigo})
    if item_check:
        # Reutiliza a lógica de visualização de item
        data = view_item_contents(codigo)
        return templates.TemplateResponse("item.html", {"request": request, "item_view": data})

    # 2. Tenta achar como CONTAINER
    container_check = get_db().containers.find_one({"_id": codigo})
    if container_check:
        # Reutiliza a lógica de visualização de container
        data = view_container_contents(codigo)
        return templates.TemplateResponse("container.html", {"request": request, "container_view": data})

    owner_check = get_db().owners.find_one({"_id": codigo})
    if owner_check:
        # Reutiliza a lógica de visualização de owner
        data = view_owner_contents(codigo)
        return templates.TemplateResponse("owner.html", {"request": request, "owner_view": data})

    # 3. Não encontrou nada
    return HTMLResponse("<h1>Código não encontrado no sistema.</h1>", status_code=404)
