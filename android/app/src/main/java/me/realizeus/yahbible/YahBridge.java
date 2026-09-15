package me.realizeus.yahbible;

import android.app.Activity;
import android.system.Os;
import android.webkit.JavascriptInterface;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.zip.GZIPInputStream;

/**
 * The FULL DESKTOP ENGINE bridge: downloads the desktop data tree + AI model into
 * filesDir/yb, boots the real O'Tav'iel Python server in-process (localhost:41537),
 * and exposes engine/AI state to the web UI. window.YahNative.* from JS.
 */
public final class YahBridge {

    private final Activity act;
    private final File base;                 // filesDir/yb — the YAHBIBLE_BASE tree
    private static volatile boolean engineStarting = false;
    private static volatile boolean engineUp = false;
    private static final Map<String, long[]> DL = new ConcurrentHashMap<>();   // rel -> {done,total,state}
    private static final Map<String, String> DLERR = new ConcurrentHashMap<>();

    public YahBridge(Activity act) {
        this.act = act;
        this.base = new File(act.getFilesDir(), "yb");
        TavLlm.init(act);
    }

    /* ---------- paths & presence ---------- */

    @JavascriptInterface
    public String basePath() { return base.getAbsolutePath(); }

    @JavascriptInterface
    public boolean hasFile(String rel) {
        File f = new File(base, rel);
        return f.isFile() && f.length() > 0;
    }

    @JavascriptInterface
    public long fileSize(String rel) {
        File f = new File(base, rel);
        return f.isFile() ? f.length() : -1;
    }

    @JavascriptInterface
    public long freeBytes() { return base.getParentFile().getFreeSpace(); }

    /* ---------- downloads (gz-aware, resumable-by-redownload, progress-polled) ---------- */

    @JavascriptInterface
    public void download(final String url, final String rel, final boolean gunzip) {
        final String key = rel;
        long[] st = DL.get(key);
        if (st != null && st[2] == 0) return;          // already running
        DL.put(key, new long[]{0, 0, 0});              // state 0=running 1=done 2=error
        DLERR.remove(key);
        new Thread(() -> {
            File out = new File(base, rel);
            File part = new File(base, rel + ".part");
            try {
                out.getParentFile().mkdirs();
                HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(30000);
                c.setReadTimeout(60000);
                c.setInstanceFollowRedirects(true);
                long total = c.getContentLengthLong();
                DL.put(key, new long[]{0, Math.max(total, 0), 0});
                InputStream in = c.getInputStream();
                java.io.InputStream src = gunzip ? new GZIPInputStream(in, 1 << 16) : in;
                FileOutputStream fo = new FileOutputStream(part);
                byte[] buf = new byte[1 << 16];
                long done = 0;
                int n;
                while ((n = src.read(buf)) > 0) {
                    fo.write(buf, 0, n);
                    done += n;
                    long[] cur = DL.get(key);
                    DL.put(key, new long[]{done, cur == null ? 0 : cur[1], 0});
                }
                fo.close();
                src.close();
                if (out.exists()) out.delete();
                if (!part.renameTo(out)) throw new RuntimeException("rename failed");
                long[] cur = DL.get(key);
                DL.put(key, new long[]{done, cur == null ? done : Math.max(cur[1], done), 1});
            } catch (Throwable t) {
                part.delete();
                DL.put(key, new long[]{0, 0, 2});
                DLERR.put(key, String.valueOf(t));
            }
        }, "yb-dl-" + rel).start();
    }

    @JavascriptInterface
    public String dlStatus(String rel) {
        long[] st = DL.get(rel);
        if (st == null) return "{\"state\":\"none\"}";
        String s = st[2] == 0 ? "running" : (st[2] == 1 ? "done" : "error");
        String err = DLERR.getOrDefault(rel, "");
        return "{\"state\":\"" + s + "\",\"done\":" + st[0] + ",\"total\":" + st[1]
                + ",\"error\":\"" + err.replace("\"", "'").replace("\\", "/") + "\"}";
    }

    /* ---------- the engine: the real Python desktop server, in-process ---------- */

    @JavascriptInterface
    public void startEngine() {
        if (engineUp || engineStarting) return;
        engineStarting = true;
        new Thread(() -> {
            try {
                try {
                    Os.setenv("YAHBIBLE_BASE", base.getAbsolutePath(), true);
                    Os.setenv("YAHBIBLE_NO_D", "1", true);
                    Os.setenv("YAHBIBLE_ANDROID", "1", true);
                    Os.setenv("YAHBIBLE_SHIPPED", "1", true);
                    Os.setenv("YAHBIBLE_LAN", "1", true);   // 📡 a computer on this phone's Wi-Fi/hotspot can mirror the app
                    Os.setenv("HOME", act.getFilesDir().getAbsolutePath(), true);
                } catch (Throwable ignored) {}
                if (!Python.isStarted()) Python.start(new AndroidPlatform(act));
                Python py = Python.getInstance();
                Object ok = py.getModule("yahbible_boot").callAttr("start").toJava(Object.class);
                engineUp = Boolean.TRUE.equals(ok);
            } catch (Throwable t) {
                engineUp = false;
            } finally {
                engineStarting = false;
            }
        }, "yb-engine").start();
    }

    @JavascriptInterface
    public String engineState() {
        return engineUp ? "up" : (engineStarting ? "starting" : "down");
    }

    /* ---------- AI presence (the model file the engine's Tav'iel will load) ---------- */

    @JavascriptInterface
    public boolean aiInstalled() {
        File dir = new File(base, "ai");
        String[] fs = dir.list((d, n) -> n.endsWith(".task"));
        return fs != null && fs.length > 0;
    }

    @JavascriptInterface
    public boolean aiLoaded() { return TavLlm.isLoaded(); }

    /** This phone's LAN/hotspot IPv4 — a computer on the same network mirrors the app there. */
    @JavascriptInterface
    public String lanAddress() {
        try {
            java.util.Enumeration<java.net.NetworkInterface> ifs =
                    java.net.NetworkInterface.getNetworkInterfaces();
            while (ifs.hasMoreElements()) {
                java.net.NetworkInterface ni = ifs.nextElement();
                if (!ni.isUp() || ni.isLoopback()) continue;
                java.util.Enumeration<java.net.InetAddress> as = ni.getInetAddresses();
                while (as.hasMoreElements()) {
                    java.net.InetAddress a = as.nextElement();
                    if (a instanceof java.net.Inet4Address && a.isSiteLocalAddress())
                        return a.getHostAddress();
                }
            }
        } catch (Throwable ignored) {}
        return "";
    }
}
