from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
import structs
import os

app = FastAPI()

# --- CONFIGURAÇÃO DE PASTAS (Mantendo o que fizemos antes) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "..", "templates")
templates = Jinja2Templates(directory=templates_dir)

MONGO_URI = os.getenv("MONGO_URI")
client_mongo = MongoClient(MONGO_URI)



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

@app.patch("/move_item/{item_id}/{novo_container}")
async def move_item_endpoint(item_id: int, novo_container: str):


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

    # Simulação de Banco de Dados
    # Dica: No futuro você pode substituir isso por um banco real ou leitura de CSV
    base_de_dados = {
        "CLIENTE_A": {"nome": "Ana Clara", "status": "normal", "saldo": "R$ 50,00"},
        "CLIENTE_B": {"nome": "Bruno Dias", "status": "vip", "saldo": "R$ 0,00"},
        "FESTA_VIP": {"nome": "Convidado VIP", "status": "vip", "mesa": "12"},
    }

    dados = base_de_dados.get(codigo)

    if dados:
        # Lógica de decisão: Qual página mostrar?
        if dados["status"] == "normal":
            return templates.TemplateResponse(
                "acesso_normal.html", 
                {"request": request, "usuario": dados}
            )
        elif dados["status"] == "vip":
             return templates.TemplateResponse(
                "acesso_vip.html", 
                {"request": request, "usuario": dados}
            )
    
    # Se o código não for encontrado
    return templates.TemplateResponse(
        "erro.html",
        {"request": request, "codigo_tentado": codigo},
        status_code=404
    )