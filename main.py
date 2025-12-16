from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Online", "msg": "API rodando na Vercel!"}

@app.post("/validar_qr")
def validar(dados: dict):
    # Simulação simples
    return {"recebido": dados, "acesso": "permitido"}

# Esta linha é OBRIGATÓRIA para funcionar na Vercel/AWS Lambda
handler = Mangum(app)