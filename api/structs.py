from pydantic import BaseModel, Field
from typing import Optional, List, Any
import uuid
from enum import Enum

def generate_id():
    return str(uuid.uuid4())

class ObjectType(str, Enum):
    ITEM = "item"
    CONTAINER = "container"

class Object(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    name: str
    type: ObjectType
    parent_id: Optional[str] = None
    original_parent_id: Optional[str] = None
    owner_id: Optional[str] = None
    description: Optional[str] = None
    

class Owner(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    cpf: str
    name: str

# --- 3. DTOs (Data Transfer Objects) ---
# Estas classes servem apenas para ENVIAR dados combinados para o Frontend
# O banco não usa isso, é apenas para visualização.

class EnrichedObject(BaseModel):       # Somente para visualização
    """
    Herda de Item, mas adiciona campos calculados apenas para visualização
    """
    info: Object
    path: List[dict] = []  # Breadcrumbs do local atual
    original_path: List[dict] = []  # Breadcrumbs do local original
    is_out_of_place: bool = False # Se está fora do container original

class ContainerView(BaseModel):
    info: Object
    subcontainers: List[Object]
    current_items: List[Object]
    owned_items: List[EnrichedObject]
    owned_subcontainers: List[EnrichedObject]
    held_objects: List[Object]
    path: List[dict] # Breadcrumbs (ex: Galpão > Estante > Caixa)

class ItemView(BaseModel):
    info: Object
    container_path: List[dict] # Breadcrumbs do container onde o item está
    original_container_path: List[dict]
    owner_name: Optional[str] = None

class OwnerView(BaseModel):
    info: Owner
    held_objects: List[EnrichedObject]          # Itens que estão FISICAMENTE com o owner
    owned_objects: List[EnrichedObject] # Itens que PERTENCEM ao owner (com dados extras)
    root_containers: List[Object]
