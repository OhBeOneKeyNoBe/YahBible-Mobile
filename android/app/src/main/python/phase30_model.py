"""Phase 30: the model, hosted inside the 683 MB third.

Elan'iel's standing constraint, which comes before the build: his machine is
not a server farm and a model must never sit resident while idle. So this
adapter owns the whole lifetime -- start, use, stop -- and stopping is not
optional cleanup at the end of a happy path. It runs in a context manager, and
the process is killed on the way out whether the run succeeded, failed, or was
interrupted.

llama.cpp rather than transformers, for the reason Phase 27 measured rather than
assumed: four separate transformers approaches to layer streaming failed on this
card (hand-rolled streaming and residency hooks both faulted at 0xC0000005,
Accelerate's device_map was silently ignored and put all 340 parameters on CPU,
and bitsandbytes 4-bit raised "invalid resource handle"). llama.cpp's
--n-gpu-layers is the aperture that actually works here.

The VRAM cap is enforced by REFUSAL, not by hope. If the card is already too
busy for the third to fit, the loop runs without a model rather than competing
with whatever Elan'iel has open.
"""

import json
import random
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

LLAMA_SERVER = r"D:\llama.cpp\build-cuda-mmq\bin\llama-server.exe"
VRAM_CAP_MB = 683  # one third, his ruling
PORT = 8099


def vram_used_mb():
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return int(out.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


class VramRefusal(RuntimeError):
    """The card has no room for the third. Refused, not squeezed in."""


class LlamaModel:
    """A model that exists only for as long as it is being used."""

    def __init__(self, model_path, gpu_layers=99, ctx=4096, port=PORT, total_mb=4096,
                 threads=None, priority=None, batch=None):
        self.model_path = model_path
        self.gpu_layers = gpu_layers
        self.ctx = ctx
        self.port = port
        self.total_mb = total_mb
        # resource caps so a big disk-streamed tier can NEVER overload the system:
        #   threads  -> few CPU threads (leaves cores for the RAM voice + other apps)
        #   priority -> 'idle'/'belownormal' OS priority (runs only on spare cycles = a trickle)
        #   batch    -> small batch/ubatch (bounded memory + CPU spikes)
        self.threads = threads
        self.priority = priority
        self.batch = batch
        self.proc = None
        self.baseline_mb = None
        self.peak_mine_mb = 0

    def __enter__(self):
        """Start, MEASURE, and shrink until the model is actually inside the third.

        The first version of this checked only whether the card had room before
        starting, then started with every layer offloaded and never looked
        again. It took 951 MB against a 683 MB third and reported success. A cap
        that is checked before the thing it caps happens is not a cap.

        So the aperture is now closed until the model fits: load, measure what
        was actually taken, and if it exceeds the third, stop and retry with
        fewer layers on the GPU. If no setting fits, that is refused and said,
        not quietly accepted.
        """
        self.baseline_mb = vram_used_mb()
        if self.baseline_mb is not None:
            headroom = self.total_mb - self.baseline_mb - 200  # 200MB for the driver
            if headroom < VRAM_CAP_MB:
                raise VramRefusal(
                    f"the card already holds {self.baseline_mb} MB of"
                    f" {self.total_mb} MB, leaving {headroom} MB -- less than the"
                    f" {VRAM_CAP_MB} MB third. Refusing to start rather than"
                    " competing with what is already running."
                )
        for attempt, layers in enumerate(self._ladder()):
            self.gpu_layers = layers
            self._start()
            taken = self._sample_vram()
            mine = (taken - self.baseline_mb) if taken is not None else None
            if mine is None or mine <= VRAM_CAP_MB:
                print(
                    f"  model inside the third: {mine} MB with {layers} layers"
                    f" on the GPU (cap {VRAM_CAP_MB} MB)"
                    + (f" after {attempt} step(s) down" if attempt else ""),
                    flush=True,
                )
                return self
            print(
                f"  {mine} MB exceeds the {VRAM_CAP_MB} MB third at"
                f" {layers} layers -- closing the aperture and retrying",
                flush=True,
            )
            self.stop()
            self.peak_mine_mb = 0
            time.sleep(3)
        raise VramRefusal(
            f"no offload setting kept this model inside the {VRAM_CAP_MB} MB"
            " third. Refused rather than run over the cap."
        )

    # MEASURED, not searched. The ladder below used to start at every layer and
    # step down, which for Qwen3-8B meant six full model loads and 53 seconds of
    # thrash before the first token -- rediscovering on every launch a fact that
    # does not change. phase30_bench.py measured it once, on the real packet
    # workload, four reps with the spread reported, and these are the winners:
    #
    #   Qwen3-8B    ngl=0    169 MB    4.74 t/s   38.0 s/turn
    #               (ngl=1 costs 488 MB more and is SLOWER: 4.48 t/s. Offloading
    #                one layer of an 8B buys nothing -- the pass is bound by
    #                streaming the other layers over PCIe either way.)
    #   Qwen3-0.6B  ngl=12   600 MB   48.54 t/s    3.7 s/turn -- 5.85x the
    #               Phase 23 baseline on 0.29x its memory.
    #
    # The measurement still runs at startup, so a wrong entry here is caught
    # rather than trusted; the table only removes the search.
    MEASURED = {
        "Qwen3-8B": 0,
        "Qwen3-0.6B": 12,
        "gemma-3-1b": 10,
    }

    def _ladder(self):
        """Offload settings to try, best measured first."""
        base = os.path.basename(self.model_path)
        for key, layers in self.MEASURED.items():
            if key.lower() in base.lower():
                # the measured setting first; the search remains as a fallback
                # for a machine whose free VRAM differs from when it was measured
                return [layers, 10, 6, 3, 0]
        return [self.gpu_layers, 20, 14, 10, 6, 3, 0]

    def _start(self):
        args = [
            LLAMA_SERVER, "-m", self.model_path,
            "--n-gpu-layers", str(self.gpu_layers),
            "-c", str(self.ctx),
            "--port", str(self.port),
            "--host", "127.0.0.1",
            "-fa", "on",
        ]
        # RESOURCE CAPS: guarantee a big disk-streamed tier stays a trickle that never
        # overloads the box. mmap is llama.cpp's default (weights page from disk, not all in
        # RAM) -- we do NOT pass --no-mmap or --mlock, so the OS keeps only the working set.
        if self.threads:
            args += ["--threads", str(self.threads), "--threads-batch", str(self.threads)]
        if self.batch:
            args += ["-b", str(self.batch), "-ub", str(self.batch)]
        creationflags = 0
        if os.name == "nt":
            creationflags |= 0x08000000  # CREATE_NO_WINDOW
            if self.priority == "idle":
                creationflags |= 0x00000040  # IDLE_PRIORITY_CLASS -> only spare CPU cycles
            elif self.priority == "belownormal":
                creationflags |= 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
        self.proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        deadline = time.time() + 180
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"llama-server exited with {self.proc.returncode} before"
                    " it was ready"
                )
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/health", timeout=3
                ) as r:
                    if r.status == 200:
                        break
            except (urllib.error.URLError, OSError):
                time.sleep(2)
        else:
            self.stop()
            raise RuntimeError("llama-server never became ready within 180s")
        self._sample_vram()
        return self

    def _sample_vram(self):
        now = vram_used_mb()
        if now is not None and self.baseline_mb is not None:
            self.peak_mine_mb = max(self.peak_mine_mb, now - self.baseline_mb)
        return now

    INSTRUCTION = (
        "You are answering from a context packet assembled by a memory system."
        " Use ONLY what the packet contains. If the packet does not contain the"
        " answer, say so plainly and do not invent one. Answer in two or three"
        " sentences, in your own words -- do NOT repeat the packet's section"
        " headings back.\n\n"
    )

    def complete(
        self, prompt, max_tokens=220, grammar=None, system=None, temperature=0.3
    ):
        """One completion, wrapped in the model's own chat template.

        Handing a raw packet to an instruction-tuned model with no instruction
        made it continue the DOCUMENT rather than answer from it -- the first
        live turn came back as "--- NOTES --- (nothing available for this
        section)", which is the packet's own formatting echoed. The packet is
        material, not a prompt, and the difference has to be stated to the model
        explicitly or the whole loop measures the wrong thing.
        """
        # The CHAT endpoint, so llama-server applies each model's OWN template
        # out of its GGUF. Hand-writing gemma's <start_of_turn> markers worked
        # for gemma and returned empty strings from Qwen, which uses ChatML --
        # and an empty answer from a control arm looks exactly like a control
        # arm that failed. A hardcoded template silently limits the harness to
        # one model family, which is the opposite of what a control is for.
        payload = {
            "messages": [
                {"role": "system", "content": (system or self.INSTRUCTION).strip()},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.92,
            # a FRESH random seed each call, so the same question is answered anew
            # every time (a fixed/default seed made every reply word-for-word identical)
            "seed": random.randint(1, 2147483647),
            # discourage the verbatim-repeat / self-parroting behavior
            "presence_penalty": 0.6,
            "frequency_penalty": 0.5,
        }
        if grammar:
            # A GRAMMAR, NOT A PLEA. Asking a model to "reply with JSON only"
            # is a request it can decline mid-sentence, and a driver that then
            # tries to salvage a command out of prose is guessing at intent
            # while holding execute permission. llama.cpp constrains sampling
            # to the grammar, so a malformed selection is not a thing the model
            # is able to emit.
            payload["grammar"] = grammar
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                out = json.loads(r.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            return f"(the model did not answer: {exc})"
        self._sample_vram()
        try:
            text = out["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return "(the model returned no message)"
        # Reasoning models wrap their thinking; the answer is what follows it.
        if "</think>" in text:
            text = text.split("</think>", 1)[1]
        return text.strip()

    def complete_stream(self, prompt, max_tokens=220, system=None, temperature=0.3):
        """Same as complete(), but yields text deltas as the model produces them
        (llama-server SSE, stream=true) -- so the reader sees the answer churn out a
        word at a time instead of one big chunk after the full generation."""
        payload = {
            "messages": [
                {"role": "system", "content": (system or self.INSTRUCTION).strip()},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.92,
            "seed": random.randint(1, 2147483647),   # fresh each call → varied replies
            "presence_penalty": 0.6,
            "frequency_penalty": 0.5,
            "stream": True,
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=body, headers={"Content-Type": "application/json"},
        )
        in_think = False
        try:
            r = urllib.request.urlopen(req, timeout=600)
        except (urllib.error.URLError, OSError):
            return
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content", "")
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                continue
            if not delta:
                continue
            # skip any <think>...</think> span (defensive; /no_think normally prevents it)
            if "<think>" in delta:
                in_think = True
                delta = delta.split("<think>", 1)[0]
            if in_think:
                if "</think>" in delta:
                    in_think = False
                    delta = delta.split("</think>", 1)[1]
                else:
                    continue
            if delta:
                yield delta

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=25)
        self.proc = None

    def __exit__(self, *exc):
        # Not conditional on success. A model left running because a run raised
        # is exactly the failure his standing rule is about.
        self.stop()
        time.sleep(2)
        after = vram_used_mb()
        print(
            f"  model stopped; VRAM {self.baseline_mb} MB before ->"
            f" {after} MB after (peak mine: {self.peak_mine_mb} MB against the"
            f" {VRAM_CAP_MB} MB third)",
            flush=True,
        )
        return False


if __name__ == "__main__":
    print(f"VRAM in use right now: {vram_used_mb()} MB", file=sys.stderr)
