from pydantic import BaseModel, Field
from typing import Optional, List, Any
import uuid

# Função auxiliar para gerar IDs únicos
def generate_id():
    return str(uuid.uuid4())

# --- 1. ITEM (A Folha) ---
class Item(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    nome: str
    descricao: Optional[str] = None
    
    container_id: Optional[str] = None 
    original_container_id: Optional[str] = None
    owner_id: Optional[str] = None

# --- 2. CONTAINER (O Nó) ---
class Container(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    nome: str
    parent_id: Optional[str] = None
    

class Owner(BaseModel):
    id: str = Field(default_factory=generate_id, alias="_id")
    cpf: str
    nome: str

# --- 3. DTOs (Data Transfer Objects) ---
# Estas classes servem apenas para ENVIAR dados combinados para o Frontend
# O banco não usa isso, é apenas para visualização.

class ContainerView(BaseModel):
    info: Container
    subcontainers: List[Container]
    items: List[Item]
    caminho_pao: List[dict] # Breadcrumbs (ex: Galpão > Estante > Caixa)

class ItemView(BaseModel):
    info: Item
    container_path: List[dict] # Breadcrumbs do container onde o item está
    original_container_path: List[dict]
    owner_name: Optional[str] = None
