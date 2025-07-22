import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, date
import pytz
import re
import os

responsaveis = {
    "aleframos62@gmail.com": "abcd1234",
    "hagata@gmail.com": "abcde123"
}

# ========== CONFIGURAÇÕES DE ACESSO ========== #
st.set_page_config(page_title="Gerenciador de Tarefas", layout="wide")

lista_autores = ["ALEXANDRE", "ARQ QUANTA", "BBRUNO MATHIAS", "BRUNO ALMEIDA", "BRUNO MATHIAS", "CAMILA", "CAROLINA", "GABRIEL M", "GABRIEL M. / MATHEUS F./CAROL", "GABRIEL MEURER", "IVANESSA", "KAYKE CHELI", "LEO", "MATHEUS F.", "MATHEUS FERREIRA", "TARCISIO", "TERCEIRIZADO - CAURIN", "TERCEIRIZADO - TEKRA", "THATY", "THATY E CAROL", "VANESSA", "VINICIUS COORD", "VITINHO", "WANDER"]

SCOPE = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

# 🔐 Autenticando com o Google Sheets PRODUÇÃO
def autenticar_google_sheets():
    try:
        # Pega o JSON da variável de ambiente
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        if not creds_json:
            st.error("Variável GOOGLE_SHEETS_CREDENTIALS não encontrada.")
            return None

        # Converte a string JSON em dict
        credentials_info = json.loads(creds_json)

        # Cria credenciais usando google.oauth2 (mais moderno)
        creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPE)

        # Autoriza o cliente gspread
        client = gspread.authorize(creds)

        # Abre a planilha pelo ID e pega a primeira aba
        sheet = client.open_by_key('1ZzMXgfnGvplabe9eNDCUXUbjuCXLieSgbpPUqAtBYOU').sheet1  
        return sheet

    except Exception as e:
        st.error(f"Erro ao autenticar com o Google Sheets: {e}")
        return None

colunas_esperadas = [
    "% CONCLUIDA", "MEMORIAL DE CÁLCULO", "MEMORIAL DE DESCRITIVO", "EDT", "OS",
    "PRODUTO", "NOME DA OS", "TIPO DE PROJETO", "NOME DA TAREFA", "DISCIPLINA",
    "SUBDISCIPLINA", "AUTOR", "RESPONSAVEL TÉCNICO (Lider)", "INÍCIO CONTRATUAL",
    "TÉRMINO CONTRATUAL", "INÍCIO REAL", "TÉRMINO REAL", "DATA REVISÃO DOC",
    "DATA REVISÃO PROJETO", "DURAÇÃO PLANEJADA (DIAS)", "DURAÇÃO REAL (DIAS)",
    "% AVANÇO PLANEJADO", "% AVANÇO REAL", "HH Orçado", "BCWS_HH", "BCWP_HH",
    "ACWP_HH", "SPI_HH", "CPI_HH", "EAC_HH", "OBSERVAÇÕES",
]

def carregar_dados(sheet):
    try:
        dados = sheet.get_all_records(expected_headers=colunas_esperadas)
    except gspread.exceptions.GSpreadException as e:
        st.error(f"Erro ao carregar dados da planilha. Verifique se a lista 'colunas_esperadas' no código corresponde EXATAMENTE aos cabeçalhos e número de colunas na sua planilha. Detalhes: {e}")
        st.stop()
    
    df = pd.DataFrame(dados)
    
    text_cols_to_force_str = [
        "EDT", "OS", "NOME DA TAREFA", "MEMORIAL DE CÁLCULO", "MEMORIAL DE DESCRITIVO", 
        "PRODUTO", "NOME DA OS", "TIPO DE PROJETO", "DISCIPLINA", "SUBDISCIPLINA", 
        "AUTOR", "RESPONSAVEL TÉCNICO (Lider)", "HH Orçado", "BCWS_HH", "BCWP_HH", 
        "ACWP_HH", "SPI_HH", "CPI_HH", "EAC_HH", "OBSERVAÇÕES"
    ]
    for col in text_cols_to_force_str:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna('') 
            
    numeric_cols_to_force_num = [
        "DURAÇÃO PLANEJADA (DIAS)", "DURAÇÃO REAL (DIAS)"
    ]
    for col in numeric_cols_to_force_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    for col in ["% CONCLUIDA", "% AVANÇO PLANEJADO", "% AVANÇO REAL"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_percent_string)

    date_cols = ["INÍCIO CONTRATUAL", "TÉRMINO CONTRATUAL", "INÍCIO REAL", "TÉRMINO REAL", 
                 "DATA REVISÃO DOC", "DATA REVISÃO PROJETO"]
    for col in date_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: None if str(x).strip() == '' else x)
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
    
    # --- Nova parte para extrair o nome base do autor ---
    if "AUTOR" in df.columns:
        # Regex para encontrar o nome base antes de "(Editado em DD/MM/YYYY HH:MM)"
        # ou o nome completo se não houver timestamp
        df['AUTOR_BASE'] = df['AUTOR'].apply(lambda x: re.sub(r'\s*\(Editado em \d{2}/\d{2}/\d{4} \d{2}:\d{2}\)$', '', x) if isinstance(x, str) else x)
        # Converte para maiúsculas para facilitar a comparação insensível a maiúsculas/minúsculas
        df['AUTOR_BASE'] = df['AUTOR_BASE'].str.upper()
    # --- Fim da nova parte ---

    return df

def get_column_letter(n):
    """Converte um número de coluna em letra do Google Sheets (A, B, ..., Z, AA, AB, etc.)"""
    result = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result

def atualizar_linha(sheet, idx, nova_linha_valores):
    try:
        coluna_final = get_column_letter(len(nova_linha_valores))
        range_name = f"A{idx}:{coluna_final}{idx}"
        
        sheet.update(values=[nova_linha_valores], range_name=range_name)
        return True
    except Exception as e:
        print(f"Erro ao atualizar a linha {idx}: {e}")
        st.error(f"Erro ao atualizar a linha: {e}. Verifique o console para mais detalhes.")
        return False

def inserir_linha(sheet, nova_linha):
    nova_linha_str = [str(val) if val is not None else '' for val in nova_linha]
    
    try:
        try:
            sheet.acell('A1') 
        except Exception as e:
            print(f"Aviso: Não foi possível ler A1 antes de append_row: {e}")

        result = sheet.append_row(nova_linha_str)
        updated_range = result.get('updates', {}).get('updatedRange', '')
        
        line_number = None
        if updated_range:
            match = re.search(r'(\d+)$', updated_range)
            if match:
                line_number = int(match.group(1))

        return line_number
    except Exception as e:
        st.error(f"Erro ao inserir a linha: {e}")
        return None

def parse_percent_string(percent_str):
    try:
        if isinstance(percent_str, (int, float)):
            return float(percent_str)
        if isinstance(percent_str, str):
            cleaned_str = percent_str.replace('%', '').replace(',', '.').strip()
            if cleaned_str:
                return float(cleaned_str)
        return 0.0
    except ValueError:
        return 0.0


st.title("Gerenciador de Planilha")

sheet = autenticar_google_sheets()
if not sheet:
    st.stop()

temp_df_check = carregar_dados(sheet)

for col_check in ["EDT", "OS", "NOME DA TAREFA"]:
    if col_check not in temp_df_check.columns:
        st.error(f"A coluna '{col_check}' é essencial e não foi encontrada. Verifique a lista 'colunas_esperadas' ou sua planilha.")
        st.stop()

colunas_faltando = [col for col in colunas_esperadas if col not in temp_df_check.columns]
if colunas_faltando:
    st.warning(f"⚠️ As seguintes colunas estão faltando na sua lista de 'colunas_esperadas' ou na planilha: {', '.join(colunas_faltando)}. Por favor, adicione-as.")
del temp_df_check

aba = st.sidebar.radio("Escolha uma opção:", ["Inserir Tarefa", "Editar Tarefa", "Visualizar Tarefas"])

# --- Seção Inserir Tarefa ---
if aba == "Inserir Tarefa":
    st.header("➕ Inserir Nova Tarefa")
    dados_df = carregar_dados(sheet)
    with st.form(key="inserir_form"):
        perc_concluida = st.number_input("% CONCLUIDA", min_value=0.0, max_value=100.0, step=0.1, format="%.1f", value=0.0)
        memorial_calculo = st.text_input("MEMORIAL DE CALCULO")
        memorial_descritivo = st.text_input("MEMORIAL DE DESCRITIVO")
        num_hierarquico = st.text_input("EDT (Número Hierárquico)", help="Este campo deve ser único para cada tarefa, em combinação com a OS e Nome da Tarefa.")
        os = st.text_input("OS")
        produto = st.text_input("PRODUTO")
        nome_os = st.text_input("NOME DA OS")
        tipo_projeto = st.text_input("TIPO DE PROJETO")
        nome_tarefa = st.text_input("NOME DA TAREFA")
        disciplina = st.text_input("DISCIPLINA")
        subdisciplina = st.text_input("SUBDISCIPLINA")
        autor = st.selectbox("AUTOR", options=[""] + sorted(lista_autores)) 
        responsavel_tecnico = st.text_input("RESPONSAVEL TÉCNICO (Lider)")
        inicio_contratual = st.date_input("INÍCIO CONTRATUAL", value=date.today())
        termino_contratual = st.date_input("TÉRMINO CONTRATUAL", value=date.today())
        
        data_revisao_doc = None
        data_revisao_projeto = None
        
        duracao_planejada = st.number_input("DURAÇÃO PLANEJADA (DIAS)", min_value=0)
        duracao_real = st.number_input("DURAÇÃO REAL (DIAS)", min_value=0)
        avanco_planejado = st.number_input("% AVANÇO PLANEJADO", min_value=0.0, max_value=100.0, step=0.1, format="%.1f", value=0.0)
        avanco_real = st.number_input("% AVANÇO REAL", min_value=0.0, max_value=100.0, step=0.1, format="%.1f", value=0.0)
        hh_orcado = st.text_input("HH Orçado")
        bcws_hh = st.text_input("BCWS_HH")
        bcwp_hh = st.text_input("BCWP_HH")
        acwp_hh = st.text_input("ACWP_HH")
        spi_hh = st.text_input("SPI_HH")
        cpi_hh = st.text_input("CPI_HH")
        eac_hh = st.text_input("EAC_HH")
        observacoes = st.text_input("OBSERVAÇÕES")

        submit_button = st.form_submit_button("Salvar")

        if submit_button:
            if not num_hierarquico or not nome_tarefa or not os:
                st.warning("Preencha os campos 'EDT', 'NOME DA TAREFA' e 'OS' (obrigatórios).")
            elif autor == "": 
                st.warning("Por favor, selecione um Autor.")
            elif any((dados_df["EDT"] == num_hierarquico) & 
                             (dados_df["NOME DA TAREFA"].str.lower() == nome_tarefa.lower()) &
                             (dados_df["OS"].str.lower() == os.lower())):
                st.error("Já existe uma tarefa com esta combinação de EDT, Nome da Tarefa e OS.")
            else:
                fuso_brasilia = pytz.timezone("America/Sao_Paulo")
                agora = datetime.now(fuso_brasilia).date()

                inicio_real_para_salvar = agora if perc_concluida > 0.0 else None
                termino_real_para_salvar = agora if perc_concluida == 100.0 else None

                data_revisao_doc_para_salvar = None
                data_revisao_projeto_para_salvar = None

                valores_para_salvar_dict = {
                    "% CONCLUIDA": f"{perc_concluida:.1f}",
                    "MEMORIAL DE CÁLCULO": memorial_calculo,
                    "MEMORIAL DE DESCRITIVO": memorial_descritivo,
                    "EDT": num_hierarquico,
                    "OS": os,
                    "PRODUTO": produto,
                    "NOME DA OS": nome_os,
                    "TIPO DE PROJETO": tipo_projeto,
                    "NOME DA TAREFA": nome_tarefa,
                    "DISCIPLINA": disciplina,
                    "SUBDISCIPLINA": subdisciplina,
                    "AUTOR": autor,
                    "RESPONSAVEL TÉCNICO (Lider)": responsavel_tecnico,
                    "INÍCIO CONTRATUAL": inicio_contratual.strftime("%d/%m/%Y") if inicio_contratual else "",
                    "TÉRMINO CONTRATUAL": termino_contratual.strftime("%d/%m/%Y") if termino_contratual else "",
                    "INÍCIO REAL": inicio_real_para_salvar.strftime("%d/%m/%Y") if inicio_real_para_salvar else "",
                    "TÉRMINO REAL": termino_real_para_salvar.strftime("%d/%m/%Y") if termino_real_para_salvar else "",
                    "DATA REVISÃO DOC": data_revisao_doc_para_salvar.strftime("%d/%m/%Y") if data_revisao_doc_para_salvar else "",
                    "DATA REVISÃO PROJETO": data_revisao_projeto_para_salvar.strftime("%d/%m/%Y") if data_revisao_projeto_para_salvar else "",
                    "DURAÇÃO PLANEJADA (DIAS)": duracao_planejada,
                    "DURAÇÃO REAL (DIAS)": duracao_real,
                    "% AVANÇO PLANEJADO": f"{avanco_planejado:.1f}",
                    "% AVANÇO REAL": f"{avanco_real:.1f}",
                    "HH Orçado": hh_orcado,
                    "BCWS_HH": bcws_hh,
                    "BCWP_HH": bcwp_hh,
                    "ACWP_HH": acwp_hh,
                    "SPI_HH": spi_hh,
                    "CPI_HH": cpi_hh,
                    "EAC_HH": eac_hh,
                    "OBSERVAÇÕES": observacoes
                }
                
                nova_linha_dados = [str(valores_para_salvar_dict.get(col, "")) for col in colunas_esperadas]

                linha_inserida = inserir_linha(sheet, nova_linha_dados)
                if linha_inserida:
                    st.success(f"✅ Tarefa inserida com sucesso na linha **{linha_inserida}** da planilha!")
                    st.rerun()
                else:
                    st.error("❌ Erro ao inserir a tarefa. Verifique o console para mais detalhes.")


# --- Seção Editar Tarefa ---
elif aba == "Editar Tarefa":
    st.header("✏️ Editar Tarefa")

    autor_filtro = st.selectbox("Selecione o autor para filtrar suas tarefas:", [""] + sorted(lista_autores))

    if autor_filtro:
        dados_df = carregar_dados(sheet)
        
        # --- FILTRO ATUALIZADO ---
        # Converte o autor_filtro para maiúsculas para comparação consistente
        autor_filtro_upper = autor_filtro.upper()
        
        df_usuario = dados_df[
            # Agora filtra pela nova coluna 'AUTOR_BASE' que contém apenas o nome do autor
            (dados_df["AUTOR_BASE"] == autor_filtro_upper) & 
            (dados_df["% CONCLUIDA"] < 100.0)
        ]
        # --- FIM DO FILTRO ATUALIZADO ---

        if df_usuario.empty:
            st.warning("Nenhuma tarefa encontrada para este usuário ou todas as tarefas estão 100% concluídas.")
        else:
            opcoes_exibidas = [
                f"OS: {os_val} / EDT: {num} / Tarefa: {nome}"
                for os_val, num, nome in zip(df_usuario["OS"], df_usuario["EDT"], df_usuario["NOME DA TAREFA"])
            ]
            
            mapa_string_para_indice_df = {
                f"OS: {os_val} / EDT: {num} / Tarefa: {nome}": idx
                for idx, (os_val, num, nome) in enumerate(zip(df_usuario["OS"], df_usuario["EDT"], df_usuario["NOME DA TAREFA"]))
            }

            default_index = 0
            # Garante que o índice padrão seja válido para evitar erro se houver apenas uma opção
            if not opcoes_exibidas: 
                selecionado_exibido = None
            else:
                selecionado_exibido = st.selectbox("Selecione a Tarefa:", options=opcoes_exibidas, index=default_index)

            if selecionado_exibido:
                indice_no_df_usuario = mapa_string_para_indice_df[selecionado_exibido]
                tarefa = df_usuario.iloc[indice_no_df_usuario].copy()
                    
                    # --- CORREÇÃO AQUI: ENCONTRAR A LINHA REAL NA PLANILHA ---
                    # Para encontrar a linha real, precisamos usar as colunas que juntas identificam UNICAMENTE a tarefa.
                    # Baseado na sua informação anterior, essa combinação é "OS", "EDT" e "NOME DA TAREFA".
                    
                    # Encontra o índice (0-based) da tarefa correspondente no DataFrame COMPLETO (dados_df)
                    # onde todos os três critérios (OS, EDT, NOME DA TAREFA) são atendidos.
                    
                    # Usamos .astype(str) nas colunas para garantir que a comparação seja feita entre strings
                    # e evitar problemas com tipos de dados misturados, especialmente se houver NaN/None em alguma delas.
                    
                matched_rows_mask = (
                        (dados_df["OS"].astype(str) == str(tarefa["OS"])) &
                        (dados_df["EDT"].astype(str) == str(tarefa["EDT"])) &
                        (dados_df["NOME DA TAREFA"].astype(str) == str(tarefa["NOME DA TAREFA"]))
                )                    
                    # Verifica se alguma linha foi encontrada
                if not dados_df[matched_rows_mask].empty:
                        # Pega o primeiro índice (0-based) do DataFrame correspondente à tarefa
                    df_index = dados_df[matched_rows_mask].index[0]
                        
                        # Converte o índice do DataFrame (0-based) para o número da linha na planilha do Google Sheets (1-based)
                        # A linha 1 da planilha é o cabeçalho, então o primeiro registro (índice 0) está na linha 2.
                    linha_idx_para_atualizar = df_index + 2
                else:
                    st.error("Erro: A tarefa selecionada não pôde ser encontrada na planilha principal com base em OS, EDT e NOME DA TAREFA. Isso pode indicar um problema de dados ou um cache desatualizado. Por favor, recarregue a página.")
                    st.stop()

                st.info(f"Tentando atualizar a linha na planilha: **{linha_idx_para_atualizar}**")

                perc_concluida_antiga = float(tarefa["% CONCLUIDA"])

                inicio_contratual_valor = pd.to_datetime(tarefa["INÍCIO CONTRATUAL"], errors='coerce')
                inicio_contratual_data = inicio_contratual_valor.date() if pd.notnull(inicio_contratual_valor) else None

                termino_contratual_valor = pd.to_datetime(tarefa["TÉRMINO CONTRATUAL"], errors='coerce')
                termino_contratual_data = termino_contratual_valor.date() if pd.notnull(termino_contratual_valor) else None
                
                inicio_real_antigo = pd.to_datetime(tarefa["INÍCIO REAL"], errors='coerce').date() if pd.notnull(pd.to_datetime(tarefa["INÍCIO REAL"], errors='coerce')) else None
                termino_real_antigo = pd.to_datetime(tarefa["TÉRMINO REAL"], errors='coerce').date() if pd.notnull(pd.to_datetime(tarefa["TÉRMINO REAL"], errors='coerce')) else None
                data_revisao_doc_antiga = pd.to_datetime(tarefa["DATA REVISÃO DOC"], errors='coerce').date() if pd.notnull(pd.to_datetime(tarefa["DATA REVISÃO DOC"], errors='coerce')) else None
                data_revisao_projeto_antiga = pd.to_datetime(tarefa["DATA REVISÃO PROJETO"], errors='coerce').date() if pd.notnull(pd.to_datetime(tarefa["DATA REVISÃO PROJETO"], errors='coerce')) else None


                with st.form(key="editar_form"):
                    perc_concluida = st.number_input("% CONCLUIDA", min_value=0.0, max_value=100.0, step=0.1, value=perc_concluida_antiga, format="%.1f")
                    memorial_calculo = st.text_input("MEMORIAL DE CALCULO", str(tarefa["MEMORIAL DE CÁLCULO"]))
                    memorial_descritivo = st.text_input("MEMORIAL DE DESCRITIVO", str(tarefa["MEMORIAL DE DESCRITIVO"]))
                    num_hierarquico = st.text_input("EDT", str(tarefa["EDT"]), disabled=True, help="EDT não pode ser alterado.")
                    os_tarefa = st.text_input("OS", str(tarefa["OS"]), disabled=True, help="OS não pode ser alterado.")
                    produto = st.text_input("PRODUTO", str(tarefa["PRODUTO"]))
                    nome_os = st.text_input("NOME DA OS", str(tarefa["NOME DA OS"]))
                    tipo_projeto = st.text_input("TIPO DE PROJETO", str(tarefa["TIPO DE PROJETO"]))
                    nome_tarefa = st.text_input("NOME DA TAREFA", str(tarefa["NOME DA TAREFA"]), disabled=True, help="Nome da Tarefa não pode ser alterado.")
                    disciplina = st.text_input("DISCIPLINA", str(tarefa["DISCIPLINA"]))
                    subdisciplina = st.text_input("SUBDISCIPLINA", str(tarefa["SUBDISCIPLINA"]))
                    autor = st.text_input("AUTOR", str(tarefa["AUTOR"]), disabled=True) 
                    responsavel_tecnico = st.text_input("RESPONSAVEL TÉCNICO (Lider)", str(tarefa["RESPONSAVEL TÉCNICO (Lider)"]))

                    inicio_contratual = st.date_input("INÍCIO CONTRATUAL", value=inicio_contratual_data or date.today())
                    termino_contratual = st.date_input("TÉRMINO CONTRATUAL", value=termino_contratual_data or date.today())
                    
                    duracao_planejada_val = int(tarefa["DURAÇÃO PLANEJADA (DIAS)"]) if pd.notnull(tarefa["DURAÇÃO PLANEJADA (DIAS)"]) else 0
                    duracao_planejada = st.number_input("DURAÇÃO PLANEJADA (DIAS)", min_value=0, value=duracao_planejada_val)
                    
                    duracao_real_val = int(tarefa["DURAÇÃO REAL (DIAS)"]) if pd.notnull(tarefa["DURAÇÃO REAL (DIAS)"]) else 0
                    duracao_real = st.number_input("DURAÇÃO REAL (DIAS)", min_value=0, value=duracao_real_val)

                    avanco_planejado = st.number_input("% AVANÇO PLANEJADO", min_value=0.0, max_value=100.0, step=0.1, value=float(tarefa["% AVANÇO PLANEJADO"]))
                    avanco_real = st.number_input("% AVANÇO REAL", min_value=0.0, max_value=100.0, step=0.1, value=float(tarefa["% AVANÇO REAL"]))
                    
                    hh_orcado = st.text_input("HH Orçado", str(tarefa["HH Orçado"]))
                    bcws_hh = st.text_input("BCWS_HH", str(tarefa["BCWS_HH"]))
                    bcwp_hh = st.text_input("BCWP_HH", str(tarefa["BCWP_HH"]))
                    acwp_hh = st.text_input("ACWP_HH", str(tarefa["ACWP_HH"]))
                    spi_hh = st.text_input("SPI_HH", str(tarefa["SPI_HH"]))
                    cpi_hh = st.text_input("CPI_HH", str(tarefa["CPI_HH"]))
                    eac_hh = st.text_input("EAC_HH", str(tarefa["EAC_HH"]))
                    observacoes = st.text_input("OBSERVAÇÕES", str(tarefa["OBSERVAÇÕES"]))

                    atualizar = st.form_submit_button("Atualizar")

                    if atualizar:
                        fuso_brasilia = pytz.timezone("America/Sao_Paulo")
                        agora_completa = datetime.now(fuso_brasilia) 
                        agora_data = agora_completa.date() 

                        if perc_concluida_antiga == 0.0 and perc_concluida > 0.0:
                            inicio_real_para_salvar = agora_data
                        else:
                            inicio_real_para_salvar = inicio_real_antigo

                        if perc_concluida_antiga < 100.0 and perc_concluida == 100.0:
                            termino_real_para_salvar = agora_data
                        else:
                            termino_real_para_salvar = termino_real_antigo
                        
                        data_revisao_doc_para_salvar = data_revisao_doc_antiga
                        data_revisao_projeto_para_salvar = data_revisao_projeto_antiga

                        autor_original_da_tarefa = str(tarefa["AUTOR"])
                        data_hora_edicao = agora_completa.strftime("%d/%m/%Y %H:%M")
                        
                        regex_timestamp = r'\s*\(Editado em \d{2}/\d{2}/\d{4} \d{2}:\d{2}\)$'
                        
                        if re.search(regex_timestamp, autor_original_da_tarefa):
                            autor_com_data_hora = re.sub(regex_timestamp, f' (Editado em {data_hora_edicao})', autor_original_da_tarefa)
                        else:
                            autor_com_data_hora = f"{autor_original_da_tarefa} (Editado em {data_hora_edicao})"

                        valores_para_salvar_dict = {
                            "% CONCLUIDA": f"{perc_concluida:.1f}",
                            "MEMORIAL DE CÁLCULO": memorial_calculo,
                            "MEMORIAL DE DESCRITIVO": memorial_descritivo,
                            "EDT": num_hierarquico,
                            "OS": os_tarefa,
                            "PRODUTO": produto,
                            "NOME DA OS": nome_os,
                            "TIPO DE PROJETO": tipo_projeto,
                            "NOME DA TAREFA": nome_tarefa,
                            "DISCIPLINA": disciplina,
                            "SUBDISCIPLINA": subdisciplina,
                            "AUTOR": autor_com_data_hora, 
                            "RESPONSAVEL TÉCNICO (Lider)": responsavel_tecnico,
                            "INÍCIO CONTRATUAL": inicio_contratual.strftime("%d/%m/%Y") if inicio_contratual else "",
                            "TÉRMINO CONTRATUAL": termino_contratual.strftime("%d/%m/%Y") if termino_contratual else "",
                            "INÍCIO REAL": inicio_real_para_salvar.strftime("%d/%m/%Y") if inicio_real_para_salvar else "",
                            "TÉRMINO REAL": termino_real_para_salvar.strftime("%d/%m/%Y") if termino_real_para_salvar else "",
                            "DATA REVISÃO DOC": data_revisao_doc_para_salvar.strftime("%d/%m/%Y") if data_revisao_doc_para_salvar else "",
                            "DATA REVISÃO PROJETO": data_revisao_projeto_para_salvar.strftime("%d/%m/%Y") if data_revisao_projeto_para_salvar else "",
                            "DURAÇÃO PLANEJADA (DIAS)": duracao_planejada,
                            "DURAÇÃO REAL (DIAS)": duracao_real,
                            "% AVANÇO PLANEJADO": f"{avanco_planejado:.1f}",
                            "% AVANÇO REAL": f"{avanco_real:.1f}",
                            "HH Orçado": hh_orcado,
                            "BCWS_HH": bcws_hh,
                            "BCWP_HH": bcwp_hh,
                            "ACWP_HH": acwp_hh,
                            "SPI_HH": spi_hh,
                            "CPI_HH": cpi_hh,
                            "EAC_HH": eac_hh,
                            "OBSERVAÇÕES": observacoes
                        }
                        
                        nova_linha_valores = [str(valores_para_salvar_dict.get(col, "")) for col in colunas_esperadas]

                        sucesso = atualizar_linha(sheet, linha_idx_para_atualizar, nova_linha_valores)
                        if sucesso:
                            st.success("✅ Tarefa atualizada com sucesso!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao atualizar. Verifique o console para mais detalhes.")

# --- Seção Visualizar Tarefas ---
elif aba == "Visualizar Tarefas":
    st.header("📋 Visualização de Tarefas")
    dados_df = carregar_dados(sheet)
    
    if not dados_df.empty:
        dados_formatados = dados_df.copy()

        colunas_data = [
            "INÍCIO CONTRATUAL", "TÉRMINO CONTRATUAL", "INÍCIO REAL", "TÉRMINO REAL",
            "DATA REVISÃO DOC", "DATA REVISÃO PROJETO"
        ]
        for col in colunas_data:
            if col in dados_formatados.columns:
                dados_formatados[col] = dados_formatados[col].dt.strftime('%d/%m/%Y').fillna('')

        colunas_percentuais = [
            "% CONCLUIDA", "% AVANÇO PLANEJADO", "% AVANÇO REAL"
        ]
        for col in colunas_percentuais:
            if col in dados_formatados.columns:
                dados_formatados[col] = (
                    dados_formatados[col].round(1).astype(str) + "%"
                )
        
        for col in ["DURAÇÃO PLANEJADA (DIAS)", "DURAÇÃO REAL (DIAS)"]:
            if col in dados_formatados.columns:
                dados_formatados[col] = dados_formatados[col].astype(str)

        colunas_ordenadas = [col for col in colunas_esperadas if col in dados_formatados.columns]
        dados_formatados = dados_formatados[colunas_ordenadas]

        st.dataframe(dados_formatados, use_container_width=True)
    else:
        st.info("Nenhuma tarefa cadastrada ainda.")