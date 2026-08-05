// 舊網址 pla-tracker.pages.dev 一律轉到正式網域，路徑與參數原樣保留
// 只轉列出的主機，不轉 preview 部署（<hash>.pla-tracker.pages.dev），保留預覽測試能力
// GET/HEAD 用 301；其他方法用 308，避免瀏覽器把 POST 改成 GET
//
// ⚠️ 這支檔案在 functions/ 根目錄，Pages 預設會讓**全站每一個請求**都先進來，
// 連 CSS／圖片／CSV 都各算一次 Functions 呼叫，而免費方案的 10 萬次／日是
// **整個帳號 13 個 Pages 專案共用**的。姊妹專案 flight-deck 2026-08-04 就是這樣
// 一天燒掉 74,213 次、收到 Cloudflare 的 75% 警告信。
// 因此根目錄有 `_routes.json` 把靜態路徑排除掉，只有 HTML 文件會進到這裡。
// 新增靜態目錄時要一起加進 `_routes.json` 的 exclude。
const REDIRECT_HOSTS = ["pla-tracker.pages.dev"];
const CANONICAL_HOST = "pla-tracker.skyfaring.net";

// Search Console 對舊網域 pla-tracker.pages.dev 的擁有權驗證檔（2026-08-05 加）。
// 為什麼不放成靜態檔：舊網域整站被下面的規則 301 轉走，而就算把它加進
// `_routes.json` 的 exclude 讓 Function 不跑，Pages 還會把 `/x.html` 308 到 `/x`
// ——兩層轉址都可能讓驗證抓不到檔。這裡直接回 200，兩個主機都適用。
// 驗證通過後**不可刪除**，Google 會定期重新檢查。
const GSC_VERIFY_PATH = "/googlec0b8776e124d248c.html";
const GSC_VERIFY_BODY = "google-site-verification: googlec0b8776e124d248c.html";

export async function onRequest(context) {
  const url = new URL(context.request.url);

  if (url.pathname === GSC_VERIFY_PATH) {
    return new Response(GSC_VERIFY_BODY, {
      headers: { "content-type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  if (!REDIRECT_HOSTS.includes(url.hostname)) return context.next();

  url.hostname = CANONICAL_HOST;
  const status = ["GET", "HEAD"].includes(context.request.method) ? 301 : 308;
  // 轉址一律 no-store：301／308 在沒有 Cache-Control 時會被瀏覽器**無限期快取**，
  // 之後就算改了轉址規則，那些瀏覽器也可能很久都不再問伺服器（改了不生效）。
  // 用 new Response 而非 Response.redirect()，後者產生的回應是 immutable、加不了標頭。
  // 對 SEO 無影響：爬蟲認的是 301 這個狀態碼本身，不靠瀏覽器快取。
  return new Response(null, {
    status,
    headers: { Location: url.toString(), "Cache-Control": "no-store" },
  });
}
