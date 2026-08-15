#!/usr/bin/env node

/**
 * 家庭简报数据收集脚本
 * 整合所有数据获取步骤为单一脚本执行
 *
 * 使用方法:
 * node family-brief-data-collector.js
 * node family-brief-data-collector.js --home-id {家庭ID}
 *
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);

// ES module 兼容: 获取 __dirname 和 __filename
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 配置路径
const CONFIG = {
    basePath: path.resolve(__dirname, '../../..'),
    outputDir: path.resolve(__dirname, '../out_put/family_brief'),
    commonSkillBin: path.resolve(__dirname, '../../../common-skill/bin'),
    routerSkillBin: path.resolve(__dirname, '../../../router-skill/bin')
};

// ==================== 直接导入模块函数 ====================
import { getHomesInfo } from '../../../common-skill/bin/get_homes_info.js';
import { getDevicesInfo, getDeviceServiceSnapshot } from '../../../common-skill/bin/get_devices_info.js';
import { getDeviceMessages } from '../../../common-skill/bin/get_device_messages.js';
import { getDeviceHistories } from '../../../common-skill/bin/get_device_histories.js';

// 执行命令并返回结果
async function execCommand(cmd) {
    try {
        const result = await execAsync(cmd, {
            encoding: 'utf-8',
            cwd: CONFIG.basePath,
            maxBuffer: 50 * 1024 * 1024
        });
        return { success: true, data: result.stdout };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

// 创建输出目录
function ensureOutputDir() {
    if (!fs.existsSync(CONFIG.outputDir)) {
        fs.mkdirSync(CONFIG.outputDir, { recursive: true });
    }
}



// 保存数据到文件
function saveData(filename, data) {
    const filepath = path.join(CONFIG.outputDir, filename);
    fs.writeFileSync(filepath, typeof data === 'object' ? JSON.stringify(data, null, 2) : data);
    return filepath;
}

// 第一步：获取家庭信息
async function fetchHomesInfo() {
    console.log('[1/12] 获取家庭信息...');
    try {
        const result = await getHomesInfo();
        console.log('  [OK] 获取家庭信息成功');
        return result;
    } catch (error) {
        console.log('  [FAIL] 获取家庭信息失败:', error.message);
        return null;
    }
}

// 第二步：获取设备基础信息
async function fetchDevicesInfo() {
    console.log('[2/12] 获取设备基础信息...');
    try {
        const result = await getDevicesInfo({});
        console.log('  [OK] 获取设备基础信息成功');
        return result;
    } catch (error) {
        console.log('  [FAIL] 获取设备基础信息失败:', error.message);
        return null;
    }
}

// 第三步：获取所有设备详细信息
async function fetchDevicesDetail(devicesInfo) {
    console.log('[3/12] 获取设备详细信息...');

    if (!devicesInfo || !Array.isArray(devicesInfo)) {
        console.log('  [SKIP] 设备信息为空，跳过详细信息获取');
        return [];
    }

    const devIds = [];
    devicesInfo.forEach((device) => {
        const devId = device.devId || device.deviceId;
        if (devId) {
            devIds.push(devId);
        }
    });

    const BATCH_SIZE = 200;
    const totalDevices = devIds.length;
    const batchCount = Math.ceil(totalDevices / BATCH_SIZE);

    console.log(`  [INFO] 共 ${totalDevices} 个设备，需分 ${batchCount} 批查询`);

    // 并行执行所有批次查询
    const batchPromises = [];
    for (let i = 0; i < batchCount; i++) {
        const startIndex = i * BATCH_SIZE;
        const endIndex = Math.min(startIndex + BATCH_SIZE, totalDevices);
        const batchDevIds = devIds.slice(startIndex, endIndex);

        batchPromises.push((async (batchIndex, start, end) => {
            console.log(`  [FETCHING] 正在查询第 ${batchIndex + 1}/${batchCount} 批 (${start + 1}-${end} 个设备)...`);

            try {
                const data = await getDeviceServiceSnapshot(batchDevIds);
                console.log(`  [OK] 第 ${batchIndex + 1}/${batchCount} 批查询成功`);
                return data;
            } catch (error) {
                console.log(`  [FAIL] 第 ${batchIndex + 1}/${batchCount} 批查询失败:`, error.message);
                return [];
            }
        })(i, startIndex, endIndex));
    }

    const allResults = await Promise.all(batchPromises);
    console.log(`  [OK] 设备详细信息获取完成`);
    const flattenedResults = allResults.flat();
    return flattenedResults;
}
// 第四步：获取设备消息/告警
async function fetchDeviceMessages() {
    console.log('[4/12] 获取设备消息/告警...');
    try {
        const result = await getDeviceMessages({ lastDays: 1 });
        console.log('  [OK] 获取设备消息成功');
        return result;
    } catch (error) {
        console.log('  [FAIL] 获取设备消息失败:', error.message);
        return null;
    }
}

// 第五步：获取儿童上网保护数据
async function getChildProtectData(devicesInfo) {
    console.log('[5/11] 获取儿童上网保护数据...');

    if (!devicesInfo || !Array.isArray(devicesInfo)) {
        console.log('  [SKIP] 设备信息为空，跳过儿童保护数据获取');
        return null;
    }

    // 过滤路由设备
    const routers = devicesInfo.filter(d =>
        d.category === 'router' ||
        d.productName?.includes('路由') ||
        d.model?.includes('router')
    );

    if (routers.length === 0) {
        console.log('  [SKIP] 未发现路由设备，跳过儿童保护数据获取');
        return null;
    }

    // 注意：router-claw.js 无导出函数，暂无法改造为直接调用
    // 保留 exec 方式，但需要修复代码逻辑
    const childProtectDataPromises = routers.map(async (router, index) => {
        const cmd = `node ${path.join(CONFIG.routerSkillBin, 'router-claw.js')} get_child_protect`;
        try {
            const result = await execCommand(cmd);
            if (result.success) {
                const data = JSON.parse(result.data);
                console.log(`  [OK] 路由 ${index + 1}/${routers.length} 儿童保护数据获取成功`);
                return {
                    routerId: router.devId,
                    data: data
                };
            } else {
                console.log(`  [FAIL] 路由 ${index + 1}/${routers.length} 获取失败: ${result.error}`);
                return null;
            }
        } catch (error) {
            console.log(`  [FAIL] 路由 ${index + 1}/${routers.length} 获取失败:`, error.message);
            return null;
        }
    });

    const childProtectDataResults = await Promise.all(childProtectDataPromises);
    const childProtectData = childProtectDataResults.filter(item => item !== null);
    console.log(`  [OK] 儿童保护数据获取完成`);
    return childProtectData;
}

// 第六步：获取门锁历史记录
async function getLockHistory(devicesInfo) {
    console.log('[6/11] 获取门锁历史记录...');

    if (!devicesInfo || !Array.isArray(devicesInfo)) {
        console.log('  [SKIP] 设备信息为空，跳过门锁历史获取');
        return null;
    }

    // 过滤门锁设备
    const locks = devicesInfo.filter(d =>
        d.category === 'lock' ||
        d.productName?.includes('门锁') ||
        d.model?.includes('lock')
    );

    if (locks.length === 0) {
        console.log('  [SKIP] 未发现门锁设备，跳过门锁历史获取');
        return null;
    }

    // 并行查询所有门锁设备
    const lockHistoryDataPromises = locks.map(async (lock, index) => {
        const devId = lock.devId || lock.deviceId;
        if (!devId) return null;

        try {
            const data = await getDeviceHistories({ devId, sid: 'eventData', date: 'today' });
            console.log(`  [OK] 门锁 ${index + 1}/${locks.length} 历史记录获取成功`);
            return {
                devId: devId,
                data: data
            };
        } catch (error) {
            console.log(`  [FAIL] 门锁 ${index + 1}/${locks.length} 获取失败:`, error.message);
            return null;
        }
    });

    const lockHistoryDataResults = await Promise.all(lockHistoryDataPromises);
    const lockHistoryData = lockHistoryDataResults.filter(item => item !== null);

    console.log(`  [OK] 门锁历史记录获取完成`);
    return lockHistoryData;
}

// 第八步：获取睡眠数据
async function getSleepData() {
    console.log('[8/10] 获取睡眠数据...');
    const cmd = `node ${path.join(CONFIG.commonSkillBin, 'pha-claw.js')} get_sleep --date today`;
    const result = await execCommand(cmd);

    if (result.success) {
        console.log(`  [OK] 睡眠数据获取完成`);
        return JSON.parse(result.data);
    } else {
        console.log('  [FAIL] 获取睡眠数据失败');
        return null;
    }
}
// 第九步：获取活动数据
async function getActivityData() {
    console.log('[9/10] 获取活动数据...');
    const cmd = `node ${path.join(CONFIG.commonSkillBin, 'pha-claw.js')} get_activity_data --date today`;
    const result = await execCommand(cmd);

    if (result.success) {
        console.log(`  [OK] 活动数据获取完成`);
        return JSON.parse(result.data);
    } else {
        console.log('  [FAIL] 获取活动数据失败');
        return null;
    }
}

// 第十步：获取情绪数据
async function getEmotionData() {
    console.log('[10/10] 获取情绪数据...');
    const cmd = `node ${path.join(CONFIG.commonSkillBin, 'pha-claw.js')} get_emotion --date today`;
    const result = await execCommand(cmd);

    if (result.success) {
        console.log(`  [OK] 情绪数据获取完成`);
        return JSON.parse(result.data);
    } else {
        console.log('  [FAIL] 获取情绪数据失败');
        return null;
    }
}
// 主函数
async function main() {
    console.log('========================================');
    console.log('  家庭简报数据收集脚本');
    console.log('========================================\n');

    ensureOutputDir();

    // 解析命令行参数
    const args = process.argv.slice(2);
    let specifiedHomeId = null;
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--home-id' && args[i + 1]) {
            specifiedHomeId = args[i + 1];
            break;
        }
    }

    const startTime = Date.now();

    // 第一阶段：并行获取基础数据（不依赖其他数据）
    console.log('=== 第一阶段：并行获取基础数据 ===');
    const phase1Promise = Promise.all([
        fetchHomesInfo(),
        fetchDevicesInfo(),
        fetchDeviceMessages()
    ]);

    // 第三阶段：并行获取个人健康数据（不依赖其他数据）
    console.log('=== 第三阶段：并行获取个人健康数据 ===');
    const phase3Promise = Promise.all([
        getSleepData(),
        getActivityData(),
        getEmotionData()
    ]);

    // 等待第一阶段完成
    const [homesInfo, devicesInfo, deviceMessages] = await phase1Promise;

    // 第二阶段：并行获取设备相关数据（依赖第一阶段的设备信息）
    console.log('\n=== 第二阶段：并行获取设备相关数据 ===');
    const devices = devicesInfo?.devices || [];
    const [devicesDetail, childProtectData, lockHistory] = await Promise.all([
        fetchDevicesDetail(devices),
        getChildProtectData(devices),
        getLockHistory(devices)
    ]);

    // 等待第三阶段完成
    const [sleepData, activityData, emotionData] = await phase3Promise;

    // 汇总所有数据到单个文件 (00-09)
    const allData = {
        timestamp: new Date().toISOString(),
        '00_summary': {
            homesInfo: homesInfo !== null,
            devicesInfo: devicesInfo !== null,
            devicesDetail: devicesDetail.length > 0,
            deviceMessages: deviceMessages !== null,
            childProtectData: childProtectData !== null,
            lockHistory: lockHistory !== null,
            sleepData: sleepData !== null,
            activityData: activityData !== null,
            emotionData: emotionData !== null
        },
        '01_homes_info': homesInfo,
        '02_devices_info': devicesInfo,
        '03_devices_detail': devicesDetail,
        '04_device_messages': deviceMessages,
        '05_child_protect': childProtectData,
        '06_lock_history': lockHistory,
        '07_sleep_data': sleepData,
        '08_activity_data': activityData,
        '09_emotion_data': emotionData
    };


    const endTime = Date.now();
    const duration = ((endTime - startTime) / 1000).toFixed(2);

    console.log('\n========================================');
    console.log('  数据收集完成');
    console.log('========================================');
    console.log(`[TIME] 总耗时: ${duration}秒`);
    // console.log(`📁 输出目录: ${CONFIG.outputDir}`);
    // console.log(`📊 汇总信息: ${summaryPath}`);
    console.log('\n数据获取统计:');
    const dataSources = allData['00_summary'];
    console.log(`  [OK] 家庭信息: ${dataSources.homesInfo ? '成功' : '失败'}`);
    console.log(`  [OK] 设备基础信息: ${dataSources.devicesInfo ? '成功' : '失败'}`);
    console.log(`  [OK] 设备详细信息: ${dataSources.devicesDetail ? `${devicesDetail.length}个设备` : '失败'}`);
    console.log(`  [OK] 设备消息: ${dataSources.deviceMessages ? '成功' : '失败'}`);
    console.log(`  [OK] 儿童保护: ${childProtectData !== null ? '成功' : '失败/无设备'}`);
    console.log(`  [OK] 门锁历史: ${dataSources.lockHistory ? '成功' : '失败/无设备'}`);
    console.log(`  [OK] 睡眠数据: ${dataSources.sleepData ? '成功' : '失败'}`);
    console.log(`  [OK] 活动数据: ${dataSources.activityData ? '成功' : '失败'}`);
    console.log(`  [OK] 情绪数据: ${dataSources.emotionData ? '成功' : '失败'}`);
    // 流式JSON输出: 一行一个JSON对象
    console.log('--- START JSON OUTPUT ---');

    // 输出汇总信息
    console.log(JSON.stringify({
        type: 'summary',
        timestamp: allData.timestamp,
        dataSources: allData['00_summary']
    }));

    // 输出家庭信息
    if (homesInfo !== null) {
        console.log(JSON.stringify({
            type: 'homes_info',
            data: homesInfo
        }));
    }

    // 输出设备基础信息
    if (devicesInfo !== null) {
        console.log(JSON.stringify({
            type: 'devices_info',
            data: devicesInfo
        }));
    }

    // 输出设备详细信息 - 逐个设备打印
    if (devicesDetail && devicesDetail.length > 0) {
        console.log(JSON.stringify({
            type: 'devices_detail_start',
            total: devicesDetail.length
        }));
        for (const deviceDetail of devicesDetail) {
            console.log(JSON.stringify({
                type: 'device_snapshot',
                data: deviceDetail
            }));
        }
        console.log(JSON.stringify({
            type: 'devices_detail_end',
            total: devicesDetail.length
        }));
    }

    // 输出设备消息
    if (deviceMessages !== null) {
        console.log(JSON.stringify({
            type: 'device_messages',
            data: deviceMessages
        }));
    }

    // 输出儿童保护数据
    if (childProtectData !== null) {
        console.log(JSON.stringify({
            type: 'child_protect',
            data: childProtectData
        }));
    }

    // 输出门锁历史
    if (lockHistory !== null) {
        console.log(JSON.stringify({
            type: 'lock_history',
            data: lockHistory
        }));
    }

    // 输出睡眠数据
    if (sleepData !== null) {
        console.log(JSON.stringify({
            type: 'sleep_data',
            data: sleepData
        }));
    }

    // 输出活动数据
    if (activityData !== null) {
        console.log(JSON.stringify({
            type: 'activity_data',
            data: activityData
        }));
    }

    // 输出情绪数据
    if (emotionData !== null) {
        console.log(JSON.stringify({
            type: 'emotion_data',
            data: emotionData
        }));
    }

    console.log('--- END JSON OUTPUT ---');
    console.log('========================================\n');
}

// 运行
if (import.meta.url === `file://${process.argv[1]}`) {
    main();
}

export {
    fetchHomesInfo,
    fetchDevicesInfo,
    fetchDevicesDetail,
    fetchDeviceMessages,
    getChildProtectData,
    getLockHistory,
    getSleepData,
    getActivityData,
    getEmotionData
};