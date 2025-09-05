-- Consulta 1: Venta en unidades por semana
SELECT DATE_TRUNC('week', daily) AS semana, SUM(quantity) AS unidades
FROM sellout
GROUP BY semana
ORDER BY semana;

-- Consulta 2: Top-5 productos por venta en unidades
SELECT p.product_name, SUM(s.quantity) AS unidades
FROM sellout s
JOIN products p ON s.product_id = p.product_id
GROUP BY p.product_name
ORDER BY unidades DESC
LIMIT 5;

-- Consulta 3: Top-5 cadenas/tiendas por venta en unidades
SELECT c.chain_name, st.store_name, SUM(s.quantity) AS unidades
FROM sellout s
JOIN stores st ON s.store_id = st.store_id
JOIN chains c ON st.chain_id = c.chain_id
GROUP BY c.chain_name, st.store_name
ORDER BY unidades DESC
LIMIT 5;

-- Consulta 4: Estacionalidad por cadena (mejor/peor día)
SELECT c.chain_name,
       TO_CHAR(daily, 'Day') AS dia_semana,
       SUM(s.quantity) AS unidades
FROM sellout s
JOIN stores st ON s.store_id = st.store_id
JOIN chains c ON st.chain_id = c.chain_id
GROUP BY c.chain_name, dia_semana
ORDER BY c.chain_name, unidades DESC;
