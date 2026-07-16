"""
utils.py — Utilitários gerais do Lotofácil Pro.
"""

import sys
import os
from datetime import datetime
from config import CACHE_DIR


def _win_safe(texto: str) -> str:
    """Remove emojis/caracteres que o terminal Windows (CP850) não suporta."""
    if sys.platform == "win32":
        return texto.encode("cp850", errors="replace").decode("cp850")
    return texto


def configurar_terminal():
    """
    No Windows, força UTF-8 no stdout/stderr para exibir acentos corretamente.
    Requer Python 3.7+ e Windows 10 build 1903+.
    """
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            os.system("chcp 65001 >nul 2>&1")
        except Exception:
            pass


def limpar_cache() -> int:
    """Remove todos os arquivos de cache. Retorna quantidade removida."""
    arquivos = list(CACHE_DIR.glob("*.json"))
    for f in arquivos:
        f.unlink()
    return len(arquivos)


def concursos_em_cache() -> list[int]:
    """Retorna lista ordenada dos numeros de concursos ja em cache."""
    return sorted(
        int(f.stem) for f in CACHE_DIR.glob("*.json") if f.stem.isdigit()
    )


def progresso(atual: int, total: int, largura: int = 30) -> str:
    """Barra de progresso ASCII pura (compativel com todos os terminais)."""
    pct = atual / total if total else 0
    cheios = int(largura * pct)
    barra = "#" * cheios + "-" * (largura - cheios)
    return f"[{barra}] {pct*100:.1f}%  ({atual}/{total})"


def formatar_dezenas(dezenas: list[int]) -> str:
    """Formata lista de dezenas como string legivel."""
    return "  ".join(f"{d:02d}" for d in sorted(dezenas))


def timestamp_nome(prefixo: str, sufixo: str) -> str:
    """Gera nome de arquivo com timestamp."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefixo}_{ts}{sufixo}"


def verificar_dependencias() -> dict[str, bool]:
    """Verifica quais dependencias opcionais estao instaladas."""
    deps = {}
    for pkg in ["requests", "openpyxl", "matplotlib", "reportlab"]:
        try:
            __import__(pkg)
            deps[pkg] = True
        except ImportError:
            deps[pkg] = False
    return deps


def banner() -> str:
    return """
+----------------------------------------------------------+
|         LOTOFACIL PRO - Analise Estatistica              |
|         Fechamento Reduzido 18-15-14  -  24 Jogos        |
+----------------------------------------------------------+
"""
