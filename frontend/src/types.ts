/** Tipos espelhando os schemas Pydantic do backend (app/schemas.py). */

export type Papel = 'recepcao' | 'medico' | 'gestor'

export interface Usuario {
  id_usuario: number
  nome: string
  email: string
  papel: Papel
  id_clinica: number
  id_medico: number | null
}

export interface ClinicaResumo {
  id_clinica: number
  nome_fantasia: string
  segmento: string
}

export interface Sessao {
  access_token: string
  token_type: 'bearer'
  usuario: Usuario
  clinica: ClinicaResumo
}

export type ModalidadeEmergencia = 'EMERGENCIA_A_CAMINHO' | 'RESGATE_SOLICITADO'
export type CorPrioridade = 'VERMELHO' | 'LARANJA' | 'AMARELO' | 'VERDE' | 'AZUL'
export type StatusConsulta = 'agendada' | 'em_andamento' | 'finalizada' | 'cancelada'

export interface MedicoMini {
  id_medico: number
  nome: string
}

export interface ConsultaFilaItem {
  id_consulta: number
  status: StatusConsulta
  agendada_para: string | null
  pet_nome: string
  especie: string
  pet_raca: string
  pet_sexo: string
  pet_idade: string
  pet_peso_kg: number | null
  pet_porte: string | null
  pet_status_reprodutivo: string | null
  tutor_nome: string
  tutor_telefone: string
  medico: MedicoMini
  status_triagem: 'pendente' | 'preenchido' | 'urgencia'
  urgencia: boolean
  nivel_prioridade: string | null
  cor_prioridade: CorPrioridade | null
  status_ia: string | null
  link_triagem: string
  whatsapp_url: string
  inicio_consulta: string | null
  fim_consulta: string | null
  duracao_minutos: number | null
  minutos_economizados: number | null
  modalidade_emergencia: ModalidadeEmergencia | null
  localizacao_gps_tutor: string | null
  maps_url_tutor: string | null
  ciente_risco_morte: boolean
}

export interface ConsultaStatus {
  id_consulta: number
  status: StatusConsulta
  inicio_consulta: string | null
  fim_consulta: string | null
}

export interface ConsultaFinalizada {
  id_consulta: number
  status: string
  inicio_consulta: string
  fim_consulta: string
  duracao_minutos: number
  benchmark_minutos: number
  minutos_economizados: number
  com_triagem: boolean
  mensagem: string
}

export interface PetResumo {
  nome: string
  especie: string
  raca: string
  sexo: string
  idade_texto: string
  peso_kg: number | null
  porte: string | null
  status_reprodutivo: string | null
}

export interface TutorComPets {
  nome: string
  telefone: string
  pets: PetResumo[]
}

export interface MedicoOut {
  id_medico: number
  id_clinica: number
  nome: string
  crmv: string
}

export interface PetIn {
  nome: string
  especie: string
  raca?: string
  sexo?: 'Macho' | 'Fêmea' | 'Não informado'
  idade_texto?: string
  peso_kg?: number | null
  porte?: 'Mini' | 'Pequeno' | 'Médio' | 'Grande' | 'Gigante' | null
  status_reprodutivo?: 'Castrado' | 'Inteiro' | null
}

export interface ConsultaAgendar {
  id_medico: number
  agendada_para?: string | null
  tutor: { nome: string; telefone: string }
  pet: PetIn
}

// ---------------------------------------------------------------------------
// Fluxo público do tutor
// ---------------------------------------------------------------------------

export interface SintomaPublico {
  id_sintoma: number
  nome_sintoma: string
  alerta_urgencia: boolean
  categoria: string
  categoria_emergencia: string | null
}

export interface GatilhoTexto {
  termo: string
  padrao: string
  categoria: string
}

export interface ProtocoloEmergenciaPublico {
  atendimento_24h: boolean
  clinica_aberta_agora: boolean
  horario_fechamento: string
  possui_veiculo_resgate: boolean
  whatsapp_plantao: string | null
  endereco_completo: string | null
  url_hospital_24h: string
  rota_clinica: { google_maps: string; waze: string }
  primeiros_socorros_negativos: Record<string, string>
  gatilhos_texto: GatilhoTexto[]
}

export interface TriagemContexto {
  clinica_nome: string
  segmento: string
  tutor_primeiro_nome: string
  pet: PetResumo
  agendada_para: string | null
  estado: 'aguardando' | 'preenchida' | 'expirada' | 'cancelada'
  sintomas: SintomaPublico[]
  texto_termo: string
  emergencia: ProtocoloEmergenciaPublico
  modalidade_emergencia: ModalidadeEmergencia | null
}

export interface TriagemSubmissao {
  aceite_termo: boolean
  ambiente: string
  alimentacao: string
  vacinacao_em_dia: boolean
  vermifugo_em_dia: boolean
  convivio_outros_animais: boolean
  manejo_preventivo?: string | null
  medicamento_continuo: string
  aspecto_urina_fezes: string
  alteracao_peso_apetite: string
  ingestao_hidrica: string
  tempo_evolucao: string
  relato_livre_tutor: string
  sintoma_ids: number[]
  ciente_risco_morte?: boolean
  alerta_critico_exibido_em?: string | null
  modalidade_emergencia?: ModalidadeEmergencia | null
  localizacao_gps_tutor?: string | null
}

export interface TriagemSubmissaoOut {
  recebida: boolean
  urgencia_detectada: boolean
  sintomas_urgencia: string[]
  acao_recomendada: 'PRONTO_SOCORRO_IMEDIATO' | 'AGUARDAR_ATENDIMENTO'
  mensagem_para_tutor: string
  status_ia: string
  primeiros_socorros_negativos: Record<string, string>
  termos_criticos_relato: string[]
  modalidade_emergencia: ModalidadeEmergencia | null
  maps_url_tutor: string | null
  whatsapp_resgate_url: string | null
}

export interface ResultadoTutor {
  status_ia: 'pendente' | 'concluida' | 'falhou'
  urgencia_detectada: boolean
  acao_recomendada: 'PRONTO_SOCORRO_IMEDIATO' | 'AGUARDAR_ATENDIMENTO'
  alerta_seguranca_tutor: string | null
  nivel_prioridade: string | null
  primeiros_socorros_negativos: Record<string, string>
  modalidade_emergencia: ModalidadeEmergencia | null
}

export interface AcionarEmergenciaIn {
  modalidade: ModalidadeEmergencia
  localizacao_gps_tutor?: string | null
  ciente_risco_morte: boolean
  alerta_critico_exibido_em?: string | null
  categorias_emergencia: string[]
}

export interface AcionarEmergenciaOut {
  registrada: boolean
  modalidade_emergencia: ModalidadeEmergencia
  localizacao_gps_tutor: string | null
  maps_url_tutor: string | null
  whatsapp_resgate_url: string | null
  rota_clinica: { google_maps: string; waze: string }
  whatsapp_plantao: string | null
  primeiros_socorros_negativos: Record<string, string>
  mensagem_para_tutor: string
}

// ---------------------------------------------------------------------------
// Briefing clínico
// ---------------------------------------------------------------------------

export interface Traducao {
  relato_leigo: string
  termo_tecnico_descritivo: string
}

export interface Relatorio {
  id_relatorio: number
  flag_urgencia_detectada: boolean
  nivel_prioridade: string
  cor_prioridade: CorPrioridade
  resumo_estruturado: string
  traducao_semiologica: Traducao[]
  cronologia_evolucao: string
  alerta_medicacao_e_bioindicadores: string
  sinais_alerta_identificados: string[]
  pontos_investigacao: string[]
  orientacao_preparatoria_consultorio: string
  alerta_seguranca_tutor: string
  aviso_governanca_etica: string
  modelo_utilizado: string
  processado_em: string
}

export interface Formulario {
  id_formulario: number
  ambiente: string
  alimentacao: string
  vacinacao_em_dia: boolean
  vermifugo_em_dia: boolean
  convivio_outros_animais: boolean
  manejo_preventivo: string | null
  medicamento_continuo: string
  aspecto_urina_fezes: string
  alteracao_peso_apetite: string
  ingestao_hidrica: string
  tempo_evolucao: string
  relato_livre_tutor: string
  urgencia_deterministica: boolean
  status_ia: string
  submetido_em: string
  sintomas: { id_sintoma: number; nome_sintoma: string; alerta_urgencia: boolean; categoria: string }[]
}

export interface Briefing {
  id_consulta: number
  status: StatusConsulta
  agendada_para: string | null
  inicio_consulta: string | null
  fim_consulta: string | null
  medico: MedicoMini
  pet: PetResumo & { id_pet: number }
  tutor: { id_tutor: number; nome: string; telefone: string }
  triagem_preenchida: boolean
  formulario: Formulario | null
  relatorio: Relatorio | null
  urgencia: boolean
  sintomas_urgencia: string[]
  status_ia: string | null
  medicamento_continuo: string | null
  benchmark_minutos: number
  modalidade_emergencia: ModalidadeEmergencia | null
  localizacao_gps_tutor: string | null
  maps_url_tutor: string | null
  ciente_risco_morte: boolean
  alerta_critico_exibido_em: string | null
  protocolo_abc_emergencia: string[]
}

// ---------------------------------------------------------------------------
// Dashboard B2B
// ---------------------------------------------------------------------------

export interface RoiSerieDia {
  dia: string
  consultas: number
  minutos_economizados: number
}

export interface RiscoDistribuicao {
  cor: CorPrioridade
  nivel: string
  quantidade: number
  percentual: number
}

export interface Metricas {
  de: string
  ate: string
  benchmark_minutos: number
  consultas_finalizadas: number
  consultas_com_triagem: number
  minutos_economizados: number
  horas_economizadas: number
  capacidade_extra_atendimentos: number
  duracao_media_minutos: number | null
  total_agendadas: number
  triagens_realizadas: number
  taxa_adesao_pct: number
  urgencias_detectadas: number
  urgencias_pct: number
  serie_diaria: RoiSerieDia[]
  observacao: string
  ticket_medio_consulta: number
  receita_adicional_potencial: number
  distribuicao_risco: RiscoDistribuicao[]
  emergencias_acionadas: number
  resgates_solicitados: number
}
