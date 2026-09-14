package me.realizeus.yahbible;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * YahBible Mobile — a native WebView shell around the fully-offline web UI in
 * assets/web/. Kept dependency-free (framework Material theme, no AndroidX) so
 * the APK builds with only the Android Gradle Plugin.
 */
public class MainActivity extends Activity {

    private WebView web;
    private PermissionRequest pendingWebPerm;
    private static final int REQ_CAMERA = 11;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Window w = getWindow();
        w.setStatusBarColor(0xFF130F1B);
        w.setNavigationBarColor(0xFF130F1B);

        web = new WebView(this);
        web.setBackgroundColor(0xFF130F1B);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);                 // localStorage (news-seen, drafts)
        s.setMediaPlaybackRequiresUserGesture(false); // let the self-cam start
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW); // LAN pairing to desktop http
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                view.loadUrl(url);
                return true;
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                for (String r : request.getResources()) {
                    if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) {
                        if (checkSelfPermission(Manifest.permission.CAMERA)
                                == PackageManager.PERMISSION_GRANTED) {
                            runOnUiThread(() -> request.grant(request.getResources()));
                        } else {
                            pendingWebPerm = request;
                            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
                        }
                        return;
                    }
                }
                runOnUiThread(request::deny);
            }
        });

        web.loadUrl("file:///android_asset/web/index.html");
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] results) {
        super.onRequestPermissionsResult(req, perms, results);
        if (req == REQ_CAMERA && pendingWebPerm != null) {
            final PermissionRequest p = pendingWebPerm;
            pendingWebPerm = null;
            boolean granted = results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED;
            runOnUiThread(() -> {
                if (granted) p.grant(p.getResources()); else p.deny();
            });
        }
    }

    @Override
    public void onBackPressed() {
        // Return to the Home tab first; a second back from Home exits.
        web.evaluateJavascript("window.__tab", value -> {
            if (value != null && value.contains("home")) {
                finish();
            } else {
                web.evaluateJavascript("window.__goHome && window.__goHome();", null);
            }
        });
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
