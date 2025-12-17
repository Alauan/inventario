from typing import Optional, List, Any
from pydantic import BaseModel, Field
import uuid

# --- MODELOS ---

class Item(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nome: str
    proprietario: Optional['Owner'] = Field(default=None, exclude=True)
    container_atual: Optional['Container'] = Field(default=None, exclude=True)

class Owner(BaseModel):
    nome: str
    cpf: str
    held_container_id: str
    owned_items_ids: List[str] = Field(default_factory=list)
    held_container: Optional['Container'] = Field(default=None, exclude=True)
    owned_items: List[Item] = Field(default_factory=list, exclude=True)

class Container(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nome: str
    items_ids: List[str] = Field(default_factory=list)
    owned_items_ids: List[str] = Field(default_factory=list)
    subcontainers_ids: List[str] = Field(default_factory=list)

    parent_id: Optional[str] = Field(default=None, exclude=True)
    items: List[Item] = Field(default_factory=list, exclude=True)
    owned_items: List[Item] = Field(default_factory=list, exclude=True)
    subcontainers: List['Container'] = Field(default_factory=list, exclude=True)
    parent_container: Optional['Container'] = Field(default=None, exclude=True)

class System(BaseModel):
    owner_cpfs: List[str] = Field(default_factory=list)
    root_container_ids: List[str] = Field(default_factory=list)

    owners: List[Owner] = Field(default_factory=list, exclude=True)
    root_containers: List[Container] = Field(default_factory=list, exclude=True)


# --- LÓGICA DE NEGÓCIO ---
def find_container_by_id(container: Container, container_id: str) -> Optional[Container]:
    if container.id == container_id:
        return container
    for sub in container.subcontainers:
        resultado = find_container_by_id(sub, container_id)
        if resultado:
            return resultado
    return None

def move_item(item: Item, novo_container: Container):
    if item.container_atual:
        old_container = item.container_atual
        if item.id in old_container.items_ids:
            old_container.items_ids.remove(item.id)
            old_container.items = [i for i in old_container.items if i.id != item.id]

    novo_container.items.append(item)
    novo_container.items_ids.append(item.id)
    
    item.container_atual = novo_container



def change_ownership(item: Item, novo_proprietario: Owner):
    if item.proprietario:
        antigo = item.proprietario
        if item.id in antigo.owned_items_ids:
            antigo.owned_items_ids.remove(item.id)
            antigo.owned_items = [i for i in antigo.owned_items if i.id != item.id]

    novo_proprietario.owned_items.append(item)
    novo_proprietario.owned_items_ids.append(item.id)
    
    item.proprietario = novo_proprietario



def load_item(db, item_id: str) -> Optional[Item]:
    """
    Carrega um item do MongoDB.
    """
    data = db.items.find_one({"id": item_id})
    if not data:
        return None
    return Item.model_validate(data)

def load_container_tree(db, container_id: str) -> Optional[Container]:
    """
    Carrega um container do MongoDB e reconstrói toda a sua hierarquia de filhos.
    """
    data = db.containers.find_one({"id": container_id})
    if not data:
        return None
    
    container = Container.model_validate(data)
    
    # Carrega subcontainers recursivamente
    for sub_id in container.subcontainers_ids:
        sub_container = load_container_tree(db, sub_id)
        if sub_container:
            container.subcontainers.append(sub_container)
            sub_container.parent_id = container.id
    
    for item_id in container.items_ids:
        item = load_item(db, item_id)
        if item:
            container.items.append(item)
            item.container_atual = container
    
    return container

def load_full_hierarchy(db, root_id: str) -> Optional[Container]:
    # 1. Busca OTIMIZADA: Traz todos os containers do sistema (ou filtra por dono/contexto)
    # Se o sistema for gigante, filtre pelos descendants, mas para < 5000 itens, pegue tudo.
    raw_containers = list(db.containers.find()) 
    raw_items = list(db.items.find())

    # 2. Converte tudo para Objetos e cria Mapas para acesso rápido
    mapa_containers = {c['id']: Container.model_validate(c) for c in raw_containers}
    mapa_items = {i['id']: Item.model_validate(i) for i in raw_items}

    # 3. Montagem das relações (Linkagem) na Memória RAM
    for c in mapa_containers.values():
        # Linkar Itens
        for item_id in c.items_ids:
            if item_id in mapa_items:
                item_obj = mapa_items[item_id]
                c.items.append(item_obj)
                item_obj.container_atual = c # Link reverso
        
        # Linkar Subcontainers (Filhos)
        for sub_id in c.subcontainers_ids:
            if sub_id in mapa_containers:
                sub_c = mapa_containers[sub_id]
                c.subcontainers.append(sub_c)
                sub_c.parent_container = c # Link reverso (opcional mas útil)

    # 4. Retorna apenas o container solicitado, agora totalmente preenchido
    return mapa_containers.get(root_id)

def load_owner(db, cpf: str) -> Optional[Owner]:
    """
    Carrega um proprietário do MongoDB.
    """
    data = db.owners.find_one({"cpf": cpf})
    if not data:
        return None
    owner = Owner.model_validate(data)
    
    # Carrega o container que ele segura
    held_container = load_container_tree(db, owner.held_container_id)
    if held_container:
        owner.held_container = held_container
    
    # Carrega os itens que ele possui
    for item_id in owner.owned_items_ids:
        item = load_item(db, item_id)
        if item:
            owner.owned_items.append(item)
    
    return owner

def get_all_roots(db) -> List[Container]:
    """
    Retorna todos os containers que não possuem pai (Raízes).
    """
    roots = []
    # Busca documentos onde parent_id é nulo
    cursor = db.containers.find({"parent_id": None})
    # filepath: c:\Users\Admin\Documents\inventario\api\structs.py
    for data in cursor:
        root_container = load_full_hierarchy(db, data['id'])
        if root_container:
            roots.append(root_container)
    return roots

def load_system(db) -> System:
    """
    Carrega todo o sistema do MongoDB.
    """
    system = System()
    # Carrega todos os proprietários
    cursor = db.owners.find()
    for data in cursor:
        owner = load_owner(db, data['cpf'])
        if owner:
            system.owners.append(owner)
            system.owner_cpfs.append(owner.cpf)
    
    # Carrega todos os containers raiz
    roots = get_all_roots(db)
    system.root_containers = roots
    for root in roots:
        system.root_containers.append(root)
        system.root_container_ids.append(root.id)
    
    return system


Item.model_rebuild()
Owner.model_rebuild()
Container.model_rebuild()