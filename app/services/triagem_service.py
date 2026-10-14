"""
app/services/triagem_service.py — Pipeline da Triagem Pré-Consulta.

  1. Router grava o formulário (com urgência determinística) e dá commit.
  2. `processar_ia_em_background` roda DEPOIS da resposta ao tutor, com sessão própria:
       monta DadosTriagem → Gemini → grava RelatorioIA → status_ia.
  3. Falha da IA NUNCA derruba o fluxo: status_ia='falhou' e o gatilho determinístico
     (RN-001) continua valendo; há rota de reprocessamento.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models import Consulta, FormularioTriagem, Pet, RelatorioIA
from app.services import ai_service
from app.services.ai_service import DadosTriagem, IAIndisponivel

logger = logging.getLogger("triagem.pipeline")


def montar_dados(formulario: FormularioTriagem, pet: Pet) -> DadosTriagem:
    sintomas = list(formulario.sintomas)
    return DadosTriagem(
        especie=pet.especie,
        raca=pet.raca,
        sexo=pet.sexo,
        idade_texto=pet.idade_texto,
        ambiente=formulario.ambiente,
        alimentacao=formulario.alimentacao,
        vacinacao_em_dia=formulario.vacinacao_em_dia,
        vermifugo_em_dia=formulario.vermifugo_em_dia,
        convivio_outros_animais=formulario.convivio_outros_animais,
        manejo_preventivo=formulario.manejo_preventivo or "",
        medicamento_continuo=formulario.medicamento_continuo,
        aspecto_urina_fezes=formulario.aspecto_urina_fezes,
        alteracao_peso_apetite=formulario.alteracao_peso_apetite,
        ingestao_hidrica=formulario.ingestao_hidrica,
        tempo_evolucao=formulario.tempo_evolucao,
        relato_livre_tutor=formulario.relato_livre_tutor,
        sintomas_marcados=[s.nome_sintoma for s in sintomas],
        sintomas_urgencia=[s.nome_sintoma for s in sintomas if s.alerta_urgencia],
        peso_kg=float(pet.peso_kg) if pet.peso_kg is not None else None,
        porte=pet.porte,
        status_reprodutivo=pet.status_reprodutivo,
    )


async def processar_ia_em_background(id_formulario: int) -> None:
    """Executa a IA com sessão própria (a sessão da requisição já foi encerrada)."""
    async with AsyncSessionLocal() as db:
        try:
            formulario: Optional[FormularioTriagem] = (
                await db.execute(
                    select(FormularioTriagem)
                    .options(
                        selectinload(FormularioTriagem.sintomas),
                        selectinload(FormularioTriagem.relatorio),
                        selectinload(FormularioTriagem.consulta)
                        .selectinload(Consulta.pet),
                    )
                    .where(FormularioTriagem.id_formulario == id_formulario)
                )
            ).scalar_one_or_none()
            if formulario is None:
                logger.error("Formulário %s não encontrado para processamento de IA.", id_formulario)
                return

            dados = montar_dados(formulario, formulario.consulta.pet)
            try:
                resultado = await ai_service.gerar_briefing(dados)
            except IAIndisponivel as exc:
                logger.error("IA indisponível para formulário %s: %s", id_formulario, exc)
                formulario.status_ia = "falhou"
                await db.commit()
                return
            except Exception:  # noqa: BLE001
                logger.exception("Erro inesperado na IA (formulário %s)", id_formulario)
                formulario.status_ia = "falhou"
                await db.commit()
                return

            b = resultado.briefing
            campos = dict(
                resumo_estruturado=b.resumo_estruturado,
                pontos_investigacao=list(b.pontos_investigacao),
                flag_urgencia_detectada=b.flag_urgencia_detectada,
                nivel_prioridade=b.nivel_prioridade.value,
                cor_prioridade=b.cor_prioridade.value,
                traducao_semiologica=[t.model_dump() for t in b.traducao_semiologica],
                cronologia_evolucao=b.cronologia_evolucao,
                alerta_medicacao_e_bioindicadores=b.alerta_medicacao_e_bioindicadores,
                sinais_alerta_identificados=list(b.sinais_alerta_identificados),
                orientacao_preparatoria_consultorio=b.orientacao_preparatoria_consultorio,
                alerta_seguranca_tutor=b.alerta_seguranca_tutor,
                aviso_governanca_etica=b.aviso_governanca_etica,
                modelo_utilizado=resultado.modelo[:80],
            )
            if formulario.relatorio is None:
                db.add(RelatorioIA(id_formulario=id_formulario, **campos))
            else:
                for k, v in campos.items():
                    setattr(formulario.relatorio, k, v)
            formulario.status_ia = "concluida"
            await db.commit()
            logger.info(
                "Relatório Clínico Prévio gerado (formulário %s, modelo %s, prioridade %s).",
                id_formulario, resultado.modelo, b.nivel_prioridade.value,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao persistir Relatório Clínico Prévio (formulário %s)", id_formulario)
            await db.rollback()

