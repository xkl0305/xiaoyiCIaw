import { hagSkillServicePost, generateTraceId, maskSecret } from '../../utils/hag-connect/utils.js';

export async function getDeviceSnapshotBatchCeliaClaw(deviceIds, verbose = false) {
  const traceId = generateTraceId();
  process.stderr.write(`[trace-id] ${traceId}\n`);

  // 入参校验
  if (!Array.isArray(deviceIds) || deviceIds.length === 0) {
    const error = {
      success: false,
      error: {
        code: 'INVALID_PARAM',
        message: 'deviceIds 不能为空且必须是数组（至少1个）',
        field: 'deviceIds'
      },
      traceId
    };
    return error;
  }

  if (verbose) console.info('[verbose] 开始批量获取设备快照');
  if (verbose) console.info(`[verbose] 设备数量: ${deviceIds.length}`);

  // 批量快照接口 payload 仅含一个字段 deviceIds（数组，取 devId）
  const body = {
    deviceIds
  };

  if (verbose) console.info('[verbose] 请求体:', JSON.stringify({ ...body, deviceIds: body.deviceIds.map(maskSecret) }, null, 2));

  let response;
  try {
    response = await hagSkillServicePost('batchGetDevSnapshot', body, verbose);
  } catch (error) {
    const errorResult = {
      success: false,
      error: {
        code: 'BATCH_GET_DETAIL_FAILED',
        message: `批量获取设备快照失败: ${error.message}`,
        detail: error.name
      },
      traceId
    };
    return errorResult;
  }

  if (verbose) console.info('[verbose] 批量快照响应: [已隐藏，如需查看请取消注释上一行]');

  return {
    success: true,
    data: {
      traceId,
      totalDevices: deviceIds.length,
      response
    }
  };
}