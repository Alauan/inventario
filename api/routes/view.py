from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from ..database import get_db, templates
from ..structs import ContainerView, ItemView, OwnerView, EnrichedObject, Owner, Object, ObjectType
from ..utils import get_breadcrumbs, enrich_object

router = APIRouter(
    prefix="/view",
    tags=["view"]
)



# 2. VISUALIZAR (O "Lazy Loading")
# É aqui que seu App vai chamar quando ler o QR Code ou clicar numa pasta.
@router.get("/container/{container_id}", response_model=ContainerView)
def view_container_contents(request: Request, container_id: str):
    container_data = get_db().objects.find_one({"_id": container_id})
    if not container_data:
        raise HTTPException(status_code=404, detail="Container não encontrado")
    
    all_objects = list(get_db().objects.find({
        "$or": [
            {"parent_id": container_id},
            {"original_parent_id": container_id}
        ]
    }))

    items = [item for item in all_objects if item.get("parent_id") == container_id and item.get("type") == "item"]
    subcontainers = [cont for cont in all_objects if cont.get("parent_id") == container_id and cont.get("type") == "container"]

    owned_items = [enrich_object(Object(**item)) for item in all_objects if item.get("original_parent_id") == container_id and item.get("parent_id") != container_id and item.get("type") == "item"]
    owned_subcontainers = [enrich_object(Object(**cont)) for cont in all_objects if cont.get("original_parent_id") == container_id and cont.get("parent_id") != container_id and cont.get("type") == "container"]
    owner_id = request.session.get("usuario_logado")
    held_objects = list(get_db().objects.find({"parent_id": owner_id}))
    breadcrumbs = get_breadcrumbs(container_id)

    return ContainerView(
        info=Object(**container_data),
        subcontainers=subcontainers,
        current_items=items,
        owned_items=owned_items,
        owned_subcontainers=owned_subcontainers,
        held_objects=held_objects,
        path=breadcrumbs
    )

@router.get(path="/item/{item_id}", response_model=ItemView)
def view_item_contents(item_id: str):
    # A. Busca os dados do item atual
    item_data = get_db().objects.find_one({"_id": item_id})
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
        owner = get_db().owners.find_one({"_id": owner_id}, {"_id": 0, "name": 1})
        if owner:
            owner_name = owner["name"]
    
    # E. Monta o pacote de resposta
    return ItemView(
        info=Object(**item_data),
        container_path=container_path,
        original_container_path=original_container_path,
        owner_name=owner_name
    )

@router.get("/owner/{owner_id}", response_model=OwnerView)
def view_owner_contents(owner_id: str):
    # A. Busca os dados do owner atual
    owner_data = get_db().owners.find_one({"_id": owner_id})
    if not owner_data:
        raise HTTPException(status_code=404, detail="Owner não encontrado")
    
    # B. Itens que estão FISICAMENTE com o owner
    held_objects_raw = list(get_db().objects.find({"parent_id": owner_id}))
    held_objects = []
    for object_dict in held_objects_raw:
        path = [{"_id": owner_data["_id"], "name": owner_data["name"]}]
        item_obj = Object(**object_dict)
        
        item_view = EnrichedObject(
            info=item_obj,
            path=path,
            original_path=get_breadcrumbs(object_dict.get("original_parent_id"))
        )
        held_objects.append(item_view)
    
    # C. Itens que PERTENCEM ao owner (com dados extras)
    owned_objects_raw = list(get_db().objects.find({"owner_id": owner_id}))
    owned_objects = []
    in_place_objects = []
    for object_dict in owned_objects_raw:
        if object_dict.get("type") != ObjectType.ITEM:
            continue
        enriched_object = enrich_object(Object(**object_dict))
        if enriched_object.is_out_of_place:
            owned_objects.append(enriched_object)
        else:
            in_place_objects.append(enriched_object)

    owned_objects.extend(in_place_objects)
    # D. Containers raiz (sem pai)
    root_containers = list(get_db().objects.find({"parent_id": None}))
    
    # E. Monta o pacote de resposta
    return OwnerView(
        info=Owner(**owner_data),
        held_objects=held_objects,
        owned_objects=owned_objects,
        root_containers=root_containers
    )


@router.get("/any/{codigo}", response_class=HTMLResponse)
async def ler_qr_code(request: Request, codigo: str):
    # 1. Se for "home", redireciona para o owner logado
    if codigo == "home":
        owner_id = request.session.get("usuario_logado")
        if not owner_id:
            return RedirectResponse(url="/auth/login", status_code=303)
        data = view_owner_contents(owner_id)
        return templates.TemplateResponse("owner.html", {"request": request, "owner_view": data})

    # 2. Tenta encontrar o código em objetos
    object_check = get_db().objects.find_one({"_id": codigo})
    if object_check:
        obj = Object(**object_check)
        if obj.type == ObjectType.CONTAINER:
            data = view_container_contents(request, codigo)
            return templates.TemplateResponse("container.html", {"request": request, "container_view": data})
        
        data = view_item_contents(codigo)
        return templates.TemplateResponse("item.html", {"request": request, "item_view": data})

    # 3. Tenta encontrar o código em owners
    owner_check = get_db().owners.find_one({"_id": codigo})
    if owner_check:
        # Reutiliza a lógica de visualização de owner
        data = view_owner_contents(codigo)
        return templates.TemplateResponse("owner.html", {"request": request, "owner_view": data})

    # 3. Não encontrou nada
    return HTMLResponse("<h1>Código não encontrado no sistema.</h1>", status_code=404)
