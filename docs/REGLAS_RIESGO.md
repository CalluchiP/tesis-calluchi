# Reglas de riesgo tributario (para validar con un contador)

Estas reglas generan las etiquetas del dataset sintético (`ml/generar_dataset.py`) y las alertas del sistema
(`app/services/alertas.py`). **Antes de la defensa, un contador debe revisarlas y firmar su validación** (juicio de experto):
es lo que sustenta que el modelo aprende criterios reales y no inventados.

Datos de un caso (12 meses): régimen, rubro, antigüedad, ventas según comprobantes emitidos, ventas y compras declaradas
(PDT 621), compras a proveedores de riesgo, gastos no deducibles, meses declarados fuera de plazo, multas previas, meses con saldo a favor.

| Señal | Cómo se calcula | Puntos máx. | Alerta media / alta |
|---|---|---|---|
| Brecha ventas | (comprobantes − declaradas) / comprobantes | 30 (se llena en 25 %) | > 5 % / > 15 % |
| Compras a proveedores de riesgo (no habido, baja, sospechoso) | riesgo / compras declaradas | 20 (30 %) | > 5 % / > 15 % |
| Margen bajo vs. rubro | margen − referencia del rubro | 10 (−25 pp) | < −10 pp / < −20 pp |
| Gastos no deducibles | gnd / ventas | 10 (8 %) | > 3 % / > 6 % |
| Meses fuera de plazo | meses / 12 | 10 | ≥ 3 / ≥ 6 |
| Multas previas | cantidad | 10 (3 o más) | ≥ 1 / ≥ 3 |
| Meses con saldo a favor | meses / 12 | 5 (50 %) | ≥ 6 |
| Empresa nueva (< 1 año) | — | 3 | informativa |
| Interacción: brecha > 10 % y proveedores de riesgo > 10 % | — | +5 | — |

Se suma ruido N(0, 4) para simular el criterio subjetivo del evaluador.
**Nivel:** puntaje < 25 = Bajo · 25–50 = Medio · ≥ 50 = Alto.

Margen bruto de referencia por rubro (SUPUESTO a sustentar con estadísticas sectoriales): comercio 22 %, servicios 45 %, manufactura 30 %, construcción 25 %.
