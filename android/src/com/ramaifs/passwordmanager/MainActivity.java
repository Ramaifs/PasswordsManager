package com.ramaifs.passwordmanager;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Browser-backed Android client. Google authentication never runs in a WebView. */
public final class MainActivity extends Activity {
    private static final String SITE = "https://password-manager-vault.masaoyhs.workers.dev/";

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (24 * getResources().getDisplayMetrics().density);
        layout.setPadding(padding, padding, padding, padding);
        TextView text = new TextView(this);
        text.setText("Password Manager 0.41\n\nAndroid-клиент открывает защищённый сайт в вашем браузере. Для загрузки нужен интернет. Хранилища и подключение Google принадлежат профилю браузера.\n\nПеред закрытием сохраните изменения в Google Drive или скачайте файл .pmvault.");
        text.setTextSize(18);
        layout.addView(text);
        Button open = new Button(this);
        open.setText("Открыть хранилища");
        android.graphics.drawable.GradientDrawable border = new android.graphics.drawable.GradientDrawable();
        border.setColor(0xffffffff);
        border.setCornerRadius(8 * getResources().getDisplayMetrics().density);
        border.setStroke(Math.max(1, (int) getResources().getDisplayMetrics().density), 0xff8864cb);
        open.setBackground(border);
        open.setTextColor(0xff6848ab);
        open.setOnClickListener(view -> openVault());
        layout.addView(open);
        setContentView(layout);
        if (savedInstanceState == null) openVault();
    }

    private void openVault() {
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(SITE));
        intent.addCategory(Intent.CATEGORY_BROWSABLE);
        // A null session is supported by Custom Tabs; it does not embed a WebView.
        Bundle extras = new Bundle();
        extras.putBinder("android.support.customtabs.extra.SESSION", null);
        intent.putExtras(extras);
        intent.putExtra("android.support.customtabs.extra.TOOLBAR_COLOR", 0xff8864cb);
        intent.putExtra("android.support.customtabs.extra.SHARE_MENU_ITEM", false);
        ResolveInfo browser = getPackageManager().resolveActivity(intent, 0);
        if (browser != null && browser.activityInfo != null) {
            Intent service = new Intent("android.support.customtabs.action.CustomTabsService");
            service.setPackage(browser.activityInfo.packageName);
            if (getPackageManager().resolveService(service, 0) != null) intent.setPackage(browser.activityInfo.packageName);
        }
        try { startActivity(intent); }
        catch (ActivityNotFoundException error) {
            new android.app.AlertDialog.Builder(this).setTitle("Нужен браузер")
                .setMessage("Установите или включите Chrome, Firefox либо другой браузер с поддержкой HTTPS.")
                .setPositiveButton("OK", null).show();
        }
    }
}
