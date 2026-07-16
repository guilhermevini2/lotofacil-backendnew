"""
ml_model.py - Treinamento e uso do modelo de Gradient Boosting para Lotofacil.

Arquitetura: HistGradientBoostingClassifier (sklearn) — equivalente funcional
ao XGBoost, nativo no scikit-learn, sem dependencias externas.

Para usar XGBoost no lugar (quando disponivel na maquina):
    Substitua o bloco _criar_modelo() por:
        import xgboost as xgb
        return xgb.XGBClassifier(
            n_estimators=400, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric='logloss',
            random_state=42
        )
"""

import json
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.calibration import CalibratedClassifierCV

from config import BASE_DIR, TOTAL_DEZENAS
from ml_features import extrair_features, NOMES_FEATURES, construir_dataset

MODEL_PATH    = BASE_DIR / "cache" / "ml_model.pkl"
META_PATH     = BASE_DIR / "cache" / "ml_meta.json"
MIN_HISTORICO = 40   # concursos minimos para comecar a treinar


# -- Fabrica do modelo --------------------------------------------------------

def _criar_modelo() -> HistGradientBoostingClassifier:
    """
    Cria instancia do modelo. Troque aqui por XGBClassifier se preferir.
    """
    return HistGradientBoostingClassifier(
        max_iter=400,            # equivalente a n_estimators
        max_depth=5,
        learning_rate=0.05,
        min_samples_leaf=20,
        l2_regularization=0.1,
        max_bins=255,
        early_stopping=True,
        n_iter_no_change=20,
        validation_fraction=0.1,
        random_state=42,
        verbose=0,
    )


# -- Treinamento --------------------------------------------------------------

def treinar(
    concursos: list[dict],
    forcar: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Treina o modelo com todo o historico disponivel.
    Se ja existe modelo salvo e nao ha novos concursos, reutiliza.

    Retorna dict com metricas de avaliacao.
    """
    # Verificar se retraining e necessario
    if not forcar and MODEL_PATH.exists() and META_PATH.exists():
        meta = json.loads(META_PATH.read_text())
        if meta.get("ultimo_concurso") == concursos[-1]["concurso"]:
            if verbose:
                print("  Modelo ML ja atualizado. Carregando cache...")
            return meta

    if verbose:
        print(f"  Construindo dataset ({len(concursos)} concursos)...")
    t0 = time.time()

    X, y, amostras_meta = construir_dataset(concursos, min_historico=MIN_HISTORICO)

    if verbose:
        print(f"  Dataset: {X.shape[0]:,} amostras x {X.shape[1]} features "
              f"| {y.sum():,} positivos ({y.mean()*100:.1f}%) "
              f"| {time.time()-t0:.1f}s")

    # Validacao walk-forward (respeitando ordem temporal)
    tscv = TimeSeriesSplit(n_splits=5)
    aucs, logloss_vals = [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
        m = _criar_modelo()
        m.fit(X[train_idx], y[train_idx])
        proba = m.predict_proba(X[val_idx])[:, 1]
        auc = roc_auc_score(y[val_idx], proba)
        ll  = log_loss(y[val_idx], proba)
        aucs.append(auc)
        logloss_vals.append(ll)
        if verbose:
            print(f"    Fold {fold}/5: AUC={auc:.4f}  LogLoss={ll:.4f}")

    # Treinar modelo final com todos os dados
    if verbose:
        print("  Treinando modelo final com todo o historico...")
    modelo_final = _criar_modelo()
    modelo_final.fit(X, y)

    # Salvar
    MODEL_PATH.parent.mkdir(exist_ok=True)
    pickle.dump(modelo_final, MODEL_PATH.open("wb"))

    meta_salva = {
        "ultimo_concurso": concursos[-1]["concurso"],
        "total_concursos": len(concursos),
        "n_amostras":      int(X.shape[0]),
        "n_features":      int(X.shape[1]),
        "n_positivos":     int(y.sum()),
        "auc_medio":       round(float(np.mean(aucs)), 4),
        "auc_std":         round(float(np.std(aucs)), 4),
        "logloss_medio":   round(float(np.mean(logloss_vals)), 4),
        "modelo":          "HistGradientBoostingClassifier (sklearn)",
        "xgboost_ready":   True,  # codigo pronto para trocar por XGBoost
    }
    META_PATH.write_text(json.dumps(meta_salva, ensure_ascii=False))

    if verbose:
        print(f"\n  Resultados da validacao walk-forward:")
        print(f"    AUC medio  : {meta_salva['auc_medio']:.4f} ± {meta_salva['auc_std']:.4f}")
        print(f"    LogLoss    : {meta_salva['logloss_medio']:.4f}")
        print(f"  Modelo salvo em: {MODEL_PATH.name}")

    return meta_salva


# -- Predicao -----------------------------------------------------------------

def carregar_modelo():
    """Carrega o modelo treinado do disco."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Modelo nao encontrado. Execute treinar() primeiro."
        )
    return pickle.load(MODEL_PATH.open("rb"))


def prever_probabilidades(
    historico: list[list[int]],
    modelo=None,
) -> dict[int, float]:
    """
    Para um historico de sorteios, retorna a probabilidade estimada
    de cada dezena (1-25) sair no PROXIMO concurso.

    Retorna: {dezena: probabilidade}
    """
    if modelo is None:
        modelo = carregar_modelo()

    X = np.array(
        [extrair_features(historico, d) for d in range(1, TOTAL_DEZENAS + 1)],
        dtype=np.float32,
    )
    probas = modelo.predict_proba(X)[:, 1]
    return {d: float(probas[d - 1]) for d in range(1, TOTAL_DEZENAS + 1)}


# -- Importancia de features --------------------------------------------------

def importancia_features(modelo=None) -> list[dict]:
    """
    Retorna lista de {feature, importancia} ordenada por importancia.
    Funciona com HistGradientBoosting e XGBoost.
    """
    if modelo is None:
        modelo = carregar_modelo()

    imp = None
    if hasattr(modelo, "feature_importances_"):
        imp = modelo.feature_importances_
    elif hasattr(modelo, "feature_importances"):
        imp = modelo.feature_importances

    if imp is None:
        return []

    resultado = [
        {"feature": nome, "importancia": round(float(val), 6)}
        for nome, val in zip(NOMES_FEATURES, imp)
    ]
    return sorted(resultado, key=lambda x: -x["importancia"])


# -- Resumo do modelo ---------------------------------------------------------

def resumo_modelo(meta: dict) -> str:
    linhas = [
        "=" * 60,
        "  MODELO ML — GRADIENT BOOSTING (XGBoost-compativel)",
        "=" * 60,
        f"  Algoritmo          : {meta.get('modelo', 'HistGradientBoosting')}",
        f"  Ultimo concurso    : {meta.get('ultimo_concurso')}",
        f"  Concursos usados   : {meta.get('total_concursos')}",
        f"  Amostras           : {meta.get('n_amostras'):,}",
        f"  Features           : {meta.get('n_features')}",
        "",
        "  Validacao walk-forward (TimeSeriesSplit, 5 folds):",
        f"  AUC medio          : {meta.get('auc_medio'):.4f} +/- {meta.get('auc_std'):.4f}",
        f"  LogLoss            : {meta.get('logloss_medio'):.4f}",
        "",
        "  Referencia (baseline aleatorio): AUC=0.5000",
        f"  Ganho sobre baseline: +{(meta.get('auc_medio',0.5)-0.5)*100:.2f} pontos",
        "=" * 60,
    ]
    return "\n".join(linhas)
