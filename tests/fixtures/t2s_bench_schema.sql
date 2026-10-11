-- Retrieval benchmark schema: 40 tables across 8 domains.
-- Used by `seatunnel-agent t2s-bench` and tests/test_text2sql_retrieval.py.

-- ── 交易域 ──────────────────────────────────────────────
CREATE TABLE dwd.dwd_trade_order_di(
  order_id string COMMENT '订单编号',
  user_id string COMMENT '用户ID',
  pay_amount decimal(18,2) COMMENT '实付金额',
  order_status string COMMENT '订单状态',
  channel string COMMENT '下单渠道'
) COMMENT '交易订单明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_trade_refund_di(
  refund_id string COMMENT '退款单号',
  order_id string COMMENT '原订单编号',
  refund_amount decimal(18,2) COMMENT '退款金额',
  refund_reason string COMMENT '退款原因'
) COMMENT '退款明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_trade_gmv_channel_df(
  channel string COMMENT '渠道',
  gmv decimal(18,2) COMMENT '成交总额',
  order_cnt bigint COMMENT '订单数'
) COMMENT '分渠道GMV汇总表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dim.dim_trade_shop_df(
  shop_id string COMMENT '店铺ID',
  shop_name string COMMENT '店铺名称',
  merchant_id string COMMENT '商家ID',
  open_date string COMMENT '开店日期'
) COMMENT '店铺维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_trade_pay_flow_di(
  flow_id string COMMENT '流水号',
  order_id string COMMENT '订单编号',
  pay_type string COMMENT '支付方式',
  pay_amount decimal(18,2) COMMENT '支付金额'
) COMMENT '支付流水明细表' PARTITIONED BY (dt string COMMENT '分区日期');

-- ── 用户域 ──────────────────────────────────────────────
CREATE TABLE dim.dim_user_profile_df(
  user_id string COMMENT '用户ID',
  gender string COMMENT '性别',
  age_level string COMMENT '年龄段',
  city string COMMENT '常住城市',
  member_level string COMMENT '会员等级'
) COMMENT '用户画像维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_user_register_di(
  user_id string COMMENT '用户ID',
  register_channel string COMMENT '注册渠道',
  device_type string COMMENT '设备类型'
) COMMENT '用户注册明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_user_login_di(
  user_id string COMMENT '用户ID',
  login_time string COMMENT '登录时间',
  login_ip string COMMENT '登录IP'
) COMMENT '用户登录日志表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_user_retention_df(
  register_date string COMMENT '注册日期',
  day1_retention double COMMENT '次日留存率',
  day7_retention double COMMENT '7日留存率',
  day30_retention double COMMENT '30日留存率'
) COMMENT '用户留存汇总表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_user_address_df(
  address_id string COMMENT '地址ID',
  user_id string COMMENT '用户ID',
  province string COMMENT '省份',
  city string COMMENT '城市',
  detail string COMMENT '详细地址'
) COMMENT '用户收货地址表' PARTITIONED BY (dt string COMMENT '分区日期');

-- ── 商品域 ──────────────────────────────────────────────
CREATE TABLE dim.dim_item_sku_df(
  sku_id string COMMENT 'SKU编号',
  item_name string COMMENT '商品名称',
  category_id string COMMENT '类目ID',
  brand string COMMENT '品牌',
  price decimal(10,2) COMMENT '售价'
) COMMENT '商品SKU维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dim.dim_item_category_df(
  category_id string COMMENT '类目ID',
  category_name string COMMENT '类目名称',
  parent_id string COMMENT '父类目ID',
  level int COMMENT '类目层级'
) COMMENT '商品类目维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_item_price_change_di(
  sku_id string COMMENT 'SKU编号',
  old_price decimal(10,2) COMMENT '原价',
  new_price decimal(10,2) COMMENT '新价',
  change_reason string COMMENT '调价原因'
) COMMENT '商品调价记录表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_item_sale_rank_df(
  sku_id string COMMENT 'SKU编号',
  sale_cnt bigint COMMENT '销量',
  sale_amount decimal(18,2) COMMENT '销售额',
  rank_num int COMMENT '销量排名'
) COMMENT '商品销量排行榜' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_item_comment_di(
  comment_id string COMMENT '评价ID',
  sku_id string COMMENT 'SKU编号',
  user_id string COMMENT '用户ID',
  star int COMMENT '评分星级',
  content string COMMENT '评价内容'
) COMMENT '商品评价明细表' PARTITIONED BY (dt string COMMENT '分区日期');

-- ── 物流域 ──────────────────────────────────────────────
CREATE TABLE dwd.dwd_lgt_ship_order_di(
  ship_id string COMMENT '发货单号',
  order_id string COMMENT '订单编号',
  warehouse_id string COMMENT '发货仓库ID',
  carrier string COMMENT '承运商'
) COMMENT '发货单明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_lgt_delivery_di(
  delivery_id string COMMENT '配送单号',
  ship_id string COMMENT '发货单号',
  courier string COMMENT '配送员',
  sign_time string COMMENT '签收时间'
) COMMENT '配送签收明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dim.dim_lgt_warehouse_df(
  warehouse_id string COMMENT '仓库ID',
  warehouse_name string COMMENT '仓库名称',
  province string COMMENT '所在省份',
  capacity bigint COMMENT '库容'
) COMMENT '仓库维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_lgt_timeliness_df(
  warehouse_id string COMMENT '仓库ID',
  avg_ship_hours double COMMENT '平均发货时长小时',
  avg_delivery_hours double COMMENT '平均配送时长小时',
  ontime_rate double COMMENT '准时率'
) COMMENT '物流时效汇总表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_lgt_inbound_di(
  inbound_id string COMMENT '入库单号',
  warehouse_id string COMMENT '仓库ID',
  sku_id string COMMENT 'SKU编号',
  inbound_cnt bigint COMMENT '入库数量'
) COMMENT '入库明细表' PARTITIONED BY (dt string COMMENT '分区日期');

-- ── 营销域 ──────────────────────────────────────────────
CREATE TABLE dwd.dwd_mkt_coupon_use_di(
  coupon_id string COMMENT '优惠券ID',
  user_id string COMMENT '用户ID',
  order_id string COMMENT '核销订单号',
  discount_amount decimal(10,2) COMMENT '优惠金额'
) COMMENT '优惠券核销明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dim.dim_mkt_campaign_df(
  campaign_id string COMMENT '活动ID',
  campaign_name string COMMENT '活动名称',
  start_date string COMMENT '开始日期',
  end_date string COMMENT '结束日期',
  budget decimal(18,2) COMMENT '活动预算'
) COMMENT '营销活动维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_mkt_ad_click_di(
  click_id string COMMENT '点击ID',
  ad_id string COMMENT '广告ID',
  user_id string COMMENT '用户ID',
  cost decimal(10,4) COMMENT '点击花费'
) COMMENT '广告点击明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_mkt_roi_df(
  campaign_id string COMMENT '活动ID',
  spend decimal(18,2) COMMENT '投放花费',
  revenue decimal(18,2) COMMENT '带来收入',
  roi double COMMENT '投资回报率'
) COMMENT '营销ROI汇总表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_mkt_push_di(
  push_id string COMMENT '推送ID',
  user_id string COMMENT '用户ID',
  title string COMMENT '推送标题',
  is_clicked int COMMENT '是否点击'
) COMMENT '消息推送明细表' PARTITIONED BY (dt string COMMENT '分区日期');

-- ── 财务域 ──────────────────────────────────────────────
CREATE TABLE dwd.dwd_fin_settle_di(
  settle_id string COMMENT '结算单号',
  merchant_id string COMMENT '商家ID',
  settle_amount decimal(18,2) COMMENT '结算金额',
  fee decimal(18,2) COMMENT '手续费'
) COMMENT '商家结算明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_fin_revenue_df(
  biz_line string COMMENT '业务线',
  revenue decimal(18,2) COMMENT '营业收入',
  profit decimal(18,2) COMMENT '利润'
) COMMENT '财务营收汇总表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_fin_invoice_di(
  invoice_id string COMMENT '发票号',
  order_id string COMMENT '订单编号',
  invoice_amount decimal(18,2) COMMENT '开票金额',
  invoice_type string COMMENT '发票类型'
) COMMENT '发票开具明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dim.dim_fin_account_df(
  account_id string COMMENT '科目ID',
  account_name string COMMENT '会计科目名称',
  account_type string COMMENT '科目类型'
) COMMENT '会计科目维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_fin_cost_di(
  cost_id string COMMENT '成本记录ID',
  cost_type string COMMENT '成本类型',
  cost_amount decimal(18,2) COMMENT '成本金额',
  dept string COMMENT '归属部门'
) COMMENT '成本支出明细表' PARTITIONED BY (dt string COMMENT '分区日期');

-- ── 客服域 ──────────────────────────────────────────────
CREATE TABLE dwd.dwd_cs_ticket_di(
  ticket_id string COMMENT '工单编号',
  user_id string COMMENT '用户ID',
  issue_type string COMMENT '问题类型',
  status string COMMENT '工单状态'
) COMMENT '客服工单明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_cs_chat_di(
  chat_id string COMMENT '会话ID',
  user_id string COMMENT '用户ID',
  agent_id string COMMENT '客服坐席ID',
  duration_sec int COMMENT '会话时长秒'
) COMMENT '在线客服会话表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_cs_satisfaction_df(
  agent_id string COMMENT '客服坐席ID',
  ticket_cnt bigint COMMENT '处理工单数',
  satisfaction double COMMENT '满意度评分'
) COMMENT '客服满意度汇总表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dim.dim_cs_agent_df(
  agent_id string COMMENT '坐席ID',
  agent_name string COMMENT '坐席姓名',
  team string COMMENT '所属小组',
  hire_date string COMMENT '入职日期'
) COMMENT '客服坐席维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_cs_call_di(
  call_id string COMMENT '通话ID',
  user_id string COMMENT '用户ID',
  agent_id string COMMENT '坐席ID',
  call_duration int COMMENT '通话时长秒'
) COMMENT '客服电话通话明细表' PARTITIONED BY (dt string COMMENT '分区日期');

-- ── 流量域 ──────────────────────────────────────────────
CREATE TABLE dwd.dwd_tfc_page_view_di(
  pv_id string COMMENT '浏览ID',
  user_id string COMMENT '用户ID',
  page_url string COMMENT '页面地址',
  stay_seconds int COMMENT '停留时长秒'
) COMMENT '页面浏览明细表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dwd.dwd_tfc_app_event_di(
  event_id string COMMENT '事件ID',
  user_id string COMMENT '用户ID',
  event_name string COMMENT '埋点事件名',
  event_params string COMMENT '事件参数JSON'
) COMMENT 'APP埋点事件表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_tfc_dau_df(
  app_version string COMMENT 'APP版本',
  dau bigint COMMENT '日活跃用户数',
  new_user_cnt bigint COMMENT '新增用户数'
) COMMENT '日活跃用户汇总表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dim.dim_tfc_channel_df(
  channel_id string COMMENT '渠道ID',
  channel_name string COMMENT '渠道名称',
  channel_type string COMMENT '渠道类型'
) COMMENT '流量渠道维表' PARTITIONED BY (dt string COMMENT '分区日期');

CREATE TABLE dws.dws_tfc_funnel_df(
  funnel_step string COMMENT '漏斗步骤',
  uv bigint COMMENT '访问人数',
  conversion_rate double COMMENT '转化率'
) COMMENT '转化漏斗汇总表' PARTITIONED BY (dt string COMMENT '分区日期');
