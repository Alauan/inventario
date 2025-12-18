from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware 
from bson import ObjectId, errors
import os
from .database import lifespan, get_db
from .utils import verificar_login_global
from .routes import auth, view, change



app = FastAPI(lifespan=lifespan, dependencies=[Depends(verificar_login_global)])
cookie_key = os.getenv("COOKIE_KEY")
if cookie_key:
    app.add_middleware(SessionMiddleware, secret_key=cookie_key)

app.include_router(auth.router)
app.include_router(view.router)
app.include_router(change.router)


@app.get("/", response_class=HTMLResponse)
async def pagina_inicial(request: Request):
    owner_id = request.session.get("usuario_logado")
    if not owner_id:
        return RedirectResponse(url="/auth/login", status_code=303)
    try:
        oid = ObjectId(owner_id)
        
        if not get_db().owners.find_one({"_id": oid}):
            raise ValueError("Usuário deletado ou inexistente")
            
    except (errors.InvalidId, ValueError, TypeError):
        request.session.clear()
        return RedirectResponse(url="/auth/login", status_code=303)

    return RedirectResponse(url=f"/view/any/home", status_code=303)





