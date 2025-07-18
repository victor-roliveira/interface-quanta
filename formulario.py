import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime, date
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
    df.columns = df.columns.str.strip()

    for col in ["Início", "Término", "Início Real", "Término Real"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: None if str(x).strip() == '' else x)
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
    
    return df

# Modificada a função atualizar_linha para aceitar os 10 valores já calculados
def atualizar_linha(sheet, numero_hierarquico, nova_linha_valores):
    registros = sheet.get_all_records() # Recarrega os registros para pegar a linha exata
    for idx, row in enumerate(registros, start=2):  # começa na linha 2 (linha 1 é cabeçalho)
        if str(row["Número Hierárquico"]).strip() == str(numero_hierarquico).strip():
            # nova_linha_valores já deve conter Início Real e Término Real calculados
            # Certifique-se de que nova_linha_valores tem 10 elementos na ordem correta
            sheet.update(f"A{idx}:J{idx}", [nova_linha_valores])
            return True
    return False

def inserir_linha(sheet, nova_linha):
    linha_para_inserir = nova_linha + ["", ""]
    sheet.append_row(linha_para_inserir)

def parse_percent_string(percent_str):
    try:
        if isinstance(percent_str, str):
            return float(percent_str.replace('%', '').replace(',', '.'))
        return float(percent_str)
    except:
        return 0.0

st.title("Gerenciador de Tarefas")

sheet = autenticar_google_sheets()
if not sheet:
    st.stop()

# Não carregamos dados_df aqui, vamos carregar dentro dos ifs para garantir frescor
# dados_df = carregar_dados(sheet) # Remova esta linha

colunas_esperadas = [
    "Número Hierárquico",
    "Nome da Tarefa",
    "% Concluída",
    "% Prevista",
    "Duração", 
    "Responsável",
    "Início",
    "Término",
    "Início Real",
    "Término Real"
]

# A verificação de colunas faltando pode ser feita com um carregamento único
# para evitar múltiplas chamadas ao sheets caso essa parte do código seja acessada sempre
temp_df_check = carregar_dados(sheet)
colunas_faltando = [col for col in colunas_esperadas if col not in temp_df_check.columns]
if colunas_faltando:
    st.error(f"⚠️ As seguintes colunas estão faltando na planilha: {colunas_faltando}. Por favor, adicione-as manualmente para o sistema funcionar corretamente.")
    st.stop()
del temp_df_check # Liberar memória da verificação temporária

aba = st.sidebar.radio("Escolha uma opção:", ["Inserir Tarefa", "Editar Tarefa", "Visualizar Tarefas"])

if aba == "Inserir Tarefa":
    st.header("➕ Inserir Nova Tarefa")
    # Carregar dados apenas quando necessário, para verificar duplicidade
    dados_df = carregar_dados(sheet) # Carrega os dados aqui
    with st.form(key="inserir_form"):
        num_hierarquico = st.text_input("Número Hierárquico")
        nome_tarefa = st.text_input("Nome da Tarefa")
        perc_concluida = st.number_input("% Concluída", min_value=0.0, max_value=100.0, step=0.1, format="%.1f", value=0.0)
        perc_previsto = st.number_input("% Prevista", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
        duracao = st.number_input("Duração (em dias)", min_value=0)
        responsavel = st.text_input("Responsável")
        inicio = st.date_input("Data Início", value=date.today()) 
        termino = st.date_input("Data Término", value=date.today())

        submit_button = st.form_submit_button("Salvar")

        if submit_button:
            if not num_hierarquico or not nome_tarefa:
                st.warning("Preencha todos os campos obrigatórios.")
            elif num_hierarquico in dados_df["Número Hierárquico"].astype(str).values:
                st.error("Já existe uma tarefa com este Número Hierárquico.")
            else:
                nova_linha_dados = [
                    num_hierarquico,
                    nome_tarefa,
                    f"{perc_concluida:.1f}",
                    f"{perc_previsto:.1f}",
                    duracao,
                    responsavel,
                    inicio.strftime("%d/%m/%Y"),
                    termino.strftime("%d/%m/%Y")
                ]
                inserir_linha(sheet, nova_linha_dados)
                st.success("✅ Tarefa inserida com sucesso!")
                st.rerun()

elif aba == "Editar Tarefa":
    st.header("✏️ Editar Tarefa")

    email = st.text_input("Digite seu email para filtrar suas tarefas:")

    if email:
        # Carregar dados aqui para garantir que estão atualizados no momento da seleção
        dados_df = carregar_dados(sheet) # Carrega os dados aqui novamente
        df_usuario = dados_df[dados_df["Responsável"].astype(str).str.contains(email, case=False, na=False)]

        if df_usuario.empty:
            st.warning("Nenhuma tarefa encontrada para este email.")
            st.stop()

        opcoes = [""] + [
            f"{num} - {nome}" 
            for num, nome in zip(df_usuario["Número Hierárquico"].astype(str), df_usuario["Nome da Tarefa"])
        ]
        mapa_numero = {f"{num} - {nome}": str(num) for num, nome in zip(df_usuario["Número Hierárquico"].astype(str), df_usuario["Nome da Tarefa"])}

        selecionado_exibido = st.selectbox("Selecione a Tarefa:", opcoes)

        if selecionado_exibido and selecionado_exibido in mapa_numero:
            selecionado = mapa_numero[selecionado_exibido]
            # Usar .copy() para evitar SettingWithCopyWarning ao modificar a série
            tarefa = dados_df[dados_df["Número Hierárquico"].astype(str) == selecionado].iloc[0].copy()

            # Obtenha o valor antigo de % Concluída ANTES de exibir o formulário
            perc_concluida_antiga = parse_percent_string(tarefa["% Concluída"])
            
            # Obtenha os valores antigos de Início Real e Término Real
            # Certifique-se de que são objetos date ou None
            inicio_real_antigo = tarefa["Início Real"].date() if pd.notnull(tarefa["Início Real"]) else None
            termino_real_antigo = tarefa["Término Real"].date() if pd.notnull(tarefa["Término Real"]) else None

            with st.form(key="editar_form"):
                nome_tarefa = st.text_input("Nome da Tarefa", tarefa["Nome da Tarefa"])
                perc_concluida = st.number_input("% Concluída", min_value=0.0, max_value=100.0, step=0.1,
                                                 value=parse_percent_string(tarefa["% Concluída"]), format="%.1f")
                perc_previsto = st.number_input("% Prevista", min_value=0.0, max_value=100.0, step=0.1,
                                                 value=parse_percent_string(tarefa["% Prevista"]), format="%.1f")
                duracao = st.number_input("Duração (em dias)", min_value=0, value=int(tarefa["Duração"]))
                
                inicio_dt = tarefa["Início"].date() if pd.notnull(tarefa["Início"]) and isinstance(tarefa["Início"], pd.Timestamp) else None
                termino_dt = tarefa["Término"].date() if pd.notnull(tarefa["Término"]) and isinstance(tarefa["Término"], pd.Timestamp) else None
                
                inicio = st.date_input("Data de Início", value=inicio_dt)
                termino = st.date_input("Data de Término", value=termino_dt)

                atualizar = st.form_submit_button("Atualizar")

                if atualizar:
                    fuso_brasilia = pytz.timezone("America/Sao_Paulo")
                    agora = datetime.now(fuso_brasilia).date() # Apenas a data para Início Real/Término Real
                    responsavel = f"{email} {datetime.now(fuso_brasilia).strftime('%H:%M %d/%m/%Y')}"

                    # Lógica para Início Real
                    inicio_real_para_salvar = inicio_real_antigo
                    if perc_concluida_antiga == 0.0 and perc_concluida > 0.0:
                        inicio_real_para_salvar = agora

                    # Lógica para Término Real
                    termino_real_para_salvar = termino_real_antigo
                    if perc_concluida_antiga < 100.0 and perc_concluida == 100.0:
                        termino_real_para_salvar = agora

                    # Formata as datas para a planilha (strings "DD/MM/YYYY" ou vazias)
                    inicio_real_str = inicio_real_para_salvar.strftime("%d/%m/%Y") if inicio_real_para_salvar else ""
                    termino_real_str = termino_real_para_salvar.strftime("%d/%m/%Y") if termino_real_para_salvar else ""

                    nova_linha_valores = [
                        selecionado,
                        nome_tarefa,
                        f"{perc_concluida:.1f}",
                        f"{perc_previsto:.1f}",
                        duracao,
                        responsavel,
                        inicio.strftime("%d/%m/%Y"),
                        termino.strftime("%d/%m/%Y"),
                        inicio_real_str,
                        termino_real_str
                    ]
                    
                    sucesso = atualizar_linha(sheet, selecionado, nova_linha_valores)
                    if sucesso:
                        st.success("✅ Tarefa atualizada com sucesso!")
                        st.rerun() # Recarrega a aplicação para mostrar os dados atualizados
                    else:
                        st.error("❌ Erro ao atualizar.")

elif aba == "Visualizar Tarefas":
    st.header("📋 Visualização de Tarefas")
    dados_df = carregar_dados(sheet) # Carrega os dados aqui para visualização
    if not dados_df.empty:
        dados_formatados = dados_df.copy()
        
        for col in ["Início", "Término", "Início Real", "Término Real"]:
            if col in dados_formatados.columns:
                dados_formatados[col] = dados_formatados[col].dt.strftime('%d/%m/%Y').fillna('')

        dados_formatados["% Concluída"] = (
            dados_formatados["% Concluída"].apply(parse_percent_string)
        ).round(1).astype(str) + "%"
        dados_formatados["% Prevista"] = (
            dados_formatados["% Prevista"].apply(parse_percent_string)
        ).round(1).astype(str) + "%"
        
        st.dataframe(dados_formatados, use_container_width=True)
    else:
        st.info("Nenhuma tarefa cadastrada ainda.")