from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Online", "msg": "Funciona!"}

@app.post("/validar_qr")
def validar(dados: dict):
    return {"recebido": dados}

# Esta linha é crítica. Ela deve estar no final e SEM indentação.
handler = Mangum(app)