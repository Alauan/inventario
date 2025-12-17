from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from contextlib import asynccontextmanager
import os
from .structs import Container, Item, ContainerView, ItemView


# Variável global do banco (padrão None)
db_client = None
db = None

def get_db():
    """Função que retorna o banco. Se for teste, podemos sobrescrever isso."""
    return db

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, db
    # Só conecta no Mongo REAL se não estivermos em modo de teste
    if not db: 
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_client = MongoClient(mongo_uri)
        db = db_client["sistema_inventario"]

    yield

    if db_client:
        db_client.close()

app = FastAPI(lifespan=lifespan)

# Inicializa templates
templates = Jinja2Templates(directory="templates")

# --- FUNÇÕES AUXILIARES ---

def get_breadcrumbs(container_id: str) -> list:
    """
    Sobe a árvore recursivamente para montar o caminho: 
    Ex: [{"id": "1", "nome": "Galpão"}, {"id": "5", "nome": "Caixa Azul"}]
    """
    caminho = []
    atual_id = container_id
    
    # Loop para subir até a raiz (limite de 10 níveis para segurança)
    for _ in range(10):
        if not atual_id:
            break
        container = db.containers.find_one({"id": atual_id}, {"_id": 0, "id": 1, "nome": 1, "parent_id": 1})
        if not container:
            break
        
        caminho.insert(0, {"id": container["id"], "nome": container["nome"]}) # Adiciona no início
        atual_id = container.get("parent_id")
        
    return caminho


@app.post("/containers/")
def create_container(container: Container):
    # Salvamos apenas os dados planos. Sem recursão.
    db.containers.insert_one(container.model_dump())
    return {"status": "criado", "id": container.id}

@app.post("/items/")
def create_item(item: Item):
    db.items.insert_one(item.model_dump())
    return {"status": "criado", "id": item.id}


# 2. VISUALIZAR (O "Lazy Loading")
# É aqui que seu App vai chamar quando ler o QR Code ou clicar numa pasta.
@app.get("/view_container/{container_id}", response_model=ContainerView)
def view_container_contents(container_id: str):
    
    # A. Busca os dados do container atual
    container_data = db.containers.find_one({"id": container_id}, {"_id": 0})
    if not container_data:
        raise HTTPException(status_code=404, detail="Container não encontrado")
    
    # B. Busca QUEM ESTÁ DENTRO (Filhos imediatos)
    # Isso é muito rápido porque o MongoDB indexa o campo 'parent_id' e 'container_id'
    subcontainers = list(db.containers.find({"parent_id": container_id}, {"_id": 0}))
    items = list(db.items.find({"container_id": container_id}, {"_id": 0}))
    
    # C. Gera o caminho (Breadcrumbs) para o usuário saber onde está
    breadcrumbs = get_breadcrumbs(container_id)

    # D. Monta o pacote de resposta
    return {
        "info": container_data,
        "subcontainers": subcontainers,
        "items": items,
        "caminho_pao": breadcrumbs
    }

@app.get(path="/view_item/{item_id}", response_model=ItemView)
def view_item_contents(item_id: str):
    # A. Busca os dados do item atual
    item_data = db.items.find_one({"id": item_id}, {"_id": 0})
    if not item_data:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    # B. Gera o caminho (Breadcrumbs) do container atual
    container_path = get_breadcrumbs(item_data.get("container_id"))
    
    # C. Gera o caminho (Breadcrumbs) do container original
    original_container_path = get_breadcrumbs(item_data.get("original_container_id"))
    
    # D. Busca o nome do proprietário, se houver
    owner_name = None
    proprietario_cpf = item_data.get("proprietario_cpf")
    if proprietario_cpf:
        owner = db.owners.find_one({"cpf": proprietario_cpf}, {"_id": 0, "nome": 1})
        if owner:
            owner_name = owner["nome"]
    
    # E. Monta o pacote de resposta
    return {
        "info": item_data,
        "container_path": container_path,
        "original_container_path": original_container_path,
        "owner_name": owner_name
    }


# 3. MOVER (Ação Atômica)
@app.put("/items/{item_id}/move")
def move_item(item_id: str, new_container_id: str):
    """
    Move um item mudando apenas o 'container_id' dele.
    """
    # Verifica se o container destino existe
    destino = db.containers.find_one({"id": new_container_id})
    if not destino:
        raise HTTPException(status_code=404, detail="Container destino não existe")

    # Atualiza o item
    result = db.items.update_one(
        {"id": item_id},
        {"$set": {"container_id": new_container_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item não encontrado ou já estava lá")
        
    return {"status": "movido", "novo_local": new_container_id}


# 4. LISTAR RAÍZES (Ponto de partida)
@app.get("/roots")
def get_roots():
    """
    Retorna apenas os containers principais (que não têm pai).
    """
    return list(db.containers.find({"parent_id": None}, {"_id": 0}))

# --- ROTAS ---

@app.get("/")
def home():
    return {"msg": "Backend de QR Code Ativo. Use /qr/CODIGO para testar."}

# --- 1. ROTA DE AUTENTICAÇÃO (Recebe o formulário) ---
@app.post("/autenticar")
async def login(nome_usuario: str = Form(...), proximo_passo: str = Form(...)):
    """
    Recebe o nome do formulário e cria o Cookie.
    """
    # Cria o redirecionamento de volta para o QR Code que ele tentou ler
    url_destino = f"/access/{proximo_passo}"
    response = RedirectResponse(url=url_destino, status_code=303)
    
    # A MÁGICA: Define o Cookie
    # key="usuario_logado": nome da variável
    # value=nome_usuario: o valor (ex: "Carlos")
    # max_age=31536000: Duração em segundos (1 ano). Depois disso expira.
    response.set_cookie(key="usuario_logado", value=nome_usuario, max_age=31536000)
    
    return response

@app.get("/access/{codigo}", response_class=HTMLResponse)
async def ler_qr_code(request: Request, codigo: str):
    
    # VERIFICAÇÃO: O usuário tem o cookie?
    usuario_nome = request.cookies.get("usuario_logado")

    # SE NÃO TIVER O COOKIE: Manda para o Login
    if not usuario_nome:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "codigo_alvo": codigo} # Passamos o código para o HTML lembrar
        )
    
    # SE TIVER O COOKIE: Mostra o conteúdo
    
    # 1. Tenta achar como ITEM
    item_check = db.items.find_one({"id": codigo}, {"_id": 1})
    if item_check:
        # Reutiliza a lógica de visualização de item
        data = view_item_contents(codigo)
        return templates.TemplateResponse("item.html", {"request": request, "item_view": data})

    # 2. Tenta achar como CONTAINER
    container_check = db.containers.find_one({"id": codigo}, {"_id": 1})
    if container_check:
        # Reutiliza a lógica de visualização de container
        data = view_container_contents(codigo)
        return templates.TemplateResponse("container.html", {"request": request, "container_view": data})

    # 3. Não encontrou nada
    return HTMLResponse("<h1>Código não encontrado no sistema.</h1>", status_code=404)





