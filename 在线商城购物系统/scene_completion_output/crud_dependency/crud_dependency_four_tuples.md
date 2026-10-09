# CRUD 数据依赖四元组

- UCG-001-UC001，数据依赖于，UCG-004-UC001，依赖缘由：R（Product）依赖于C（Product）
- UCG-001-UC002，数据依赖于，UCG-004-UC001，依赖缘由：R（Product）依赖于C（Product）
- UCG-001-UC003，数据依赖于，UCG-004-UC001，依赖缘由：R（Product）依赖于C（Product）
- UCG-002-UC001，数据依赖于，UCG-001-UC003，依赖缘由：R（Cart）依赖于C（Cart）
- UCG-002-UC001，数据依赖于，UCG-004-UC001，依赖缘由：R（Product）依赖于C（Product）
- UCG-002-UC002，数据依赖于，UCG-002-UC001，依赖缘由：U（Order）依赖于C（Order）
- UCG-002-UC003，数据依赖于，UCG-002-UC001，依赖缘由：R（Order）依赖于C（Order）
- UCG-003-UC001，数据依赖于，UCG-002-UC001，依赖缘由：U（Order）依赖于C（Order）
- UCG-003-UC002，数据依赖于，UCG-003-UC001，依赖缘由：U（Shipment）依赖于C（Shipment）
- UCG-003-UC003，数据依赖于，UCG-003-UC001，依赖缘由：R（Shipment）依赖于C（Shipment）
- UCG-003-UC003，数据依赖于，UCG-003-UC002，依赖缘由：R（LogisticsEvent）依赖于C（LogisticsEvent）
- UCG-003-UC004，数据依赖于，UCG-002-UC001，依赖缘由：R（Order）依赖于C（Order）
- UCG-004-UC002，数据依赖于，UCG-004-UC001，依赖缘由：U（Product）依赖于C（Product）
- UCG-004-UC004，数据依赖于，UCG-004-UC001，依赖缘由：U（Product）依赖于C（Product）
