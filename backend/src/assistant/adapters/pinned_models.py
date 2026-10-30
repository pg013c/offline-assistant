"""Every model the app loads, pinned by commit and file hash (ADR 0004, 0016, 0017, 0019).

`make models` fetches exactly these files and checks them; the API checks them again at
startup, so two machines with the same `uv.lock` get the same chunks and the same vectors.
"""

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


class ModelsNotReady(Exception):
    """A model or tool the app needs is missing; the message says how to install it."""


@dataclass(frozen=True)
class PinnedModel:
    repository: str
    revision: str
    # Where the files live, relative to ASSISTANT_MODELS_DIR.
    directory: str
    # Path under `directory` -> SHA-256.
    files: Mapping[str, str]


# Docling looks for its models under `docling/<organisation>--<name>`.
DOCLING_LAYOUT = PinnedModel(
    repository="docling-project/docling-layout-heron",
    revision="8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
    directory="docling/docling-project--docling-layout-heron",
    files={
        "config.json": "fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d",
        "model.safetensors": "00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c",
        "preprocessor_config.json": (
            "cd38cd59999e7a95d68e487fbe5132df3d4e5c32a0836add57e6126ba0c4eaf1"
        ),
    },
)
# TableFormer v2.3.0.
DOCLING_TABLES = PinnedModel(
    repository="docling-project/docling-models",
    revision="fc0f2d45e2218ea24bce5045f58a389aed16dc23",
    directory="docling/docling-project--docling-models",
    files={
        "config.json": "9c34024dc28ff47b75818f415e769809798c29bf9bde6f2ccc63a4acb62396d9",
        "model_artifacts/tableformer/accurate/tableformer_accurate.safetensors": (
            "2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9"
        ),
        "model_artifacts/tableformer/accurate/tm_config.json": (
            "984e122ceb8ccf84d84c9d2882f6f2302a44b4f1e577babd6289892c36f3cffd"
        ),
        "model_artifacts/tableformer/fast/tableformer_fast.safetensors": (
            "3119563aab5a7c96fda4d621119b63fd8806272b86c30936d15507616422f718"
        ),
        "model_artifacts/tableformer/fast/tm_config.json": (
            "dca6762508dddfae6d57d6cb4ef822c6000119dff0f3b6489db7413118c2622a"
        ),
    },
)
# The dense model and its tokenizer; the ONNX copy, ColBERT and sparse heads are not used.
BGE_M3 = PinnedModel(
    repository="BAAI/bge-m3",
    revision="5617a9f61b028005a4858fdac845db406aefb181",
    directory="embeddings/BAAI--bge-m3",
    files={
        "1_Pooling/config.json": "e54c164a07274f2eb45bb724f54a79d1efcc90c41573887cd9a29aeee0597352",
        "config.json": "26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa",
        "config_sentence_transformers.json": (
            "1eef72430e7194a1e59680e635aed81ffa083f05668dbc5bb1c56c04c0999c38"
        ),
        "modules.json": "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf",
        "pytorch_model.bin": "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38",
        "sentence_bert_config.json": (
            "eb9b44b13c0f52a3b3685c3b1cbdea1ba8b04bea123b98f61610048940776eb1"
        ),
        "sentencepiece.bpe.model": (
            "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865"
        ),
        "special_tokens_map.json": (
            "8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835"
        ),
        "tokenizer.json": "21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08",
        "tokenizer_config.json": (
            "a62b2b6784f990259fddef5f16388693a8043be4f69179e6a5257eeb3f9abac4"
        ),
    },
)

DOCLING_MODELS = (DOCLING_LAYOUT, DOCLING_TABLES)
# The cross-encoder that reorders search candidates (ADR 0019).
BGE_RERANKER = PinnedModel(
    repository="BAAI/bge-reranker-v2-m3",
    revision="953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
    directory="rerankers/BAAI--bge-reranker-v2-m3",
    files={
        "config.json": "13dcd6c31d9fec9d1d8e158702072f62d7fa7d312a64b9fe057bec9a08cfe41a",
        "model.safetensors": "d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286",
        "sentencepiece.bpe.model": (
            "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865"
        ),
        "special_tokens_map.json": (
            "8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835"
        ),
        "tokenizer.json": "69564b696052886ed0ac63fa393e928384e0f8caada38c1f4864a9bfbf379c15",
        "tokenizer_config.json": (
            "7e4c1cc848840aeccdd763458c18dd525eb0f795c992e00ebe9c28554e7db2d4"
        ),
    },
)
PINNED_MODELS = (*DOCLING_MODELS, BGE_M3, BGE_RERANKER)


def verify_models(models_dir: Path, models: Iterable[PinnedModel]) -> None:
    """Raise `ModelsNotReady` unless every file of every model exists with its hash."""
    problems: list[str] = []
    for model in models:
        folder = models_dir / model.directory
        for path, digest in sorted(model.files.items()):
            file = folder / path
            if not file.is_file():
                problems.append(f"{model.repository}: {path} is missing")
            elif _sha256(file) != digest:
                problems.append(f"{model.repository}: {path} differs from the pinned version")
    if problems:
        raise ModelsNotReady(
            f"Models in {models_dir} are not ready: {'; '.join(problems)}. "
            "Run `make models` (the only step that needs the network)."
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# The local LLM, served by llama-server rather than loaded by the API (ADR 0021); fetched by
# `make llm-models`, not `make models`, so CI and the test model need no 5 GB download.
QWEN3_8B = PinnedModel(
    repository="Qwen/Qwen3-8B-GGUF",
    revision="7c41481f57cb95916b40956ab2f0b139b296d974",
    directory="llm/Qwen--Qwen3-8B-GGUF",
    files={
        "Qwen3-8B-Q4_K_M.gguf": "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
    },
)
LLM_MODELS: tuple[PinnedModel, ...] = (QWEN3_8B,)
