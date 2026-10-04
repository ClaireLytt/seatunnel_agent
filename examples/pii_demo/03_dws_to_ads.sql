-- DWS → ADS：银行卡号一路裸奔到报表层（未脱敏跨层扩散的反例）
INSERT OVERWRITE TABLE ads.pay_report
SELECT
  p.user_id,
  p.bank_card_no,
  sum(p.amount) AS pay_amount,
  p.dt
FROM ods.order_pay p
GROUP BY p.user_id, p.bank_card_no, p.dt;
