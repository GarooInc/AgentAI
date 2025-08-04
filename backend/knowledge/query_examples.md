# Query examples
This file contains examples of queries that can be used with the AgentAI system. These queries are designed to test the capabilities of the agents and ensure they can handle various types of requests effectively.

## Identifying three buyer personas
following the question: "Using data from the reservations, identify three distinct buyer personas for Itz'ana Resort. For each persona, provide a the average spending, the average lenght of stay and the preferred room type."

``` sql
WITH base AS (
  SELECT
    ROOM_CATEGORY_LABEL,
    DEPOSIT_PAID               AS deposit_paid,
    date(ARRIVAL)              AS arrival_date,
    date(DEPARTURE)            AS departure_date,
    julianday(date(DEPARTURE))
      - julianday(date(ARRIVAL)) AS nights,
    ADULTS,
    CHILDREN,
    CASE
      WHEN ADULTS = 1 AND CHILDREN = 0 THEN 'Adult Solo'
      WHEN ADULTS = 2 AND CHILDREN = 0 THEN 'Couple'
      WHEN CHILDREN > 0               THEN 'Family'
      ELSE NULL
    END AS buyer_persona
  FROM reservations
),
filtered AS (
  SELECT *
  FROM base
  WHERE buyer_persona IS NOT NULL
    AND nights BETWEEN 1 AND 30
    -- Opcional: filtrar un rango de fechas
    -- AND arrival_date >= '2024-01-01'
    -- AND departure_date <= '2024-12-31'
),
agg AS (
  SELECT
    buyer_persona,
    ROUND(AVG(deposit_paid), 2) AS average_spending,
    ROUND(AVG(nights),       2) AS average_stay_length
  FROM filtered
  GROUP BY buyer_persona
),
room_pref AS (
  SELECT
    buyer_persona,
    TRIM(ROOM_CATEGORY_LABEL) AS preferred_room_type,
    COUNT(*)                 AS cnt,
    ROW_NUMBER() OVER (
      PARTITION BY buyer_persona
      ORDER BY COUNT(*) DESC, TRIM(ROOM_CATEGORY_LABEL)
    ) AS rn
  FROM filtered
  WHERE ROOM_CATEGORY_LABEL IS NOT NULL
    AND TRIM(ROOM_CATEGORY_LABEL) <> ''
  GROUP BY buyer_persona, TRIM(ROOM_CATEGORY_LABEL)
)
SELECT
  a.buyer_persona       AS persona,
  a.average_spending    AS gasto_promedio,
  a.average_stay_length AS estancia_promedio,
  r.preferred_room_type AS habitacion_preferida
FROM agg a
LEFT JOIN room_pref r
  ON r.buyer_persona = a.buyer_persona
 AND r.rn = 1
ORDER BY CASE a.buyer_persona
  WHEN 'Adult Solo' THEN 1
  WHEN 'Couple'     THEN 2
  WHEN 'Family'     THEN 3
  ELSE 4
END;
```

## Getting the global revenue generated from 'Walk-In' reservations
Following the question: "Cual es la venta generada por Walk-In"? 'Walk-In' is a term used to refer to reservations made directly at the hotel without prior booking. In the database, this is represented in the `ORIGIN_OF_BOOKING` column.

``` sql
SELECT SUM(DEPOSIT_PAID) AS total_revenue
    FROM reservations
WHERE ORIGIN_OF_BOOKING = 'Walk‑In';
```

## Getting the total sales by month and room type. 
Following the question: "Cual es la venta total por mes y año?"
``` sql
-- 1. Filtrar reservas válidas y calcular noches
WITH filtered AS (
  SELECT
    CONFIRMATION_NO      AS res_id,
    date(ARRIVAL)        AS arrival,
    date(DEPARTURE)      AS departure,
    ROOM_CATEGORY_LABEL  AS room_type,
    DEPOSIT_PAID         AS deposit_paid,
    CAST(julianday(DEPARTURE) - julianday(ARRIVAL) AS INTEGER) AS nights
  FROM reservations
  WHERE
    GUARANTEE_CODE = 'CHECKED IN'
    AND deposit_paid > 0
    AND ROOM_CATEGORY_LABEL IS NOT NULL
    AND ARRIVAL IS NOT NULL
    AND DEPARTURE IS NOT NULL
    AND (julianday(DEPARTURE) - julianday(ARRIVAL)) >= 1
),

-- 2. Generar una fila por cada noche de la reserva
reservation_days AS (
  SELECT
    res_id,
    arrival,
    departure,
    room_type,
    deposit_paid,
    nights,
    arrival AS night_date
  FROM filtered
  UNION ALL
  SELECT
    rd.res_id,
    rd.arrival,
    rd.departure,
    rd.room_type,
    rd.deposit_paid,
    rd.nights,
    date(rd.night_date, '+1 day') AS night_date
  FROM reservation_days AS rd
  WHERE rd.night_date < date(rd.departure, '-1 day')
)

-- 3. Agregar por año, mes y tipo de cuarto
SELECT
  strftime('%Y', night_date) AS year,
  strftime('%m', night_date) AS month,
  room_type,
  ROUND(
    SUM(deposit_paid * 1.0 / nights),
    2
  ) AS total_revenue
FROM reservation_days
GROUP BY year, month, room_type
ORDER BY year ASC, month ASC, room_type DESC;
```

