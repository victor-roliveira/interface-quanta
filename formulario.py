import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime
import pytz

responsaveis = {
    "aleframos62@gmail.com": "abcd1234",
    "hagata@gmail.com": "abcde123"
}

# ========== CONFIGURAÇÕES DE ACESSO ========== #
st.set_page_config(page_title="Gerenciador de Tarefas", layout="wide")

SCOPE = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

# 🔐 Autenticando com o Google Sheets PRODUÇÃO
def autenticar_google_sheets():
    try:
        credentials_info = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key('1ZzMXgfnGvplabe9eNDCUXUbjuCXLieSgbpPUqAtBYOU').sheet1  
        return sheet
    except Exception as e:
        st.error(f"Erro ao autenticar com o Google Sheets: {e}")
        return None

# 📥 Carrega os dados da planilha
def carregar_dados(sheet):
    dados = sheet.get_all_records()
    df = pd.DataFrame(dados)
    # Remover espaços nos nomes das colunas
    df.columns = df.columns.str.strip()
    return df

# 🧾 Atualiza a tabela na planilha
def atualizar_linha(sheet, numero_hierarquico, nova_linha):
    registros = sheet.get_all_records()
    for idx, row in enumerate(registros, start=2):  # header é linha 1
        if str(row["Número Hierárquico"]).strip() == str(numero_hierarquico).strip():
            sheet.update(f"A{idx}:F{idx}", [nova_linha])
            return True
    return False

# 🆕 Insere nova linha
def inserir_linha(sheet, nova_linha):
    sheet.append_row(nova_linha)

# 🔄 Função para converter string percentual para float
def parse_percent_string(percent_str):
    try:
        if isinstance(percent_str, str):
            return float(percent_str.replace('%', '').replace(',', '.'))
        return float(percent_str)
    except:
        return 0.0

# ========== INTERFACE STREAMLIT ========== #
st.title("Gerenciador de Tarefas")

sheet = autenticar_google_sheets()
if not sheet:
    st.stop()

dados_df = carregar_dados(sheet)

# Verificação de colunas obrigatórias
colunas_esperadas = [
    "Número Hierárquico",
    "Nome da Tarefa",
    "% Concluída",
    "% Prevista",
    "Duração"
]

colunas_faltando = [col for col in colunas_esperadas if col not in dados_df.columns]
if colunas_faltando:
    st.error(f"⚠️ As seguintes colunas estão faltando na planilha: {colunas_faltando}")
    st.stop()

aba = st.sidebar.radio("Escolha uma opção:", ["Inserir Tarefa", "Editar Tarefa", "Visualizar Tarefas"])

# ========== FORMULÁRIO DE INSERÇÃO ========== #
if aba == "Inserir Tarefa":
    st.header("➕ Inserir Nova Tarefa")
    with st.form(key="inserir_form"):
        num_hierarquico = st.text_input("Número Hierárquico")
        nome_tarefa = st.text_input("Nome da Tarefa")
        perc_concluida = st.number_input("% Concluída", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
        perc_previsto = st.number_input("% Prevista", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
        duracao = st.number_input("Duração (em dias)", min_value=0)

        submit_button = st.form_submit_button("Salvar")

        if submit_button:
            if not num_hierarquico or not nome_tarefa:
                st.warning("Preencha todos os campos obrigatórios.")
            elif num_hierarquico in dados_df["Número Hierárquico"].astype(str).values:
                st.error("Já existe uma tarefa com este Número Hierárquico.")
            else:
                nova_linha = [num_hierarquico, nome_tarefa, f"{perc_concluida:.1f}", f"{perc_previsto:.1f}", duracao]
                inserir_linha(sheet, nova_linha)
                st.success("✅ Tarefa inserida com sucesso!")
                st.rerun()
# ========== FORMULÁRIO DE EDIÇÃO ========== #
elif aba == "Editar Tarefa":
    st.header("✏️ Editar Tarefa")

    opcoes = [""] + [
        f"{num} - {nome}" 
        for num, nome in zip(dados_df["Número Hierárquico"].astype(str), dados_df["Nome da Tarefa"])
    ]
    mapa_numero = {f"{num} - {nome}": str(num) for num, nome in zip(dados_df["Número Hierárquico"].astype(str), dados_df["Nome da Tarefa"])}
    
    selecionado_exibido = st.selectbox("Selecione a Tarefa:", opcoes)

    if selecionado_exibido and selecionado_exibido in mapa_numero:
        selecionado = mapa_numero[selecionado_exibido]
        tarefa = dados_df[dados_df["Número Hierárquico"].astype(str) == selecionado].iloc[0]

        with st.form(key="editar_form"):
            # Campos da tarefa
            nome_tarefa = st.text_input("Nome da Tarefa", tarefa["Nome da Tarefa"])
            perc_concluida = st.number_input(
                "% Concluída", 
                min_value=0.0, 
                max_value=100.0, 
                step=0.1,
                value=parse_percent_string(tarefa["% Concluída"]), 
                format="%.1f"
            )
            perc_previsto = st.number_input(
                "% Prevista", 
                min_value=0.0, 
                max_value=100.0, 
                step=0.1,
                value=parse_percent_string(tarefa["% Prevista"]), 
                format="%.1f"
            )
            duracao = st.number_input("Duração (em dias)", min_value=0, value=int(tarefa["Duração"]))

            # 🔐 Autenticação
            st.markdown("#### 🔐 Identificação do Responsável")
            email = st.text_input("Email")
            senha = st.text_input("Senha", type="password")

            atualizar = st.form_submit_button("Atualizar")

            if atualizar:
                if not email or not senha:
                    st.warning("Por favor, preencha o email e a senha.")
                elif email in responsaveis and responsaveis[email] == senha:
                    from datetime import datetime
                    import pytz

                    fuso_brasilia = pytz.timezone("America/Sao_Paulo")
                    agora = datetime.now(fuso_brasilia).strftime("%H:%M %d/%m/%Y")
                    responsavel = f"{email} {agora}"

                    if "Responsável" not in dados_df.columns:
                        st.error("A coluna 'Responsável' não foi encontrada na planilha.")
                        st.stop()

                    nova_linha = [selecionado, nome_tarefa, f"{perc_concluida:.1f}", f"{perc_previsto:.1f}", duracao, responsavel]

                    sucesso = atualizar_linha(sheet, selecionado, nova_linha)
                    if sucesso:
                        st.success("✅ Tarefa atualizada com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao atualizar.")
                else:
                    st.error("❌ Email ou senha incorretos.")
# ========== VISUALIZAÇÃO DE DADOS ========== #
elif aba == "Visualizar Tarefas":
    st.header("📋 Visualização de Tarefas")
    if not dados_df.empty:
        dados_formatados = dados_df.copy()
        dados_formatados["% Concluída"] = (
            dados_formatados["% Concluída"].apply(parse_percent_string)
        ).round(1).astype(str) + "%"
        dados_formatados["% Prevista"] = (
            dados_formatados["% Prevista"].apply(parse_percent_string)
        ).round(1).astype(str) + "%"
        st.dataframe(dados_formatados, use_container_width=True)
    else:
        st.info("Nenhuma tarefa cadastrada ainda.")
