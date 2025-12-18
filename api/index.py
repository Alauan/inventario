from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware 
import os
from .database import lifespan
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
    return RedirectResponse(url=f"/view/any/{owner_id}", status_code=303)





