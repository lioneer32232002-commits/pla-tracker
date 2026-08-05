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

export async function onRequest(context) {
  const url = new URL(context.request.url);
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
