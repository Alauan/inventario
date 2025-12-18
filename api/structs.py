from pydantic import BaseModel, Field
from typing import Optional, List, Any
import uuid

# Função auxiliar para gerar IDs únicos
def generate_id():
    return str(uuid.uuid4())

# --- 1. ITEM (A Folha) ---
class Item(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    name: str
    description: Optional[str] = None
    
    container_id: Optional[str] = None 
    original_container_id: Optional[str] = None
    owner_id: Optional[str] = None

# --- 2. CONTAINER (O Nó) ---
class Container(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    name: str
    parent_id: Optional[str] = None
    

class Owner(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    cpf: str
    name: str

# --- 3. DTOs (Data Transfer Objects) ---
# Estas classes servem apenas para ENVIAR dados combinados para o Frontend
# O banco não usa isso, é apenas para visualização.

class ContainerView(BaseModel):
    info: Container
    subcontainers: List[Container]
    current_items: List[Item]
    path: List[dict] # Breadcrumbs (ex: Galpão > Estante > Caixa)

class ItemView(BaseModel):
    info: Item
    container_path: List[dict] # Breadcrumbs do container onde o item está
    original_container_path: List[dict]
    owner_name: Optional[str] = None

class EnrichedItem(ItemView):       # Somente para visualização
    """
    Herda de Item, mas adiciona campos calculados apenas para visualização
    """
    is_out_of_place: bool = False # Se está fora do container original
    is_lent: bool = False # Se está emprestado

class OwnerView(BaseModel):
    info: Owner
    held_items: List[ItemView]          # Itens que estão FISICAMENTE com o owner
    owned_items: List[EnrichedItem] # Itens que PERTENCEM ao owner (com dados extras)
    root_containers: List[Container]
