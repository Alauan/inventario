from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Online"}

@app.post("/validar_qr")
def validar(dados: dict):
    return {"recebido": dados}

handler = Mangum(app)