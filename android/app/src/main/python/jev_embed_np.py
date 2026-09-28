r"""JEV ON A PHONE -- a BERT embedder in numpy alone.

WHY THIS EXISTS. Jev's instant answers need exactly one neural operation: embed
the question, then compare it against a precomputed index by arithmetic. On the
desktop that embedding comes from a llama.cpp server. A phone has no such
server -- the fork is a CUDA build, there is no ARM equivalent, and Chaquopy
ships no llama.cpp.

But Chaquopy DOES ship numpy (1.26.2, cp312, arm64-v8a), and bge-small is a
12-layer BERT: embeddings, twelve blocks of attention and a feed-forward, layer
norms, and a CLS vector at the end. That is a few matrix multiplies. No native
build, no LLM, no WebGPU, no ONNX runtime.

THE PROPERTY THAT MATTERS MOST. The weights are read from the SAME GGUF that
built the index (`bge-small-en-v1.5-q8_0.gguf` -> `tv2_base_variants.npz`,
11,550 x 384). Query and key therefore live in one vector space by
construction, not by hope. Rebuilding the index with different weights, or
embedding with a differently-trained ONNX export, is the classic way to make
recall collapse silently -- there is no error, just worse answers.

Two details that silently ruin a reimplementation, both taken from the file
rather than assumed:
  * `bert.pooling_type = 2`, which is CLS -- the first token's vector, NOT the
    mean over tokens. Most examples default to mean.
  * `bert.attention.layer_norm_epsilon = 1e-12`, not the 1e-5 that most
    frameworks default to.

Exported for the phone by build_jev_mobile.py; verified against the running
llama-server by prove_jev_embed.py, which is the only reason to trust it.
"""
from __future__ import annotations

import json
import os
import unicodedata

import numpy as np

GGUF = os.environ.get("JEV_BGE_GGUF",
                      r"D:\0000_Raw_LLM Models\bge-small-en-v1.5-q8_0.gguf")


# ------------------------------------------------------------ tokenizer ----
class WordPiece:
    """BERT WordPiece, uncased -- the tokenizer bge was trained with.

    Implemented here rather than pulled from a library because the phone must
    not gain a dependency for 80 lines of string handling, and because the
    vocabulary travels inside the GGUF we already ship.
    """

    def __init__(self, tokens, cls_id, sep_id, unk_id, pad_id):
        self.vocab = {t: i for i, t in enumerate(tokens)}
        self.cls, self.sep, self.unk, self.pad = cls_id, sep_id, unk_id, pad_id

    @staticmethod
    def _clean(text):
        out = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD:
                continue
            out.append(" " if ch in ("\t", "\n", "\r") or
                       unicodedata.category(ch) == "Zs" else ch)
        return "".join(out)

    @staticmethod
    def _strip_accents(text):
        # uncased BERT lowercases AND strips accents; skipping the second step
        # silently changes the tokenisation of any accented word.
        n = unicodedata.normalize("NFD", text)
        return "".join(c for c in n if unicodedata.category(c) != "Mn")

    @staticmethod
    def _is_punct(ch):
        cp = ord(ch)
        if (33 <= cp <= 47) or (58 <= cp <= 64) or (91 <= cp <= 96) or \
           (123 <= cp <= 126):
            return True
        return unicodedata.category(ch).startswith("P")

    def _basic(self, text):
        text = self._strip_accents(self._clean(text).lower())
        words, cur = [], []
        for ch in text:
            if ch == " ":
                if cur:
                    words.append("".join(cur))
                    cur = []
            elif self._is_punct(ch):
                if cur:
                    words.append("".join(cur))
                    cur = []
                words.append(ch)
            else:
                cur.append(ch)
        if cur:
            words.append("".join(cur))
        return words

    # U+2581 LOWER ONE EIGHTH BLOCK. llama.cpp converts BERT's WordPiece
    # vocabulary into SentencePiece form when it writes a GGUF, so a
    # WORD-INITIAL piece is stored as "▁the" and a CONTINUATION piece is
    # stored BARE -- there is not a single "##" token in the file. Reading it
    # as ordinary WordPiece looks up "the", misses, and falls through to [UNK]:
    # measured, three of seven tokens in "the wolf shall dwell with the lamb"
    # became unknown and the resulting vector agreed with llama.cpp at cosine
    # 0.53. Nothing raised. This is the detail that would have silently
    # wrecked the port, and it is why prove_jev_embed compares token IDs
    # against llama-server's own /tokenize rather than trusting a cosine.
    MARK = "▁"

    def _wordpiece(self, word):
        whole = self.MARK + word
        if whole in self.vocab:
            return [self.vocab[whole]]
        if len(word) > 100:
            return [self.unk]
        out, start, first = [], 0, True
        while start < len(word):
            end = len(word)
            piece_id = None
            while start < end:
                piece = (self.MARK if first else "") + word[start:end]
                if piece in self.vocab:
                    piece_id = self.vocab[piece]
                    break
                end -= 1
            if piece_id is None:
                return [self.unk]        # whole word unknown, per BERT
            out.append(piece_id)
            start = end
            first = False
        return out

    def encode(self, text, max_len=512):
        ids = [self.cls]
        for w in self._basic(text):
            ids.extend(self._wordpiece(w))
            if len(ids) >= max_len - 1:
                break
        ids = ids[:max_len - 1] + [self.sep]
        return ids


# -------------------------------------------------------------- weights ----
def _dequant_q8_0(raw, shape):
    """Q8_0: blocks of 32 int8 with one f16 scale each."""
    blk = 32
    n = int(np.prod(shape))
    nb = n // blk
    b = raw.view(np.uint8).reshape(nb, 2 + blk)
    scales = b[:, :2].copy().view(np.float16).astype(np.float32).reshape(nb, 1)
    q = b[:, 2:].view(np.int8).astype(np.float32)
    return (q * scales).reshape(shape)


def load_weights(path=GGUF):
    """{name: float32 array} -- dequantised once, on the machine that exports."""
    from gguf import GGUFReader
    r = GGUFReader(path)
    W = {}
    for t in r.tensors:
        shape = tuple(int(x) for x in t.shape)
        if t.tensor_type.name == "F32":
            W[t.name] = np.asarray(t.data, dtype=np.float32).reshape(
                shape[::-1]) if len(shape) > 1 else np.asarray(
                t.data, dtype=np.float32)
        elif t.tensor_type.name == "Q8_0":
            # GGUF stores [in, out]; numpy wants [out, in] for x @ W.T
            W[t.name] = _dequant_q8_0(np.asarray(t.data), shape[::-1])
        else:
            W[t.name] = np.asarray(t.data, dtype=np.float32)
    meta = {}
    for f in r.fields.values():
        if f.name in ("bert.block_count", "bert.embedding_length",
                      "bert.attention.head_count",
                      "bert.attention.layer_norm_epsilon",
                      "bert.pooling_type"):
            meta[f.name] = f.parts[f.data[0]][0]
    tf = r.fields["tokenizer.ggml.tokens"]
    tokens = [bytes(tf.parts[i]).decode("utf-8", "replace") for i in tf.data]
    ids = {k: int(r.fields["tokenizer.ggml." + k].parts[
        r.fields["tokenizer.ggml." + k].data[0]][0])
        for k in ("cls_token_id", "seperator_token_id", "unknown_token_id",
                  "padding_token_id")}
    return W, meta, tokens, ids


# -------------------------------------------------------------- forward ----
def _layernorm(x, w, b, eps):
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * w + b


def _gelu(x):
    # the exact erf GELU, which is what BERT uses -- the tanh approximation
    # differs by enough to move a cosine in the third decimal.
    from math import sqrt
    return 0.5 * x * (1.0 + _erf(x / sqrt(2.0)))


def _erf(x):
    # Abramowitz-Stegun 7.1.26, vectorised: |eps| < 1.5e-7, well under the
    # tolerance the parity proof holds the whole pipeline to.
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * np.exp(-a * a)
    return s * y


class Embedder:
    """bge-small in numpy. CLS-pooled, L2-normalised, 512-token truncation."""

    def __init__(self, weights=None, meta=None, tokens=None, ids=None,
                 path=GGUF):
        if weights is None:
            weights, meta, tokens, ids = load_weights(path)
        self.W = weights
        self.n_layer = int(meta["bert.block_count"])
        self.n_head = int(meta["bert.attention.head_count"])
        self.eps = float(meta["bert.attention.layer_norm_epsilon"])
        self.d = int(meta["bert.embedding_length"])
        self.tok = WordPiece(tokens, ids["cls_token_id"],
                             ids["seperator_token_id"],
                             ids["unknown_token_id"], ids["padding_token_id"])

    def _block(self, x, i):
        W = self.W
        p = f"blk.{i}."
        h, dh = self.n_head, self.d // self.n_head
        q = x @ W[p + "attn_q.weight"].T + W[p + "attn_q.bias"]
        k = x @ W[p + "attn_k.weight"].T + W[p + "attn_k.bias"]
        v = x @ W[p + "attn_v.weight"].T + W[p + "attn_v.bias"]
        n = x.shape[0]
        q = q.reshape(n, h, dh).transpose(1, 0, 2)
        k = k.reshape(n, h, dh).transpose(1, 0, 2)
        v = v.reshape(n, h, dh).transpose(1, 0, 2)
        s = (q @ k.transpose(0, 2, 1)) / np.sqrt(dh)   # no mask: not causal
        s = s - s.max(-1, keepdims=True)
        e = np.exp(s)
        a = e / e.sum(-1, keepdims=True)
        o = (a @ v).transpose(1, 0, 2).reshape(n, self.d)
        o = o @ W[p + "attn_output.weight"].T + W[p + "attn_output.bias"]
        x = _layernorm(x + o, W[p + "attn_output_norm.weight"],
                       W[p + "attn_output_norm.bias"], self.eps)
        f = x @ W[p + "ffn_up.weight"].T + W[p + "ffn_up.bias"]
        f = _gelu(f)
        f = f @ W[p + "ffn_down.weight"].T + W[p + "ffn_down.bias"]
        return _layernorm(x + f, W[p + "layer_output_norm.weight"],
                          W[p + "layer_output_norm.bias"], self.eps)

    def encode(self, text, max_len=512):
        W = self.W
        ids = self.tok.encode(text, max_len)
        n = len(ids)
        x = W["token_embd.weight"][ids].astype(np.float32)
        x = x + W["position_embd.weight"][:n]
        x = x + W["token_types.weight"][0]
        x = _layernorm(x, W["token_embd_norm.weight"],
                       W["token_embd_norm.bias"], self.eps)
        for i in range(self.n_layer):
            x = self._block(x, i)
        v = x[0]                                   # CLS pooling, not mean
        return v / (np.linalg.norm(v) + 1e-9)

    def encode_many(self, texts, max_len=512):
        return np.asarray([self.encode(t, max_len) for t in texts],
                          dtype=np.float32)


_E = None


def get(path=GGUF):
    global _E
    if _E is None:
        _E = Embedder(path=path)
    return _E


def embed(texts, path=GGUF):
    """Drop-in for taviel_decide.embed -- same shape, same space."""
    if isinstance(texts, str):
        texts = [texts]
    return get(path).encode_many(texts).tolist()


if __name__ == "__main__":
    import time
    e = get()
    t0 = time.time()
    v = e.encode("Why does a loving God allow evil and suffering?")
    print(f"dim {v.shape[0]}  norm {np.linalg.norm(v):.6f}  "
          f"{(time.time()-t0)*1000:.0f} ms (first call includes nothing "
          f"lazy -- weights already loaded)")
    t0 = time.time()
    for _ in range(5):
        e.encode("Is the Bible full of contradictions?")
    print(f"{(time.time()-t0)/5*1000:.0f} ms per question, warm")
