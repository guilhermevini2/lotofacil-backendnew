"""
config.py — Configuracoes centrais do Lotofacil Pro v2
"""

from pathlib import Path

# -- Diretorios ----------------------------------------------------------------
BASE_DIR      = Path(__file__).parent
CACHE_DIR     = BASE_DIR / "cache"
RELATORIO_DIR = BASE_DIR / "relatorios"
JOGOS_DIR     = BASE_DIR / "jogos"

for d in (CACHE_DIR, RELATORIO_DIR, JOGOS_DIR):
    d.mkdir(exist_ok=True)

# -- API ----------------------------------------------------------------------
API_BASE        = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
API_TIMEOUT     = 15
API_RETRY_MAX   = 4
API_RETRY_DELAY = 1.5
API_SLEEP       = 0.35

# -- Concurso -----------------------------------------------------------------
CONCURSO_INICIO_2026 = 3577
TOTAL_DEZENAS        = 25
DEZENAS_SORTEADAS    = 15
DEZENAS_FECHAMENTO   = 18

# -- Analise estatistica ------------------------------------------------------
JANELAS_TENDENCIA = [10, 20, 30, 50, 100]

# -- Pool adaptativo ----------------------------------------------------------
# Tamanhos de pool a testar automaticamente
POOL_SIZES = [18, 19, 20, 21]

# -- Decaimento exponencial ---------------------------------------------------
# Fator de decaimento: concursos mais recentes pesam mais no ranking
# 1.0 = sem decaimento (todos iguais), 0.97 = decaimento suave
DECAY_FACTOR = 0.97

# -- Filtros de consistencia nos jogos ----------------------------------------
FILTRO_SOMA_MIN      = 170
FILTRO_SOMA_MAX      = 230
FILTRO_MAX_CONSEC    = 5     # max de dezenas consecutivas por jogo
FILTRO_PAR_MIN       = 5     # minimo de pares por jogo
FILTRO_PAR_MAX       = 10    # maximo de pares por jogo
FILTRO_LINHA_MIN     = 1     # minimo de dezenas por linha do volante
FILTRO_LINHA_MAX     = 5     # maximo de dezenas por linha do volante

# -- Pares e trios quentes ----------------------------------------------------
TOP_PARES  = 30   # quantos pares quentes considerar no score
TOP_TRIOS  = 20   # quantos trios quentes considerar no score

# -- Alerta de acumulacao -----------------------------------------------------
ACUMULACAO_MINIMA = 1_000_000.0   # R$ — alerta se premio acumulado >= este valor

# -- Fechamento ---------------------------------------------------------------
INDICES_FECHAMENTO = [
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 16, 17, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 13, 14, 15, 16, 17, 18],
    [1,  2,  3,  4,  5,  6, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [1,  2,  3,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 13, 14, 16, 17],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 12, 13, 15, 16, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 11, 12, 14, 15, 17, 18],
    [1,  2,  4,  5,  7,  8, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [1,  3,  4,  6,  7,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [2,  3,  5,  6,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 13, 15, 17, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 14, 15, 16, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 12, 13, 14, 17, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 12, 14, 15, 16, 17],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 11, 12, 13, 14, 16, 18],
    [1,  2,  3,  4,  5,  6,  7,  8,  9, 11, 12, 13, 15, 16, 17],
    [1,  2,  4,  6,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [1,  2,  5,  6,  7,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [1,  3,  4,  5,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [1,  3,  5,  6,  7,  8, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [2,  3,  4,  5,  7,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    [2,  3,  4,  6,  7,  8, 10, 11, 12, 13, 14, 15, 16, 17, 18],
]

# -- Conjuntos matematicos ----------------------------------------------------
PRIMOS     = {2, 3, 5, 7, 11, 13, 17, 19, 23}
FIBONACCI  = {1, 2, 3, 5, 8, 13, 21}
MULTIPLOS3 = {3, 6, 9, 12, 15, 18, 21, 24}

GRID = {d: ((d-1)//5 + 1, (d-1)%5 + 1) for d in range(1, 26)}
MOLDURA = {d for d, (r, c) in GRID.items() if r in (1,5) or c in (1,5)}
CENTRO  = set(range(1, 26)) - MOLDURA

# -- Exportacao ---------------------------------------------------------------
EXCEL_FONT   = "Arial"
EXCEL_HEADER = "1F4E79"
EXCEL_ALT    = "D9E1F2"
EXCEL_GREEN  = "E2EFDA"
EXCEL_YELLOW = "FFF2CC"
EXCEL_ORANGE = "FCE4D6"
