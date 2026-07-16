# Lotofacil Pro v2

Sistema de analise estatistica e fechamento reduzido 18-15-14 para a Lotofacil.

## Instalacao (Windows)

1. Extraia o ZIP em qualquer pasta (ex: C:\LotofacilPro\)
2. Duplo clique em **instalar.bat** — instala Python e todas as dependencias
3. Duplo clique em **rodar.bat** — menu interativo (terminal)
   ou **abrir_app.bat** — app web instalavel no celular

## App Web (instalavel no celular)

O Lotofacil Pro tem uma interface web moderna que pode ser instalada
como app no seu celular (Android ou iPhone), sem precisar de loja de
aplicativos.

**Como usar:**

1. No PC, duplo clique em **abrir_app.bat** (ou opcao [8] no rodar.bat)
2. O terminal vai mostrar um endereco tipo `http://192.168.x.x:5000`
3. No celular, conecte na MESMA rede Wi-Fi do PC
4. Abra esse endereco no navegador do celular (Chrome ou Safari)
5. Toque no menu do navegador e escolha **"Adicionar a tela inicial"**
   (Android) ou **"Adicionar a Tela de Inicio"** (iPhone)
6. Pronto — o app aparece com icone proprio, tela cheia, sem barra
   de navegador

**Importante:** o PC precisa estar ligado e com o `abrir_app.bat`
rodando enquanto voce usa o app no celular. Os dados ficam guardados
no PC (cache local).

## Instalacao (Linux / Mac)

    pip install -r requirements.txt
    python main.py

## Uso avancado (linha de comando)

    python main.py                  # Analise completa
    python main.py --limpar-cache   # Re-baixa todos os concursos
    python main.py --sem-graficos   # Mais rapido, sem matplotlib
    python main.py --sem-excel      # Sem exportacao Excel
    python main.py --pool 20        # Usa pool de 20 dezenas

## Estrutura

    LotofacilPro/
    ├── main.py            Orquestrador principal
    ├── config.py          Configuracoes e parametros
    ├── api.py             Download com retry e cache local
    ├── statistics.py      14 analises estatisticas
    ├── ranking.py         Score com decaimento exponencial + pares/trios
    ├── fechamento.py      Geracao dos jogos + filtros de consistencia
    ├── filtros.py         Interface dos filtros
    ├── validator.py       Validacao matematica (816 combinacoes)
    ├── simulator.py       Backtest fixo e dinamico
    ├── pool_adaptativo.py Comparativo de pools 18/19/20/21
    ├── acumulacao.py      Alerta de concurso acumulado
    ├── exports.py         Excel (6 abas), CSV, TXT, PDF
    ├── graphs.py          9 graficos PNG
    ├── utils.py           Utilitarios e compatibilidade Windows
    ├── cache/             JSONs por concurso
    ├── relatorios/        Relatorios gerados
    └── jogos/             CSVs dos jogos

## Novidades v2

- Decaimento exponencial no ranking (concursos recentes pesam mais)
- Analise de pares e trios quentes
- Pool adaptativo comparando 18, 19, 20 e 21 dezenas
- Filtros de consistencia historica nos jogos
- Backtest dinamico (sem vies de dados futuros)
- Alerta de concurso acumulado
- 9 graficos PNG (antes eram 6)
- Excel com 6 abas (antes eram 5)
- 4 CSVs (antes eram 3)

## Garantia matematica

O fechamento 18-15-14 garante >=14 pontos em pelo menos um dos 24 jogos
SE E SOMENTE SE todos os 15 numeros sorteados estiverem dentro das 18 dezenas.
Validado sobre todas as C(18,15) = 816 combinacoes possiveis.

## AVISO

Este sistema e descritivo — analisa padroes historicos. NAO e preditivo.
A Lotofacil e um jogo de probabilidade. A Caixa retém ~35% da arrecadacao.
