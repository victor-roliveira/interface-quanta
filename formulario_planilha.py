import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import pytz
import re # Importar a biblioteca re para expressões regulares

# ========== CONFIGURAÇÕES ========== #
st.set_page_config(page_title="Gerenciador de Planilha", layout="wide")

SCOPE = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

lista_autores = ["ALEXANDRE", "ARQ QUANTA", "BBRUNO MATHIAS", "BRUNO ALMEIDA", "BRUNO MATHIAS", "CAMILA", "CAROLINA", "GABRIEL M", "GABRIEL M. / MATHEUS F./CAROL", "GABRIEL MEURER", "IVANESSA", "KAYKE CHELI", "LEO", "MATHEUS F.", "MATHEUS FERREIRA", "TARCISIO", "TERCEIRIZADO - CAURIN", "TERCEIRIZADO - TEKRA", "THATY", "THATY E CAROL", "VANESSA", "VINICIUS COORD", "VITINHO", "WANDER"]

def autenticar_google_sheets():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key('1ZzMXgfnGvplabe9eNDCUXUbjuCXLieSgbpPUqAtBYOU').sheet1
        return sheet
    except Exception as e:
        st.error(f"Erro ao autenticar com o Google Sheets: {e}")
        return None

# Definir colunas_esperadas globalmente para que carregar_dados possa acessá-la
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
        result = sheet.append_row(nova_linha_str)
        updated_range = result.get('updates', {}).get('updatedRange', '')
        
        # === MODIFICAÇÃO CHAVE AQUI: Extração mais robusta do número da linha ===
        line_number = None
        if updated_range:
            # Expressão regular para encontrar um ou mais dígitos no final da string
            # ou após uma letra/cifrão ($)
            match = re.search(r'(\d+)$', updated_range)
            if match:
                line_number = int(match.group(1))
        # ======================================================================

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

# colunas_esperadas já está definida globalmente acima

# A checagem inicial de colunas também usará a função carregar_dados atualizada
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
    dados_df = carregar_dados(sheet) # Carrega dados usando expected_headers
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
        autor = st.text_input("AUTOR")
        responsavel_tecnico = st.text_input("RESPONSAVEL TÉCNICO (Lider)")
        inicio_contratual = st.date_input("INÍCIO CONTRATUAL", value=date.today())
        termino_contratual = st.date_input("TÉRMINO CONTRATUAL", value=date.today())
        
        # Estas variáveis são definidas como None inicialmente, não são inputs do usuário
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

    # Substitua st.text_input por st.selectbox
    # Adicione uma opção vazia no início para que o usuário possa "não filtrar" ou redefinir
    autor_filtro = st.selectbox("Selecione o autor para filtrar suas tarefas:", [""] + sorted(lista_autores))

    if autor_filtro: # Apenas carrega e filtra se um autor for selecionado
        dados_df = carregar_dados(sheet)
        
        df_usuario = dados_df[
            (dados_df["AUTOR"].str.lower() == autor_filtro.lower()) & # Comparação exata para o selectbox
            (dados_df["% CONCLUIDA"] < 100.0)
        ]

        if df_usuario.empty:
            st.warning("Nenhuma tarefa encontrada para este usuário ou todas as tarefas estão 100% concluídas.")
            # Não use st.stop() aqui, para permitir que o usuário mude o filtro
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
            selecionado_exibido = st.selectbox("Selecione a Tarefa:", options=opcoes_exibidas, index=default_index)

            if selecionado_exibido:
                indice_no_df_usuario = mapa_string_para_indice_df[selecionado_exibido]
                tarefa = df_usuario.iloc[indice_no_df_usuario].copy()
                
                linha_idx_para_atualizar = df_usuario.index[indice_no_df_usuario] + 2

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
                    autor = st.text_input("AUTOR", str(tarefa["AUTOR"]))
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
                        agora = datetime.now(fuso_brasilia).date()

                        if perc_concluida_antiga == 0.0 and perc_concluida > 0.0:
                            inicio_real_para_salvar = agora
                        else:
                            inicio_real_para_salvar = inicio_real_antigo

                        if perc_concluida_antiga < 100.0 and perc_concluida == 100.0:
                            termino_real_para_salvar = agora
                        else:
                            termino_real_para_salvar = termino_real_antigo
                        
                        data_revisao_doc_para_salvar = data_revisao_doc_antiga
                        data_revisao_projeto_para_salvar = data_revisao_projeto_antiga

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