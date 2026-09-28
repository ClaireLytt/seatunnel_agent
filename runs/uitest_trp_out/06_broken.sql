-- transpile-error: Expected table name but got WHERE. Line 2, Col: 27.
-- Intentionally broken: parse error must not abort the batch
SELECT order_id, FROM WHERE dt = ;
