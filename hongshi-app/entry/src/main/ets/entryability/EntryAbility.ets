import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    console.info('[HongShi] Ability onCreate');
  }

  onDestroy(): void {
    console.info('[HongShi] Ability onDestroy');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    console.info('[HongShi] onWindowStageCreate');
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        console.error(`[HongShi] loadContent failed: ${JSON.stringify(err)}`);
        return;
      }
      console.info('[HongShi] loadContent success');
    });
  }

  onWindowStageDestroy(): void {}
  onForeground(): void {}
  onBackground(): void {}
}
