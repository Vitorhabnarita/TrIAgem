"""
scripts/seed.py — Catálogo de sintomas (com flag de urgência) e clínica demo opcional.

Uso:
    python scripts/seed.py                 # só o catálogo de sintomas (idempotente)
    python scripts/seed.py --demo          # + clínica demo com usuários (senhas aleatórias)

As credenciais demo são gravadas em `.demo_credentials.txt` (ignorado pelo git) — nunca no código.
"""

import argparse
import asyncio
import os
import secrets
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal, engine  # noqa: E402
from app.models import Clinica, MedicoVeterinario, Sintoma, Usuario  # noqa: E402
from app.security import hash_senha  # noqa: E402

# (nome, urgência, categoria)
CATALOGO: list[tuple[str, bool, str]] = [
    # --- Sinais de URGÊNCIA (RN-001 — gatilho determinístico) ---
    ("Convulsão (tremores, rigidez ou perda de controle do corpo)", True, "Emergência"),
    ("Dificuldade grave para respirar / falta de ar", True, "Emergência"),
    ("Sangramento ativo ou que não para", True, "Emergência"),
    ("Desmaio ou perda de consciência", True, "Emergência"),
    ("Tentativa de urinar sem sucesso (faz esforço e não sai nada)", True, "Emergência"),
    ("Tentativa de vomitar sem sucesso com barriga inchada", True, "Emergência"),
    ("Suspeita de ingestão de veneno, remédio ou produto tóxico", True, "Emergência"),
    ("Atropelamento, queda de altura ou trauma grave", True, "Emergência"),
    ("Gengivas muito pálidas, azuladas ou roxas", True, "Emergência"),
    ("Barriga muito inchada e dura", True, "Emergência"),
    ("Dor intensa (grita ou não deixa ser tocado)", True, "Emergência"),
    # --- Digestivo ---
    ("Vômito", False, "Digestivo"),
    ("Diarreia", False, "Digestivo"),
    ("Fezes com sangue ou muco", False, "Digestivo"),
    ("Falta de apetite", False, "Digestivo"),
    ("Salivação excessiva", False, "Digestivo"),
    ("Mau hálito ou dificuldade para mastigar", False, "Digestivo"),
    # --- Respiratório ---
    ("Tosse", False, "Respiratório"),
    ("Espirros frequentes", False, "Respiratório"),
    ("Secreção no nariz", False, "Respiratório"),
    ("Respiração mais rápida que o normal", False, "Respiratório"),
    # --- Urinário ---
    ("Urina com mais frequência", False, "Urinário"),
    ("Urina com sangue ou cheiro muito forte", False, "Urinário"),
    ("Bebendo muito mais água que o normal", False, "Urinário"),
    # --- Pele e ouvidos ---
    ("Coceira intensa", False, "Pele e ouvidos"),
    ("Queda de pelo ou falhas no pelo", False, "Pele e ouvidos"),
    ("Feridas ou caroços na pele", False, "Pele e ouvidos"),
    ("Sacode a cabeça / mau cheiro no ouvido", False, "Pele e ouvidos"),
    ("Secreção ou vermelhidão nos olhos", False, "Pele e ouvidos"),
    # --- Locomotor / comportamento ---
    ("Manca ou tem dificuldade para andar", False, "Locomotor"),
    ("Dor ao levantar ou subir escadas", False, "Locomotor"),
    ("Apatia, prostração ou muito sonolento", False, "Comportamento"),
    ("Mudança de comportamento (agressivo, escondido, ansioso)", False, "Comportamento"),
    ("Perda de peso", False, "Comportamento"),
    ("Sensação de febre (corpo quente, tremores leves)", False, "Comportamento"),
]


async def seed_sintomas() -> None:
    async with AsyncSessionLocal() as db:
        existentes = {s.nome_sintoma: s for s in (await db.execute(select(Sintoma))).scalars()}
        novos = 0
        for nome, urgencia, categoria in CATALOGO:
            s = existentes.get(nome)
            if s is None:
                db.add(Sintoma(nome_sintoma=nome, alerta_urgencia=urgencia, categoria=categoria, ativo=True))
                novos += 1
            else:
                s.alerta_urgencia, s.categoria = urgencia, categoria
        await db.commit()
        print(f"[seed] sintomas: {novos} novos, {len(CATALOGO) - novos} atualizados.")


async def seed_demo() -> None:
    async with AsyncSessionLocal() as db:
        if await db.scalar(select(Clinica).where(Clinica.cnpj == "00.000.000/0001-91")):
            print("[seed] clínica demo já existe — nada a fazer.")
            return
        clinica = Clinica(nome_fantasia="Clínica Veterinária Demo TrIAgem", cnpj="00.000.000/0001-91")
        db.add(clinica)
        await db.flush()
        medico = MedicoVeterinario(id_clinica=clinica.id_clinica, nome="Dra. Helena Duarte", crmv="CRMV-SP 10001")
        db.add(medico)
        await db.flush()

        senhas = {p: secrets.token_urlsafe(12) for p in ("recepcao", "medico", "gestor")}
        db.add_all([
            Usuario(id_clinica=clinica.id_clinica, nome="Recepção Demo", email="recepcao@demo.triagem.app",
                    senha_hash=hash_senha(senhas["recepcao"]), papel="recepcao"),
            Usuario(id_clinica=clinica.id_clinica, id_medico=medico.id_medico, nome="Dra. Helena Duarte",
                    email="medico@demo.triagem.app", senha_hash=hash_senha(senhas["medico"]), papel="medico"),
            Usuario(id_clinica=clinica.id_clinica, nome="Gestor Demo", email="gestor@demo.triagem.app",
                    senha_hash=hash_senha(senhas["gestor"]), papel="gestor"),
        ])
        await db.commit()

    caminho = os.path.join(os.path.dirname(__file__), "..", ".demo_credentials.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("Credenciais DEMO (geradas localmente — não commitar)\n")
        for papel, senha in senhas.items():
            f.write(f"{papel}@demo.triagem.app  |  {senha}\n")
    print("[seed] clínica demo criada. Credenciais em .demo_credentials.txt")


async def main(demo: bool) -> None:
    await seed_sintomas()
    if demo:
        await seed_demo()
    await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    asyncio.run(main(p.parse_args().demo))

