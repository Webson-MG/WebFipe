import streamlit as st
import requests

# --- Configuração da API FIPE ---
BASE_URL = "https://veiculos.fipe.org.br/api/veiculos"
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://veiculos.fipe.org.br/",
}

def get_tabela_referencia():
    resp = requests.post(f"{BASE_URL}/ConsultarTabelaDeReferencia", headers=HEADERS)
    return resp.json()[0]["Codigo"]

def get_marcas(tipo, tabela):
    payload = {"codigoTabelaReferencia": tabela, "codigoTipoVeiculo": tipo}
    resp = requests.post(f"{BASE_URL}/ConsultarMarcas", headers=HEADERS, json=payload)
    return resp.json()

def get_modelos(tipo, tabela, marca):
    payload = {
        "codigoTabelaReferencia": tabela,
        "codigoTipoVeiculo": tipo,
        "codigoMarca": marca,
    }
    try:
        resp = requests.post(f"{BASE_URL}/ConsultarModelos", headers=HEADERS, json=payload)
        if resp.status_code != 200:
            st.error(f"Erro ao consultar modelos: {resp.status_code}")
            return []
        return resp.json().get("Modelos", [])
    except Exception as e:
        st.error(f"Erro ao obter modelos: {e}")
        st.text(resp.text)
        return []

def get_anos(tipo, tabela, marca, modelo):
    payload = {
        "codigoTabelaReferencia": tabela,
        "codigoTipoVeiculo": tipo,
        "codigoMarca": marca,
        "codigoModelo": modelo,
    }
    try:
        resp = requests.post(f"{BASE_URL}/ConsultarAnoModelo", headers=HEADERS, json=payload)

        if resp.status_code != 200:
            st.error(f"Erro HTTP ao consultar anos: {resp.status_code}")
            return []

        return resp.json()

    except requests.exceptions.RequestException as e:
        st.error(f"Erro de rede ao consultar anos: {e}")
        return []
    except ValueError as e:
        st.error(f"Resposta inválida da FIPE ao consultar anos (não é JSON): {e}")
        st.text(resp.text)  # mostra o conteúdo bruto da resposta para debug
        return []

def get_valor(tipo, tabela, marca, modelo, ano, cod_combustivel):
    payload = {
        "codigoTabelaReferencia": tabela,
        "codigoMarca": marca,
        "codigoModelo": modelo,
        "codigoTipoVeiculo": tipo,
        "anoModelo": int(ano),
        "codigoTipoCombustivel": int(cod_combustivel),
        "tipoConsulta": "tradicional",
        "modeloCodigoExterno": None,
    }
    try:
        resp = requests.post(f"{BASE_URL}/ConsultarValorComTodosParametros", headers=HEADERS, json=payload)

        # Verifica se a resposta está OK
        if resp.status_code != 200:
            return {"erro": f"Erro HTTP: {resp.status_code}", "raw": resp.text}

        # Tenta interpretar como JSON
        return resp.json()

    except requests.exceptions.RequestException as e:
        return {"erro": f"Erro na requisição: {e}"}
    except Exception as e:
        return {"erro": f"Erro inesperado: {e}"}

# --- Interface Streamlit ---
st.set_page_config(page_title="Consulta FIPE", layout="centered")
st.title("Consulta FIPE 🚗")

# Tipo de veículo
tipo_veiculo = st.selectbox(
    "Tipo de Veículo",
    [("Carro", 1), ("Moto", 2), ("Caminhão", 3)],
    format_func=lambda x: x[0]
)
tipo = tipo_veiculo[1]

tabela = get_tabela_referencia()

# Marcas
marcas = get_marcas(tipo, tabela)
marca_dict = {m["Label"]: int(m["Value"]) for m in marcas}
marca_opcoes = [""] + list(marca_dict.keys())
marca_nome = st.selectbox("Marca", marca_opcoes, index=0)
if marca_nome == "":
    st.warning("Por favor, selecione uma Marca.")
    st.stop()
codigo_marca = marca_dict[marca_nome]

# Modelos (multiseleção)
modelos = get_modelos(tipo, tabela, codigo_marca)
modelo_dict = {m["Label"]: int(m["Value"]) for m in modelos}
modelo_opcoes = list(modelo_dict.keys())
modelos_selecionados = st.multiselect("Modelos", modelo_opcoes)

if not modelos_selecionados:
    st.warning("Por favor, selecione pelo menos um Modelo.")
    st.stop()

# Dicionário final com Label -> "ano-cod_comb"
ano_dict = {}

if len(modelos_selecionados) == 1:
    codigo_modelo = modelo_dict[modelos_selecionados[0]]
    anos = get_anos(tipo, tabela, codigo_marca, codigo_modelo)
    for a in anos:
        if a["Value"].startswith("32000"):
            label = "Zero Km (2025)"
        else:
            label = a["Label"]
        ano_dict[label] = a["Value"]

    ano_opcoes = list(ano_dict.keys())
    anos_selecionados = st.multiselect("Ano(s)/Combustível", ano_opcoes)

    if not anos_selecionados:
        st.warning("Por favor, selecione pelo menos um Ano/Combustível.")
        st.stop()

else:
    st.info("Múltiplos modelos selecionados: mostrando apenas anos comuns entre todos.")
    # Interseção de anos
    anos_por_modelo = []
    for nome_modelo in modelos_selecionados:
        codigo_modelo = modelo_dict[nome_modelo]
        anos_raw = get_anos(tipo, tabela, codigo_marca, codigo_modelo)
        anos_formatados = {}
        for a in anos_raw:
            if a["Value"].startswith("32000"):
                label = "Zero Km (2025)"
            else:
                label = a["Label"]
            anos_formatados[label] = a["Value"]
        anos_por_modelo.append(anos_formatados)

    # Interseção dos rótulos (labels visíveis)
    labels_comuns = set(anos_por_modelo[0].keys())
    for outros in anos_por_modelo[1:]:
        labels_comuns &= set(outros.keys())

    if not labels_comuns:
        st.error("❌ Nenhum ano/combustível em comum entre os modelos selecionados.")
        st.stop()

    # Preenche ano_dict apenas com os anos em comum
    for label in labels_comuns:
        ano_dict[label] = anos_por_modelo[0][label]  # todos têm o mesmo valor

    ano_opcoes = sorted(list(ano_dict.keys()))
    ano_unico = st.selectbox("Ano/Combustível", [""] + ano_opcoes)
    if ano_unico == "":
        st.warning("Por favor, selecione o Ano/Combustível.")
        st.stop()
    anos_selecionados = [ano_unico]

# Botão para buscar
if st.button("Consultar Valor"):
    st.subheader("🔍 Resultado(s) da Tabela FIPE")
    for modelo_nome in modelos_selecionados:
        codigo_modelo = modelo_dict[modelo_nome]
        for ano_label in anos_selecionados:
            ano_modelo, cod_comb = ano_dict[ano_label].split("-")
            resultado = get_valor(tipo, tabela, codigo_marca, codigo_modelo, ano_modelo, cod_comb)

            st.markdown("---")
            if "erro" in resultado:
                st.error(f"Erro ao consultar: {resultado['erro']}")
                if "raw" in resultado:
                    st.text(resultado["raw"])  # útil para debugging
                continue

            if "Valor" not in resultado:
                st.warning("⚠️ Nenhum valor retornado pela FIPE para este modelo/ano.")
                continue

            st.write(f"**Veículo:** {resultado['Marca']} {resultado['Modelo']}")
            st.write(f"**Ano/Combustível:** {resultado['AnoModelo']} / {resultado['Combustivel']}")
            st.write(f"**Preço FIPE:** {resultado['Valor']}")