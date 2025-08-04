# Query examples
This file contains examples of queries that can be used with the AgentAI system. These queries are designed to test the capabilities of the agents and ensure they can handle various types of requests effectively.

## Identifying three buyer personas
following the question: "Using data from the reservations, identify three distinct buyer personas for Itz'ana Resort. For each persona, provide a the average spending, the average lenght of stay and the preferred room type."

``` sql
WITH base AS (
  SELECT
    ROOM_CATEGORY_LABEL,
    EFFECTIVE_RATE_AMOUNT,
    date(ARRIVAL)    AS arrival_date,
    date(DEPARTURE)  AS departure_date,
    julianday(date(DEPARTURE)) - julianday(date(ARRIVAL)) AS nights,
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
    ROUND(AVG(EFFECTIVE_RATE_AMOUNT), 2) AS average_spending,
    ROUND(AVG(nights), 2)                AS average_stay_length
  FROM filtered
  GROUP BY buyer_persona
),
room_pref AS (
  SELECT
    buyer_persona,
    TRIM(ROOM_CATEGORY_LABEL) AS preferred_room_type,
    COUNT(*) AS cnt,
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

## Gettinng the global revenue generated from 'Walk-In' reservations
Following the question: "Cual es la venta generada por Walk-In"?

'Walk-In' is a term used to refer to reservations made directly at the hotel without prior booking. In the database, this is represented in the `ORIGIN_OF_BOOKING` column.

``` sql
SELECT SUM(EFFECTIVE_RATE_AMOUNT)
    FROM reservations
WHERE ORIGIN_OF_BOOKING = 'Walk‑In';
```
