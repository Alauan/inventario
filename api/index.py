from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Online", "msg": "Funcionando nativamente!"}

@app.get("/validar/{codigo}")
def validar(codigo: str):
    return {"recebido": codigo, "acesso": "permitido"}