package me.realizeus.yahbible;

import android.content.Context;

import com.google.mediapipe.tasks.genai.llminference.LlmInference;

/**
 * Tav'iel's on-device mind: a LiteRT .task model (Qwen2.5-1.5B-Instruct or
 * DeepSeek-R1-Distill) served through MediaPipe LLM inference, fully offline.
 * Reached from Python (the grounded ask pipeline) over the Chaquopy bridge.
 */
public final class TavLlm {

    private static LlmInference llm;
    private static String loadedPath;
    private static Context appCtx;
    private static volatile String lastError = "";

    private TavLlm() {}

    static void init(Context ctx) {
        appCtx = ctx.getApplicationContext();
    }

    /** Load (or keep) the model at path. Returns true when ready. */
    public static synchronized boolean ensure(String path, int maxTokens) {
        try {
            if (llm != null && path.equals(loadedPath)) return true;
            unload();
            LlmInference.LlmInferenceOptions opts =
                    LlmInference.LlmInferenceOptions.builder()
                            .setModelPath(path)
                            .setMaxTokens(Math.max(512, maxTokens))
                            .build();
            llm = LlmInference.createFromOptions(appCtx, opts);
            loadedPath = path;
            lastError = "";
            return true;
        } catch (Throwable t) {
            llm = null;
            loadedPath = null;
            lastError = String.valueOf(t);
            return false;
        }
    }

    /** The exact reason the last load or generation failed — truth over silence. */
    public static String lastError() { return lastError; }

    /** Blocking generation — called from a Python worker thread, never the UI. */
    public static synchronized String generate(String prompt, int maxTokens) {
        if (llm == null) return "";
        try {
            return llm.generateResponse(prompt);
        } catch (Throwable t) {
            lastError = String.valueOf(t);
            return "";
        }
    }

    /** Machine-first: free the model's memory. */
    public static synchronized void unload() {
        if (llm != null) {
            try { llm.close(); } catch (Throwable ignored) {}
            llm = null;
            loadedPath = null;
        }
    }

    public static synchronized boolean isLoaded() {
        return llm != null;
    }
}
