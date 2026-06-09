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
    "Identifique os dias do mês em que cada FII historicamente "
    "negociou mais próximo da mínima mensal."
)

# ==========================================================
# FUNÇÕES
# ==========================================================

@st.cache_data(ttl=3600)
def baixar_dados(ticker):

    try:

        df = yf.download(
            ticker,
            auto_adjust=True,
            progress=False,
            multi_level_index=False
        )

        if df.empty:
            return None

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

    estatistica["Atratividade"] = (
        1 - estatistica["PosicaoMedia"]
    ) * 100

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
        "top3": top3,
        "heatmap": estatistica
    }


def calcular_score_atual(df):

    if len(df) < 30:
        return np.nan

    atual = float(df["Close"].iloc[-1])

    minimo = float(df["Close"].min())
    maximo = float(df["Close"].max())

    if np.isclose(maximo, minimo):
        return np.nan

    score = (
        (maximo - atual)
        / (maximo - minimo)
    ) * 100

    score = max(0, min(score, 100))

    return round(score, 1)


def criar_heatmap(heatmap_df):

    dias = list(range(1, 32))

    valores = []

    for dia in dias:

        linha = heatmap_df[
            heatmap_df["Day"] == dia
        ]

        if len(linha):

            valores.append(
                float(
                    linha["Atratividade"].iloc[0]
                )
            )

        else:

            valores.append(np.nan)

    fig = go.Figure(
        data=go.Heatmap(
            z=[valores],
            x=dias,
            y=[""],
            hoverongaps=False
        )
    )

    fig.update_layout(
        height=220,
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20
        )
    )

    return fig


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

            score = calcular_score_atual(df)

            ranking.append({
                "FII": fii,
                "Melhor Dia": analise["melhor_dia"],
                "Top 1": analise["top3"][0] if len(analise["top3"]) > 0 else "",
                "Top 2": analise["top3"][1] if len(analise["top3"]) > 1 else "",
                "Top 3": analise["top3"][2] if len(analise["top3"]) > 2 else "",
                "Meses": analise["meses"],
                "Confiabilidade": analise["confiabilidade"],
                "Score Atual": score
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
                "Score",
                score
            )

            st.markdown(
                "### 🏆 Top 3 Dias"
            )

            top3_df = pd.DataFrame({
                "Posição": [
                    "1º",
                    "2º",
                    "3º"
                ],
                "Dia": analise["top3"]
            })

            st.dataframe(
                top3_df,
                use_container_width=True
            )

            st.markdown(
                "### 🔥 Heatmap"
            )

            st.plotly_chart(
                criar_heatmap(
                    analise["heatmap"]
                ),
                use_container_width=True
            )

            st.markdown(
                "### 📈 Histórico"
            )

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
                height=450
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    if len(ranking):

        st.divider()

        st.header(
            "🏆 Ranking Geral"
        )

        ranking_df = pd.DataFrame(
            ranking
        )

        ranking_df = ranking_df.sort_values(
            "Score Atual",
            ascending=False
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
