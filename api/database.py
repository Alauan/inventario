from pymongo import MongoClient
from pymongo.database import Database
from contextlib import asynccontextmanager
from fastapi import FastAPI
import os
from fastapi.templating import Jinja2Templates


db_client = None
db: Database = None #type: ignore
templates = Jinja2Templates(directory="templates")

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

    