import { webview } from '@kit.ArkWeb';

@Entry
@Component
struct Index {
  controller: webview.WebviewController = new webview.WebviewController();

  aboutToAppear(): void {
    webview.WebviewController.initializeWebEngine();
  }

  build() {
    Column() {
      Web({ src: $rawfile('hongshi.html'), controller: this.controller })
        .width('100%')
        .height('100%')
        .javaScriptAccess(true)
        .domStorageAccess(true)
        .fileAccess(true)
        .onlineImageAccess(true)
        .mixedMode(MixedMode.All)
        .onPageEnd(() => {
          console.info('[HongShi] game page loaded');
        })
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#0d3b2e')
  }
}
