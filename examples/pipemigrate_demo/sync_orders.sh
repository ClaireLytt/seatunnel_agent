#!/bin/bash
# nightly order sync from mysql to the warehouse
sqoop import --connect jdbc:mysql://db/shop --table orders \
  --target-dir /warehouse/ods/orders --num-mappers 4
