"""Plongement de phrases : un texte devient un vecteur, et deux textes de même
sens, dans n'importe laquelle des trois langues, tombent l'un près de l'autre.

Modèle : multilingual-e5-small (licence MIT), export ONNX quantifié en int8.
Il tourne avec onnxruntime et sentencepiece, sans PyTorch, pour tenir dans
les 512 Mo de l'offre gratuite de Render : le découpeur `tokenizer.json` du
même dépôt prendrait à lui seul 250 Mo, le modèle SentencePiece d'origine 40. Les fichiers sont téléchargés à une
révision figée et vérifiés par empreinte : un fichier modifié en amont est
refusé au lieu d'être chargé.

Téléchargement, au build : python -m app.plongement
"""
import hashlib
import logging
import os
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

import numpy as np

log = logging.getLogger("hanabi.plongement")

DEPOT = "Xenova/multilingual-e5-small"
REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
FICHIERS = {
    "onnx/model_quantized.onnx": "f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193",
    "sentencepiece.bpe.model": "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
}
DOSSIER = Path(
    os.environ.get("HANABI_MODELES", Path(__file__).resolve().parents[1] / "var" / "modeles")
) / "multilingual-e5-small" / REVISION[:12]

# Les requêtes et les fiches dépassent rarement quelques dizaines de mots
LONGUEUR_MAX = 128
DIMENSION = 384


def _empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def present() -> bool:
    return all((DOSSIER / nom).is_file() for nom in FICHIERS)


def telecharger() -> Path:
    """Télécharge ce qui manque, vérifie chaque empreinte, puis range le fichier."""
    for nom, attendue in FICHIERS.items():
        cible = DOSSIER / nom
        if cible.is_file():
            continue
        cible.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{DEPOT}/resolve/{REVISION}/{nom}"
        log.info("téléchargement de %s", url)
        with tempfile.NamedTemporaryFile(dir=cible.parent, delete=False) as tmp:
            with urllib.request.urlopen(url, timeout=60) as reponse:
                while bloc := reponse.read(1 << 20):
                    tmp.write(bloc)
        obtenue = _empreinte(Path(tmp.name))
        if obtenue != attendue:
            os.unlink(tmp.name)
            raise RuntimeError(f"{nom} : empreinte {obtenue}, {attendue} attendue")
        os.replace(tmp.name, cible)
    return DOSSIER


class Encodeur:
    """Texte vers vecteur unitaire de 384 dimensions."""

    def __init__(self, dossier: Path | None = None):
        import onnxruntime as ort

        dossier = dossier or DOSSIER
        import sentencepiece as spm

        self.sp = spm.SentencePieceProcessor(model_file=str(dossier / "sentencepiece.bpe.model"))
        options = ort.SessionOptions()
        # Des requêtes d'une seule phrase : la réserve mémoire ne ferait rien gagner
        options.enable_cpu_mem_arena = False
        # Un seul cœur : l'hébergeur n'en donne qu'une fraction, et plusieurs
        # fils se disputeraient ce peu de calcul au lieu de l'accélérer
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(dossier / "onnx" / "model_quantized.onnx"),
            options,
            providers=["CPUExecutionProvider"],
        )
        self.entrees = {e.name for e in self.session.get_inputs()}

    def _jetons(self, texte: str) -> list[int]:
        # Numérotation de XLM-R : <s>=0, <pad>=1, </s>=2, <unk>=3, puis les
        # pièces SentencePiece décalées de un
        pieces = [3 if i == 0 else i + 1 for i in self.sp.encode(texte.strip())]
        return [0, *pieces[: LONGUEUR_MAX - 2], 2]

    def encoder(self, textes: list[str]) -> np.ndarray:
        """Un texte à la fois. Le modèle quantifié calcule l'échelle de ses
        activations sur tout le lot : encodé avec d'autres, un même texte
        bougeait de 0,002, assez pour changer une décision de la recherche selon
        les objets voisins dans le catalogue."""
        sortie = np.empty((len(textes), DIMENSION), dtype=np.float32)
        for i, texte in enumerate(textes):
            sortie[i] = self._lot([self._jetons(texte)])[0]
        return sortie

    def _lot(self, jetons: list[list[int]]) -> np.ndarray:
        largeur = max(map(len, jetons))
        ids = np.ones((len(jetons), largeur), dtype=np.int64)
        masque = np.zeros_like(ids)
        for i, j in enumerate(jetons):
            ids[i, : len(j)] = j
            masque[i, : len(j)] = 1
        flux = {"input_ids": ids, "attention_mask": masque}
        if "token_type_ids" in self.entrees:
            flux["token_type_ids"] = np.zeros_like(ids)
        etats = self.session.run(None, flux)[0]
        # Moyenne des jetons réels, comme à l'entraînement d'e5
        poids = masque[..., None].astype(np.float32)
        moyenne = (etats * poids).sum(axis=1) / np.clip(poids.sum(axis=1), 1e-9, None)
        return moyenne / np.linalg.norm(moyenne, axis=1, keepdims=True)

    def requetes(self, textes: list[str]) -> np.ndarray:
        return self.encoder([f"query: {t}" for t in textes])

    def passages(self, textes: list[str]) -> np.ndarray:
        return self.encoder([f"passage: {t}" for t in textes])


_encodeur: Encodeur | None = None
_chargement = threading.Lock()
_echec = False


def encodeur(attendre: bool = False) -> Encodeur | None:
    """L'encodeur s'il est prêt, sinon None : la recherche retombe sur le texte.

    Sans `attendre`, le chargement part en arrière-plan : un démarrage à froid
    ne fait pas patienter la première requête.
    """
    global _encodeur
    if _encodeur is not None or _echec or not present():
        return _encodeur
    if attendre:
        _charger()
    elif not _chargement.locked():
        threading.Thread(target=_charger, name="plongement", daemon=True).start()
    return _encodeur


def _charger() -> None:
    global _encodeur, _echec
    with _chargement:
        if _encodeur is not None or _echec:
            return
        try:
            _encodeur = Encodeur()
            log.info("modèle de plongement chargé")
        except Exception:
            # Une bibliothèque absente ou un fichier abîmé coupe la recherche
            # par le sens, jamais la boutique
            _echec = True
            log.exception("modèle de plongement indisponible, recherche par le texte seule")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print(telecharger())
