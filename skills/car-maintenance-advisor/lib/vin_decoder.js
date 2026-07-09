/**
 * VIN 解码模块
 * 纯本地计算，无需API调用
 * 参考标准：ISO 3779 / SAE J853
 */

const VIN_WEIGHTS = [8,7,6,5,4,3,2,10,0,9,8,7,6,5,4,3,2];
const VIN_CHARS = '0123456789X';

// 第1-3位：制造商标识（WMI）
const WMI_MAP = {
  'WAU': 'Audi',
  'WUA': 'Audi',
  'WVW': 'Volkswagen',
  'WVG': 'Volkswagen',
  'WVB': 'Volkswagen',
  'WBA': 'BMW',
  'WBS': 'BMW M',
  'WBY': 'BMW i',
  'WDD': 'Mercedes-Benz',
  'WDB': 'Mercedes-Benz',
  'WDZ': 'Mercedes-Benz',
  'JTH': 'Lexus',
  'JTJ': 'Lexus',
  'JTD': 'Toyota',
  'JTE': 'Toyota',
  'JTM': 'Toyota',
  '1G1': 'Chevrolet',
  '1G6': 'Cadillac',
  'JH4': 'Acura',
  'SHH': 'Honda',
  'JM1': 'Mazda',
  'JN1': 'Nissan',
  'JN8': 'Nissan',
  'KL4': 'Buick',
  'KL7': 'Chevrolet',
};

// 第10位：年款编码
const YEAR_MAP = {
  'L': 2020, 'M': 2021, 'N': 2022, 'P': 2023,
  'R': 2024, 'S': 2025, 'T': 2026, 'V': 2027,
  'W': 1998, 'X': 1999, 'Y': 2000, '1': 2001,
  '2': 2002, '3': 2003, '4': 2004, '5': 2005,
  '6': 2006, '7': 2007, '8': 2008, '9': 2009,
  'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013,
  'E': 2014, 'F': 2015, 'G': 2016, 'H': 2017,
  'J': 2018, 'K': 2019,
};

// 奥迪车型代码（第4-7位，因年代而异，这里给出常见C8 A6的参考）
const AUDI_MODEL_MAP = {
  '4G': 'A6 (C7)',
  '4K': 'A6 (C8)',
  '4A': 'A6 (C8) Avant',
  '8W': 'A4 (B9)',
  '8V': 'A3 (8V)',
  'FV': 'Q5 (FY)',
  '80': 'Q7 (4M)',
  '4M': 'Q7 (4M)',
  'F3': 'Q3 (F3)',
};

/**
 * 验证VIN格式
 */
function validateVIN(vin) {
  if (!vin) return { valid: false, error: 'VIN不能为空' };
  const cleaned = vin.trim().toUpperCase();
  if (cleaned.length !== 17) return { valid: false, error: `VIN长度应为17位，当前为${cleaned.length}位` };
  if (/[IOQ]/.test(cleaned)) return { valid: false, error: 'VIN不能包含字母I、O、Q' };
  return { valid: true, vin: cleaned };
}

/**
 * 计算VIN校验位（第9位）
 */
function calcCheckDigit(vin) {
  const map = { '0':0,'1':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
    'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7,'H':8,
    'J':1,'K':2,'L':3,'M':4,'N':5,'P':7,'R':9,
    'S':2,'T':3,'U':4,'V':5,'W':6,'X':7,'Y':8,'Z':9 };
  let sum = 0;
  for (let i = 0; i < 17; i++) {
    sum += (map[vin[i]] || 0) * VIN_WEIGHTS[i];
  }
  return VIN_CHARS[sum % 11];
}

/**
 * 主解码函数
 */
function decodeVIN(vinInput) {
  const validation = validateVIN(vinInput);
  if (!validation.valid) return validation;

  const vin = validation.vin;
  const wmi = vin.substring(0, 3);
  const brand = WMI_MAP[wmi] || '未知品牌';
  const yearCode = vin[9];
  const year = YEAR_MAP[yearCode] || null;

  // 校验位验证
  const expectedCheck = calcCheckDigit(vin);
  const checkValid = vin[8] === expectedCheck;

  // 尝试识别具体车型
  let modelHint = '';
  if (brand === 'Audi') {
    const modelCode = vin.substring(3, 6);
    modelHint = AUDI_MODEL_MAP[modelCode] || '';
  }

  return {
    valid: true,
    vin,
    wmi,
    brand,
    model_hint: modelHint,
    year_code: yearCode,
    year,
    check_digit_valid: checkValid,
    check_digit_expected: expectedCheck,
    actual_check_digit: vin[8],
    plant_code: vin[10],
    serial_number: vin.substring(11),
    // 用于后续知识库查询的key
    query_key: {
      brand: brand.toLowerCase(),
      year,
    }
  };
}

module.exports = { decodeVIN, validateVIN, calcCheckDigit };
