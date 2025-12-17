# test_api.py
from fastapi.testclient import TestClient
import mongomock
from index import app, db # Importe seu app e a variável db
import index # Importe o módulo inteiro para sobrescrever a variável global

# --- CONFIGURAÇÃO DO AMBIENTE DE TESTE ---

# 1. Criamos um banco de mentira (na memória RAM)
mock_client = mongomock.MongoClient()
mock_db = mock_client["sistema_teste"]

# 2. "Hackeamos" o main.py para ele usar nosso banco falso
index.db = mock_db 

# 3. Criamos o cliente de teste do FastAPI
client = TestClient(app)

# --- OS TESTES ---

def test_fluxo_completo_inventario():
    print("\n--- INICIANDO TESTE ---")

    # 1. CRIAR A RAIZ (GALPÃO)
    resp = client.post("/containers/", json={"nome": "Galpão A"})
    assert resp.status_code == 200
    id_galpao = resp.json()["id"]
    print(f"✅ Galpão criado: {id_galpao}")

    # 2. CRIAR SUB-CONTAINER (ESTANTE)
    resp = client.post("/containers/", json={
        "nome": "Estante 1", 
        "parent_id": id_galpao
    })
    id_estante = resp.json()["id"]
    print(f"✅ Estante criada dentro do Galpão: {id_estante}")

    # 3. CRIAR ITEM NA ESTANTE (PARAFUSADEIRA)
    resp = client.post("/items/", json={
        "nome": "Parafusadeira Bosch",
        "container_id": id_estante
    })
    id_item = resp.json()["id"]
    print(f"✅ Item criado na Estante: {id_item}")

    # 4. TESTAR A VISUALIZAÇÃO (VIEW) - O TESTE DE FOGO
    # Vamos ver se o 'lazy loading' e os breadcrumbs funcionam
    resp = client.get(f"/view/{id_estante}")
    dados = resp.json()

    # Verificações
    assert dados["info"]["id"] == id_estante
    assert len(dados["items"]) == 1
    assert dados["items"][0]["nome"] == "Parafusadeira Bosch"
    
    # Teste do Breadcrumb (Caminho do Pão)
    # Esperado: Galpão A -> Estante 1
    crumbs = dados["caminho_pao"]
    assert crumbs[0]["nome"] == "Galpão A"
    assert crumbs[1]["nome"] == "Estante 1"
    print("✅ Visualização e Breadcrumbs corretos!")

    # 5. TESTAR MOVIMENTAÇÃO (MOVE)
    # Vamos criar uma caixa solta e mover o item pra lá
    resp = client.post("/containers/", json={"nome": "Caixa de Ferramentas"})
    id_caixa = resp.json()["id"]

    resp = client.put(f"/items/{id_item}/move", params={"new_container_id": id_caixa})
    assert resp.status_code == 200
    
    # Verificar se saiu da estante
    resp_estante = client.get(f"/view/{id_estante}")
    assert len(resp_estante.json()["items"]) == 0
    print("✅ Item removido da Estante com sucesso.")

    # Verificar se chegou na caixa
    resp_caixa = client.get(f"/view/{id_caixa}")
    assert len(resp_caixa.json()["items"]) == 1
    print("✅ Item chegou na Caixa com sucesso.")

    print("\n🎉 TODOS OS TESTES PASSARAM!")