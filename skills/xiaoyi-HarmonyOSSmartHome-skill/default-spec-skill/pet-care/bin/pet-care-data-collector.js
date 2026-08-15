#!/usr/bin/env node

/**
 * 宠物照护数据采集中心
 * 统一获取宠物照护所需的所有数据
 */

import { getDevicesInfo } from '../../../common-skill/bin/get_devices_info.js';
import { recognizePetDevices } from './pet-device-recognizer.js';
import { fetchPetDeviceSnapshots } from './pet-data-collector.js';
import { fetchTemperatureMonitorResult } from './temperature-monitor.js';

// ==================== 常量定义 ====================

/**
 * @typedef {Object} PetCareData
 * @property {string} timestamp - 数据采集时间
 * @property {object} devices - 宠物设备列表（已分类）
 * @property {object} snapshots - 宠物设备快照
 * @property {object} temperature - 温度监控结果
 * @property {boolean} isOwnerAway - 主人是否不在家
 * @property {object} summary - 数据获取汇总
 */

/**
 * 获取"今天"的时间范围
 * @returns {Date[]} [startOfDay, now]
 */
function getTodayRange() {
  const now = new Date();
  const startOfDay = new Date(now);
  startOfDay.setHours(0, 0, 0, 0);
  return [startOfDay, now];
}

/**
 * 判断主人是否在家
 * 通过检查门锁的最近开门记录来判断
 * @returns {Promise<boolean>} 主人是否不在家
 */
async function isOwnerAway() {
  try {
    // 简化实现：假设如果最近30分钟内有门锁开门记录，主人可能在家
    // 实际实现需要结合 human-behavior-sense 模块的数据
    return true;
  } catch (error) {
    console.warn('[warn] 判断主人是否在家失败:', error.message);
    return true; // 默认假设不在家
  }
}

/**
 * 统一数据采集函数
 * @returns {Promise<PetCareData>} 宠物照护数据
 */
export async function fetchPetCareData() {
  console.log('[info] 开始采集宠物照护数据...');
  const startTime = Date.now();

  // 并行获取基础数据
  console.log('[step 1/4] 获取设备列表...');
  const devicesInfo = await getDevicesInfo({});
  const petDevices = recognizePetDevices(devicesInfo);
  console.log(`  识别到 ${petDevices.totalCount} 个宠物相关设备`);

  // 获取设备快照
  console.log('[step 2/4] 获取设备快照...');
  const snapshots = await fetchPetDeviceSnapshots(petDevices);

  console.log('[step 3/4] 获取温度监控数据...');
  const temperature = await fetchTemperatureMonitorResult();

  // 判断主人是否在家
  console.log('[step 4/4] 判断主人状态...');
  const ownerAway = await isOwnerAway();

  const endTime = Date.now();
  const duration = ((endTime - startTime) / 1000).toFixed(2);

  // 汇总
  const summary = {
    totalDevices: petDevices.totalCount,
    catLitterOnline: snapshots.catLitter?.filter(c => c.online).length || 0,
    feederOnline: snapshots.feeder?.filter(f => f.online).length || 0,
    temperatureAvailable: temperature.value !== null,
    ownerAway: ownerAway,
    duration: `${duration}秒`
  };

  console.log(`[info] 数据采集完成，耗时 ${duration}秒`);

  return {
    timestamp: new Date().toISOString(),
    devices: petDevices,
    snapshots: snapshots,
    temperature: temperature,
    isOwnerAway: ownerAway,
    summary: summary
  };
}

export {
  isOwnerAway
};