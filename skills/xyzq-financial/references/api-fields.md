# 接口返回数据字段释义

## 2. 查询公司公告

返回的data为公告列表，数组格式，字段如下：

| 字段名          | 类型  | 说明   |
| ------------ | --- | ---- |
| `titl`       | 字符串 | 公告标题 |
| `infoTypeCd` | 字符串 | 公告类型 |
| `ntcDt`      | 字符串 | 公告日期 |
| `linkAddr`   | 字符串 | 链接地址 |
| `exchCd`     | 字符串 | 交易所  |
| `secuCd`     | 字符串 | 证券代码 |
| `secuAbbr`   | 字符串 | 证券简称 |

## 3. 查询公司利润表

返回的data为利润列表，数组格式，字段如下：

| 字段名                | 类型  | 说明        |
| ------------------ | --- | --------- |
| `secuCd`           | 字符串 | 证券代码      |
| `secuAbbr`         | 字符串 | 证券简称      |
| `corpCnName`       | 字符串 | 公司中文名称    |
| `name`             | 字符串 | 报告名       |
| `bizTotalNcm`      | 数字  | 营业总收入     |
| `bizNcm`           | 数字  | 营业收入      |
| `bizTotalCost`     | 数字  | 营业总成本     |
| `bizCost`          | 数字  | 营业成本      |
| `bizTaxAndAdt`     | 数字  | 营业税金及附加   |
| `saleExp`          | 数字  | 销售费用      |
| `mngExp`           | 数字  | 管理费用      |
| `finExp`           | 数字  | 财务费用      |
| `bizProf`          | 数字  | 营业利润      |
| `profGamt`         | 数字  | 利润总额      |
| `netProf`          | 数字  | 净利润       |
| `pcoHolderNetProf` | 数字  | 母公司股东净利润  |
| `beps`             | 数字  | 基本每股收益    |
| `intNetNcm`        | 数字  | 利息净收入     |
| `chagAndCmsNetNcm` | 数字  | 手续费及佣金净收入 |
| `insmPrft`         | 数字  | 投资收益      |
| `fairValChgPrft`   | 数字  | 公允价值变动收益  |
| `exchgPrft`        | 数字  | 汇兑收益      |
| `othBkNcm`         | 数字  | 其他业务收入    |
| `alrdErnPrem`      | 数字  | 已赚保费      |

## 4. 查询公司负债表

返回的data为负债列表，数组格式，字段如下：

| 字段名                     | 类型  | 说明            |
| ----------------------- | --- | ------------- |
| `secuCd`                | 字符串 | 证券代码          |
| `secuAbbr`              | 字符串 | 证券简称          |
| `name`                  | 字符串 | 报告名           |
| `liabRate`              | 字符串 | 资产负债率 总负债/总资产 |
| `crrcFund`              | 数字  | 货币资金          |
| `recvBill`              | 数字  | 应收票据          |
| `recvAccNamt`           | 数字  | 应收账款净额        |
| `prePayItm`             | 数字  | 预付款项          |
| `buyRsaleFinAst`        | 数字  | 买入返售金融资产      |
| `invt`                  | 数字  | 存货            |
| `flowAstTot`            | 数字  | 流动资产合计        |
| `allocLoan`             | 数字  | 发放贷款          |
| `avlSellFinAst`         | 数字  | 可供出售金融资产      |
| `hldExprInsm`           | 数字  | 持有到期投资        |
| `ltRecvMny`             | 数字  | 长期应收款         |
| `ltStorInsm`            | 数字  | 长期股权投资        |
| `fixAst`                | 数字  | 固定资产          |
| `intnAst`               | 数字  | 无形资产          |
| `gdwl`                  | 数字  | 商誉            |
| `noFlowAstTot`          | 数字  | 非流动资产合计       |
| `astTot`                | 数字  | 总资产           |
| `stBrow`                | 数字  | 短期借款          |
| `pyabStfSlry`           | 数字  | 应付职工薪酬        |
| `pyabTaxFee`            | 数字  | 应付税费          |
| `flowLiabTot`           | 数字  | 流动负债合计        |
| `ltBrow`                | 数字  | 长期借款          |
| `pyabBond`              | 数字  | 应付债券          |
| `defrIctLiab`           | 数字  | 递延所得税负债       |
| `noFlowLiabTot`         | 数字  | 非流动负债合计       |
| `liabTot`               | 数字  | 负债合计          |
| `paidCap`               | 数字  | 实收资本          |
| `capRsv`                | 数字  | 资本公积          |
| `surpRsv`               | 数字  | 盈余公积          |
| `noAssnProf`            | 数字  | 未分配利润         |
| `pcoHolderEqyTot`       | 数字  | 母公司股东权益合计     |
| `fewHolderEqy`          | 数字  | 少数股东权益        |
| `eqyOrHolderEqyTot`     | 数字  | 所有者权益         |
| `cashAndDepinCbkMnyItm` | 数字  | 现金及存入中央银行款项   |

## 5. 查询公司现金流量表

返回的data为现金流量表，数组格式，字段如下：

| 字段名                        | 类型  | 说明                       |
| -------------------------- | --- | ------------------------ |
| `secuCd`                   | 字符串 | 证券代码                     |
| `secuAbbr`                 | 字符串 | 证券简称                     |
| `corpCnName`               | 字符串 | 公司中文名称                   |
| `name`                     | 字符串 | 报告名                      |
| `saleMercPrvdLsRcvOfCash`  | 数字  | 销售商品提供劳务收到的现金            |
| `oprtActCashInflSttl`      | 数字  | 经营活动现金流入小计               |
| `purcMercGetLsPayCash`     | 数字  | 购买商品接受劳务支付现金             |
| `payStfAndForStfPayCash`   | 数字  | 支付职工以及为职工支付现金            |
| `payTaxFee`                | 数字  | 支付税费                     |
| `oprtActCfOutSttl`         | 数字  | 经营活动现金流出小计               |
| `oprtActProdOfCfQtyNamt`   | 数字  | 经营活动产生的现金流量净额            |
| `rcvInsmRcvOfCash`         | 数字  | 收回投资收到的现金                |
| `obtnInsmPrftRcvOfCash`    | 数字  | 取得投资收益收到的现金              |
| `dfarcn`                   | 数字  | 处置固定资产无形资产和其他长期资产收回的现金净额 |
| `insmActCashInflSttl`      | 数字  | 投资活动现金流入小计               |
| `fapc`                     | 数字  | 购建固定资产无形资产和其他长期资产支付现金    |
| `insmPayOfCash`            | 数字  | 投资支付的现金                  |
| `insmActCfOutSttl`         | 数字  | 投资活动现金流出小计               |
| `insmActProdOfCfQtyNamt`   | 数字  | 投资活动产生的现金流量净额            |
| `acptInsmRcvOfCash`        | 数字  | 吸收投资收到的现金                |
| `obtBrowRcvOfCash`         | 数字  | 取得借款收到的现金                |
| `fingActCashInflSttl`      | 数字  | 筹资活动现金流入小计               |
| `repyDebtPayOfCash`        | 数字  | 偿还债务支付的现金                |
| `assnDvdProfPayIntPayCash` | 数字  | 分配股利利润偿付利息支付现金           |
| `fingActCfOutSttl`         | 数字  | 筹资活动现金流出小计               |
| `fingActProdOfCfQtyNamt`   | 数字  | 筹资活动产生的现金流量净额            |
| `cashAndCequNetAddAmt`     | 数字  | 现金及现金等价物净增加额             |
| `epCashAndCequBal`         | 数字  | 期末现金及现金等价物余额             |
| `agtBuseSecuRcvCashNamt`   | 数字  | 代理买卖证券收到现金净额             |
| `custDpsiIbkSavMnyNetAdd`  | 数字  | 客户存款同业存放款净增加             |
| `payChagAndCmsOfCash`      | 数字  | 支付手续费及佣金的现金              |

## 6. 查询公司财报

返回的data为财报表，数组格式，字段如下：

| 字段名                      | 类型  | 说明            |
| ------------------------ | --- | ------------- |
| `secuCd`                 | 字符串 | 证券代码          |
| `secuAbbr`               | 字符串 | 证券简称          |
| `endTime`                | 长整数 | 截止时间          |
| `corpCnName`             | 字符串 | 公司中文名称        |
| `name`                   | 字符串 | 报告名           |
| `netProf`                | 数字  | 净利润           |
| `bizNcm`                 | 数字  | 营业收入          |
| `astTot`                 | 数字  | 总资产           |
| `eqyOrHolderEqyTot`      | 数字  | 所有者权益         |
| `liabRate`               | 字符串 | 资产负债率 总负债/总资产 |
| `oprtActProdOfCfQtyNamt` | 数字  | 经营活动现金流净额     |

## 7. 查询历史行情

返回的data包含行情概览（overview）与行情数据列表（detailList）。

行情概览（overview）：

| 字段名              | 类型  | 说明       |
| ---------------- | --- | -------- |
| `secuCd`         | 字符串 | 证券代码     |
| `secuAbbr`       | 字符串 | 证券简称     |
| `startPrice`     | 数字  | 期初收盘价前复权 |
| `startDate`      | 字符串 | 期初日期     |
| `endPrice`       | 数字  | 最新收盘价前复权 |
| `endDate`        | 字符串 | 最新日期     |
| `periodMaxPrc`   | 数字  | 区间最高价前复权 |
| `periodMinPrc`   | 数字  | 区间最低价前复权 |
| `periodMaxDate`  | 字符串 | 区间最高日期   |
| `periodMinDate`  | 字符串 | 区间最低日期   |
| `maxMtchAmt`     | 数字  | 最大成交额    |
| `maxMtchAmtDate` | 字符串 | 最大成交额日期  |
| `periodRfr`      | 字符串 | 区间涨跌幅    |

行情数据列表（detailList）数组格式，字段如下：

| 字段名        | 类型  | 说明     |
| ---------- | --- | ------ |
| `secuCd`   | 字符串 | 证券代码   |
| `secuAbbr` | 字符串 | 证券简称   |
| `transDt`  | 字符串 | 交易日期   |
| `oprc`     | 数字  | 开盘价前复权 |
| `hprc`     | 数字  | 最高价前复权 |
| `lprc`     | 数字  | 最低价前复权 |
| `cprc`     | 数字  | 今收盘前复权 |
| `mtchAmt`  | 数字  | 成交额    |
| `dayRfr`   | 数字  | 日涨跌幅   |
