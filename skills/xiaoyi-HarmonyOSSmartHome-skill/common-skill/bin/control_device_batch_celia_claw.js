import { hagSkillServicePost, generateTraceId, maskSecret } from '../../utils/hag-connect/utils.js';

export async function controlDeviceBatchCeliaClaw(deviceIds, deviceTypeId, productId, sid, data, timeoutForAckMode = 10000, verbose = false) {
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
  if (!deviceTypeId || typeof deviceTypeId !== 'string') {
    const error = {
      success: false,
      error: {
        code: 'INVALID_PARAM',
        message: 'deviceTypeId 不能为空且必须是字符串',
        field: 'deviceTypeId'
      },
      traceId
    };
    return error;
  }
  if (!productId || typeof productId !== 'string') {
    const error = {
      success: false,
      error: {
        code: 'INVALID_PARAM',
        message: 'productId 不能为空且必须是字符串',
        field: 'productId'
      },
      traceId
    };
    return error;
  }
  if (!sid || typeof sid !== 'string') {
    const error = {
      success: false,
      error: {
        code: 'INVALID_PARAM',
        message: 'sid 不能为空且必须是字符串',
        field: 'sid'
      },
      traceId
    };
    return error;
  }
  if (!data) {
    const error = {
      success: false,
      error: {
        code: 'INVALID_PARAM',
        message: 'data 不能为空',
        field: 'data'
      },
      traceId
    };
    return error;
  }

  if (verbose) console.info('[verbose] 开始批量控制设备');
  if (verbose) console.info(`[verbose] 设备数量: ${deviceIds.length}, 设备类型: ${deviceTypeId}, 产品ID: ${productId}, 服务: ${sid}`);

  const mode = 'ACK';
  const requestId = traceId;
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  const timestamp = `${year}${month}${day}T${hours}${minutes}${seconds}Z`;

  let parsedData;
  if (typeof data === 'string') {
    try {
      parsedData = JSON.parse(data);
    } catch (err) {
      const error = {
        success: false,
        error: {
          code: 'INVALID_JSON',
          message: 'data 解析失败，请传入有效的 JSON 字符串',
          field: 'data'
        },
        traceId
      };
      return error;
    }
  } else if (typeof data === 'object') {
    parsedData = data;
  } else {
    const error = {
      success: false,
      error: {
        code: 'INVALID_PARAM',
        message: 'data 必须是 JSON 字符串或对象',
        field: 'data'
      },
      traceId
    };
    return error;
  }

  const body = {
    mode,
    requestId,
    timestamp,
    deviceIds,
    deviceTypeId,
    productId,
    timeoutForAckMode,
    sid,
    operation: 'POST',
    data: parsedData
  };

  if (verbose) console.info('[verbose] 请求体:', JSON.stringify({ ...body, deviceIds: body.deviceIds.map(maskSecret) }, null, 2));

  let response;
  try {
    response = await hagSkillServicePost('batchDevCommand', body, verbose);
  } catch (error) {
    const errorResult = {
      success: false,
      error: {
        code: 'BATCH_CONTROL_FAILED',
        message: `批量控制设备失败: ${error.message}`,
        detail: error.name
      },
      traceId
    };
    return errorResult;
  }

  if (verbose) console.info('[verbose] 批量控制响应: [已隐藏，如需查看请取消注释上一行]');

  return {
    success: true,
    data: {
      requestId,
      timestamp,
      traceId,
      totalDevices: deviceIds.length,
      deviceTypeId,
      productId,
      sid,
      response
    }
  };
}