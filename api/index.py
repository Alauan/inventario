from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware # cookies autenticados
from pymongo import MongoClient
from pymongo.database import Database
from contextlib import asynccontextmanager
import os
from .structs import Container, Item, ContainerView, ItemView, Owner


# Variável global do banco (padrão None)
db_client = None
db: Database = None #type: ignore

def get_db():
    """Função que retorna o banco. Se for teste, podemos sobrescrever isso."""
    return db

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, db
    if not db:  #type: ignore
        mongo_uri = os.getenv("MONGO_URI")
        db_client = MongoClient(mongo_uri)
        db = db_client["inventario"]

    yield

    if db_client:
        db_client.close()


async def verificar_login_global(request: Request):
    # Lista de rotas que são PÚBLICAS (não precisam de login)
    rotas_publicas = [
        "/login",       # A página de login
        "/autenticar",  # O endpoint que processa o login
        "/docs",        # Documentação do FastAPI (opcional)
        "/openapi.json" # Necessário para o /docs
    ]
    
    # Se a rota atual for pública, deixa passar
    if request.url.path in rotas_publicas:
        return

    # Verifica se o usuário está na sessão
    usuario = request.session.get("usuario_logado")
    
    if not usuario:
        raise HTTPException(status_code=303, headers={"Location": "/login"})

app = FastAPI(lifespan=lifespan, dependencies=[Depends(verificar_login_global)])
cookie_key = os.getenv("COOKIE_KEY")
if cookie_key:
    app.add_middleware(SessionMiddleware, secret_key=cookie_key)

@app.get("/login", response_class=HTMLResponse)
def pagina_login(request: Request):
    # Renderiza o login.html mas sem um "código alvo" específico
    return templates.TemplateResponse(
        "login.html", 
        context={"request": request, "codigo_alvo": "home", "erro": None}
    )

# Inicializa templates
templates = Jinja2Templates(directory="templates")

# --- FUNÇÕES AUXILIARES ---

def get_breadcrumbs(container_id: str) -> list:
    caminho = []
    atual_id = container_id
    
    for _ in range(10):
        if not atual_id:
            break
        container = db.containers.find_one({"_id": atual_id})
        if not container:
            break
        
        caminho.insert(0, {"id": container["_id"], "nome": container["nome"]}) 
        atual_id = container.get("parent_id")
        
    return caminho

@app.post("/containers/")
def create_container(container: Container):
    db.containers.insert_one(container.model_dump(by_alias=True))
    return {"status": "criado", "id": container.id}

@app.post("/items/")
def create_item(item: Item):
    db.items.insert_one(item.model_dump(by_alias=True))
    return {"status": "criado", "id": item.id}

@app.post("/owners/")
def create_owner(owner: Owner):
    db.owners.insert_one(owner.model_dump(by_alias=True))
    return {"status": "criado", "id": owner.id}


@app.post("/web/create_item")
async def web_create_item(
    request: Request,
    nome: str = Form(...),
    descricao: str = Form(None),
    container_id: str = Form(...)):
    """
    Cria um item via formulário Web, definindo a origem e localização atual
    como o container onde o botão foi clicado.
    """
    # 1. Cria o objeto Item
    # Nota: Definimos tanto container_id quanto original_container_id
    novo_item = Item(
        nome=nome,
        descricao=descricao,
        container_id=container_id,
        original_container_id=container_id,
        owner_id=request.session.get("usuario_logado")
    )
    
    # 2. Salva no banco
    db.items.insert_one(novo_item.model_dump(by_alias=True))
    
    # 3. Redireciona de volta para a visualização do container
    return RedirectResponse(url=f"/access/{container_id}", status_code=303)


# 2. VISUALIZAR (O "Lazy Loading")
# É aqui que seu App vai chamar quando ler o QR Code ou clicar numa pasta.
@app.get("/view_container/{container_id}", response_model=ContainerView)
def view_container_contents(container_id: str):
    
    # A. Busca os dados do container atual
    container_data = db.containers.find_one({"_id": container_id})
    if not container_data:
        raise HTTPException(status_code=404, detail="Container não encontrado")
    
    # B. Busca QUEM ESTÁ DENTRO (Filhos imediatos)
    # Isso é muito rápido porque o MongoDB indexa o campo 'parent_id' e 'container_id'
    subcontainers = list(db.containers.find({"parent_id": container_id}))
    items = list(db.items.find({"container_id": container_id}))
    
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
    item_data = db.items.find_one({"_id": item_id})
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
        owner = db.owners.find_one({"_id": owner_id}, {"_id": 0, "nome": 1})
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


# 4. LISTAR RAÍZES (Ponto de partida)
@app.get("/roots")
def get_roots():
    """
    Retorna apenas os containers principais (que não têm pai).
    """
    return list(db.containers.find({"parent_id": None}))

# --- ROTAS ---

@app.get("/")
def home():
    return {"msg": "Backend de QR Code Ativo. Use /qr/CODIGO para testar."}

# --- 1. ROTA DE AUTENTICAÇÃO (Recebe o formulário) ---
@app.post("/autenticar")
async def login(request: Request, nome_usuario: str = Form(...), senha: str = Form(...), cpf_usuario: str = Form(...), proximo_passo: str = Form(...)):
    """
    Recebe o nome do formulário e cria o Cookie.
    """
    # Cria o redirecionamento de volta para o QR Code que ele tentou ler
    SYSTEM_PASSWORD = os.getenv("SYSTEM_PASSWORD", "senha123")

    if senha != SYSTEM_PASSWORD:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "codigo_alvo": proximo_passo, "erro": "Senha incorreta!"}
        )
    
    # Verifica se o usuário já existe pelo CPF
    usuario = db.owners.find_one({"cpf": cpf_usuario})
    
    if usuario:
        # Atualiza o nome se o CPF já existe
        db.owners.update_one(
            {"cpf": cpf_usuario},
            {"$set": {"nome": nome_usuario}}
        )
    else:
        # Cria um novo usuário se o CPF não existe
        usuario_novo = Owner(nome=nome_usuario, cpf=cpf_usuario)
        db.owners.insert_one(usuario_novo.model_dump(by_alias=True))
        usuario = usuario_novo.model_dump()

    url_destino = f"/access/{proximo_passo}"
    response = RedirectResponse(url=url_destino, status_code=303)
    
    request.session["usuario_logado"] = usuario["_id"]
    
    return response

@app.get("/access/{codigo}", response_class=HTMLResponse)
async def ler_qr_code(request: Request, codigo: str):
    # 1. Tenta achar como ITEM
    item_check = db.items.find_one({"_id": codigo})
    if item_check:
        # Reutiliza a lógica de visualização de item
        data = view_item_contents(codigo)
        return templates.TemplateResponse("item.html", {"request": request, "item_view": data})

    # 2. Tenta achar como CONTAINER
    container_check = db.containers.find_one({"_id": codigo})
    if container_check:
        # Reutiliza a lógica de visualização de container
        data = view_container_contents(codigo)
        return templates.TemplateResponse("container.html", {"request": request, "container_view": data})

    # 3. Não encontrou nada
    return HTMLResponse("<h1>Código não encontrado no sistema.</h1>", status_code=404)





