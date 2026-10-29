"""One model loads at a time, whichever adapter loads it.

Loading through transformers patches torch globally for a moment, so a model loading on
another thread at the same time can come out as empty "meta" tensors. Every adapter that
loads a model holds this lock while it does (F-05).
"""

import threading

MODEL_LOADING = threading.Lock()
