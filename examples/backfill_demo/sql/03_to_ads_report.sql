-- DWS -> ADS: 销售大盘
INSERT OVERWRITE TABLE ads.sales_report
SELECT item_name, sum(amount) AS gmv
FROM dws.sales
GROUP BY item_name;
