import importlib.util
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np

from .base import ModelUnavailable

MODEL_ID = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
MODEL_REVISION = os.getenv('EMBEDDING_REVISION', 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42')


class Encoder:
    def __init__(self):
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='semantic-model')
        self.model = None
        self.state = 'not_prepared'
        self.revision = None
        self.error = None

    def status(self):
        # Keep status non-blocking while another thread downloads/encodes.
        installed = importlib.util.find_spec('sentence_transformers') is not None
        return {'state': self.state if installed else 'not_installed', 'model': MODEL_ID, 'requested_revision': MODEL_REVISION, 'resolved_revision': self.revision, 'device': 'cpu', 'error': self.error}

    def prepare(self):
        with self.lock:
            if self.state in ('loading', 'ready'):
                return self.status()
            if importlib.util.find_spec('sentence_transformers') is None:
                raise ModelUnavailable('Installer les dépendances sémantiques puis reconstruire l’API')
            self.state, self.error = 'loading', None
            self.pool.submit(self._load)
            return self.status()

    def _load(self):
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            torch.set_num_threads(max(1, min(8, int(os.getenv('EMBEDDING_THREADS', '2')))))
            options = dict(device='cpu', revision=MODEL_REVISION, trust_remote_code=False)
            try:
                model = SentenceTransformer(MODEL_ID, local_files_only=True, **options)
            except (OSError, ValueError):
                model = SentenceTransformer(MODEL_ID, **options)
            model.eval()
            revision = getattr(model._first_module().auto_model.config, '_commit_hash', None)
            with self.lock:
                self.model, self.revision, self.state = model, revision or MODEL_REVISION, 'ready'
        except Exception as error:
            import logging
            logging.getLogger(__name__).error('Préparation du modèle impossible : %s', type(error).__name__)
            self.state, self.error = 'error', 'Préparation impossible : vérifier les dépendances, le réseau et le cache de modèles, puis réessayer.'

    def encode(self, texts):
        with self.lock:
            if self.model is None:
                raise ModelUnavailable('Le modèle sémantique doit être préparé dans Administration → Algorithmes')
            return np.asarray(self.model.encode(list(texts), batch_size=16, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False), dtype=np.float32)


encoder = Encoder()


@lru_cache(maxsize=2)
def semantic_index(documents):
    return encoder.encode(documents)


def semantic_features(context):
    matrix = semantic_index(context.documents)
    profile = encoder.encode([context.profile])[0]
    # Negative cosine is not a positive relevance/redundancy signal here.
    relevance = np.clip(matrix @ profile, 0, 1)
    def similarities(candidates, selected):
        return np.clip(matrix[candidates] @ matrix[selected].T, 0, 1)
    return relevance, similarities
