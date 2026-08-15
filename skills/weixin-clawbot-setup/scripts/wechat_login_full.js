/**
 * WeChat Login Full Automation Script
 * 
 * 一次运行完成：生成二维码 → 等待扫码 → 保存账号 → 触发 reload
 * 
 * Usage: node /path/to/wechat_login_full.js
 * 
 * Output signals:
 *   stdout: QR_URL:<url>        - 二维码链接
 *           DONE:<accountId>    - 登录成功，账号已保存
 *           DUP:<message>       - 该微信已绑定过
 *           FAIL:<message>      - 登录失败
 *   stderr: 日志信息
 *   file:   /tmp/wechat_qr_login.png - 二维码图片
 */

const pluginDir = "/home/sandbox/.openclaw/extensions/openclaw-weixin/dist/src";
const fs = await import("fs");
const path = await import("path");

const loginQr = await import(path.join(pluginDir, "auth", "login-qr.js"));
const accounts = await import(path.join(pluginDir, "auth", "accounts.js"));

// Step 1: Generate QR code
console.error("[微信登录] 正在获取二维码...");
const start = await loginQr.startWeixinLoginWithQr({
  accountId: "relogin-" + Date.now(),
  force: true,
  verbose: false,
});

if (!start.qrcodeUrl) {
  console.log("FAIL:获取二维码失败 - " + start.message);
  process.exit(1);
}

// Output QR URL for the agent to use
console.log("QR_URL:" + start.qrcodeUrl);
console.error("[微信登录] 二维码已获取，等待用户扫描...");

// Step 2: Wait for user to scan (blocking, up to 5 min)
const result = await loginQr.waitForWeixinLogin({
  sessionKey: start.sessionKey,
  timeoutMs: 300000,
  verbose: false,
});

if (result.connected && result.botToken && result.accountId) {
  // Step 3: Save account
  console.error("[微信登录] 扫码成功，保存账号...");
  
  // The accounts module handles normalization internally
  // We need to ensure the normalized form is used for storage
  let accountId = result.accountId;
  
  accounts.saveWeixinAccount(accountId, {
    token: result.botToken,
    baseUrl: result.baseUrl || accounts.DEFAULT_BASE_URL,
    userId: result.userId,
  });
  accounts.registerWeixinAccountId(accountId);
  
  // Clear stale context tokens for same userId
  if (result.userId) {
    const inbound = await import(path.join(pluginDir, "messaging", "inbound.js"));
    accounts.clearStaleAccountsForUserId(accountId, result.userId, inbound.clearContextTokensForAccount);
  }
  
  // Trigger channel reload (writes config changes to openclaw.json)
  accounts.triggerWeixinChannelReload();
  
  console.log("DONE:" + accountId);
  console.error("[微信登录] ✅ 账号已保存: " + accountId);
} else if (result.alreadyConnected) {
  console.log("DUP:" + result.message);
} else {
  console.log("FAIL:" + result.message);
}
