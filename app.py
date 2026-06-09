import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime

# ==========================================================
# CONFIG
# ==========================================================

st.set_page_config(
    page_title="FII Best Buy Day Analyzer",
    layout="wide"
)

st.title("🏢 FII Best Buy Day Analyzer")

st.caption(
    "Identifique quais dias do mês historicamente negociaram "
    "mais próximos das mínimas mensais."
)

# ==========================================================
# FUNÇÕES
# ==========================================================

@st.cache_data(ttl=3600)
def baixar_dados(ticker):

    try:

        df = yf.download(
            ticker,
            period="max",
            auto_adjust=True,
            progress=False
        )

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        if "Date" not in df.columns:
            return None

        if "Close" not in df.columns:
            return None

        df["Date"] = pd.to_datetime(df["Date"])

        df["Close"] = pd.to_numeric(
            df["Close"],
            errors="coerce"
        )

        df = df.dropna(subset=["Close"])

        df["Day"] = df["Date"].dt.day
        df["Month"] = df["Date"].dt.to_period("M")

        return df

    except Exception as e:

        st.error(f"Erro ao baixar {ticker}: {e}")

        return None


def classificar_confiabilidade(meses):

    if meses >= 60:
        return "Muito Alta"

    if meses >= 36:
        return "Alta"

    if meses >= 24:
        return "Média"

    if meses >= 12:
        return "Baixa"

    return "Muito Baixa"


def analisar_fii(df):

    registros = []

    meses = int(df["Month"].nunique())

    for _, grupo in df.groupby("Month"):

        grupo = grupo.copy()

        minimo = float(grupo["Close"].min())
        maximo = float(grupo["Close"].max())

        if np.isclose(maximo, minimo):
            continue

        grupo["Posicao"] = (
            (grupo["Close"] - minimo)
            / (maximo - minimo)
        )

        registros.append(
            grupo[["Day", "Posicao"]]
        )

    if len(registros) == 0:
        return None

    base = pd.concat(
        registros,
        ignore_index=True
    )

    estatistica = (
        base.groupby("Day")
        .agg(
            PosicaoMedia=("Posicao", "mean"),
            Observacoes=("Posicao", "count")
        )
        .reset_index()
    )

    estatistica = estatistica.sort_values(
        "PosicaoMedia"
    )

    melhor_dia = int(
        estatistica.iloc[0]["Day"]
    )

    top3 = (
        estatistica.head(3)["Day"]
        .astype(int)
        .tolist()
    )

    return {
        "meses": meses,
        "confiabilidade": classificar_confiabilidade(meses),
        "melhor_dia": melhor_dia,
        "top3": top3
    }


def calcular_score_sazonal(df):

    try:

        hoje = datetime.now().day

        registros = []

        for _, grupo in df.groupby("Month"):

            grupo = grupo.copy()

            minimo = float(grupo["Close"].min())
            maximo = float(grupo["Close"].max())

            if np.isclose(maximo, minimo):
                continue

            grupo["Posicao"] = (
                (grupo["Close"] - minimo)
                / (maximo - minimo)
            )

            registros.append(
                grupo[["Date", "Day", "Posicao"]]
            )

        if len(registros) == 0:
            return np.nan

        base = pd.concat(
            registros,
            ignore_index=True
        )

        historico_mesmo_dia = base[
            base["Day"] == hoje
        ]["Posicao"]

        if len(historico_mesmo_dia) < 5:
            return np.nan

        ultimo_mes = df["Month"].max()

        grupo_atual = df[
            df["Month"] == ultimo_mes
        ].copy()

        minimo_atual = float(
            grupo_atual["Close"].min()
        )

        maximo_atual = float(
            grupo_atual["Close"].max()
        )

        if np.isclose(
            minimo_atual,
            maximo_atual
        ):
            return np.nan

        preco_atual = float(
            df["Close"].iloc[-1]
        )

        posicao_atual = (
            (preco_atual - minimo_atual)
            / (maximo_atual - minimo_atual)
        )

        score = (
            historico_mesmo_dia >
            posicao_atual
        ).mean() * 100

        return round(score, 1)

    except Exception:

        return np.nan


def gerar_excel(df):

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="Ranking",
            index=False
        )

    output.seek(0)

    return output


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.header("⚙️ Configurações")

fiis_padrao = [
    "GARE11",
    "GGRC11",
    "HGLG11",
    "XPLG11",
    "MXRF11"
]

texto_fiis = st.sidebar.text_area(
    "FIIs (um por linha)",
    value="\n".join(fiis_padrao),
    height=220
)

fiis = []

for linha in texto_fiis.splitlines():

    ticker = linha.strip().upper()

    if ticker:
        fiis.append(ticker)

analisar = st.sidebar.button(
    "🚀 Analisar",
    use_container_width=True
)

# ==========================================================
# EXECUÇÃO
# ==========================================================

if analisar:

    ranking = []

    if len(fiis) == 0:

        st.warning(
            "Informe pelo menos um FII."
        )

        st.stop()

    abas = st.tabs(fiis)

    for idx, fii in enumerate(fiis):

        with abas[idx]:

            ticker = f"{fii}.SA"

            st.subheader(f"📊 {fii}")

            with st.spinner(
                f"Carregando {fii}..."
            ):

                df = baixar_dados(
                    ticker
                )

            if df is None:

                st.error(
                    "Não foi possível obter dados."
                )

                continue

            analise = analisar_fii(df)

            if analise is None:

                st.warning(
                    "Histórico insuficiente."
                )

                continue

            score = calcular_score_sazonal(df)

            data_inicio = (
                df["Date"]
                .min()
                .strftime("%d/%m/%Y")
            )

            data_final = (
                df["Date"]
                .max()
                .strftime("%d/%m/%Y")
            )

            ranking.append({
                "FII": fii,
                "Melhor Dia": analise["melhor_dia"],
                "Top 1": analise["top3"][0],
                "Top 2": analise["top3"][1],
                "Top 3": analise["top3"][2],
                "Meses": analise["meses"],
                "Confiabilidade": analise["confiabilidade"],
                "Score": score
            })

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Melhor Dia",
                analise["melhor_dia"]
            )

            c2.metric(
                "Meses",
                analise["meses"]
            )

            c3.metric(
                "Confiabilidade",
                analise["confiabilidade"]
            )

            c4.metric(
                "Score Sazonal",
                "N/A" if pd.isna(score) else score
            )

            st.markdown(
                f"""
                **Início do histórico:** {data_inicio}

                **Fim do histórico:** {data_final}
                """
            )

            st.markdown("### 🏆 Top 3 Dias")

            top3_df = pd.DataFrame({
                "Posição": ["1º", "2º", "3º"],
                "Dia": analise["top3"]
            })

            st.dataframe(
                top3_df,
                use_container_width=True
            )

            st.markdown("### 📈 Histórico")

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df["Close"],
                    mode="lines",
                    name=fii
                )
            )

            fig.update_layout(
                height=450,
                showlegend=False
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    if len(ranking):

        st.divider()

        st.header("🏆 Ranking Geral")

        ranking_df = pd.DataFrame(
            ranking
        )

        ranking_df = ranking_df.sort_values(
            "Score",
            ascending=False,
            na_position="last"
        )

        st.dataframe(
            ranking_df,
            use_container_width=True
        )

        excel = gerar_excel(
            ranking_df
        )

        st.download_button(
            label="📥 Exportar Excel",
            data=excel,
            file_name="ranking_fiis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:

    st.info(
        "Clique em 'Analisar' para iniciar."
    )
