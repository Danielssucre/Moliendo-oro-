# 🏗️ Reporte de Arquitectura Técnica: Polimata v2.0
**Enfoque**: Evaluación de Activos de Software para Inversión/Compra

## 1. Topología del Sistema
El bot no es un script lineal, sino una **Arquitectura de Micro-Módulos** coordinada por un Orquestador Central. Esto permite cambiar la estrategia sin romper el sistema de riesgo.

### Capas de la Cebolla (Cebolla de Protección):
1. **Núcleo de Inteligencia (ML Engine)**:
   - `StopHuntModel`: Detecta manipulación de mercado ("stop hunting") antes de entrar.
   - `RLTrailingManager`: Algoritmo de Aprendizaje por Refuerzo (Reinforcement Learning) para mover el SL de forma inteligente.
   - `AsymmetricRiskOracle`: Ajusta el tamaño de la posición basado en la probabilidad de éxito.
2. **Capa Estratégica**:
   - `SkypieEnel`: Motor de sniping de tendencias.
   - `Polimata Master RL`: Modelo DQN (Deep Q-Network) que adapta el bot a diferentes regímenes de mercado.
3. **Capa de Ejecución y Conectividad**:
   - Abstracción Multi-Broker: Funciona en paralelo con Axi (MT5) y Binance (Crypto).
4. **Capa de Seguridad (Guardian Layer)**:
   - **Basket Lock Theory**: Lógica colectiva que ignora el ruido de pares individuales para ganar en equipo.
   - **Small-Cap Shield**: Algoritmo de filtrado automático de activos de alto riesgo para proteger el margen.

---

## 2. Inventario de Propiedad Intelectual (IP)
A nivel de código, los activos más valiosos ("The Secret Sauce") son:

- **Orquestador De Alistamiento**: Gestiona el "Pulse" del mercado y solo permite operar cuando hay alineación entre el Guardian y los modelos ML.
- **Shadow Grid Tracking**: El bot corre una "grilla fantasma" interna para probar variantes antes de ejecutarlas en real, optimizando el aprendizaje sin arriesgar capital.
- **Lógica de Anti-Fuga (Trailing Basket)**: Recién implementada para asegurar que el capital crezca de forma escalonada, eliminando el riesgo de "reversión total".

---

## 3. Escalabilidad Técnica
La arquitectura de **Clases Desacopladas** (`RealGridManager`, `MarketGuardian`, `TelegramBot`) permite:
- **Hot-Swapping**: Cambiar de Binance a Kraken o de Axi a IC Markets solo actualizando el conector.
- **Escalabilidad de Capital**: El sistema soporta balanceadores de riesgo que pueden manejar desde $20 hasta $200,000 sin cambiar la lógica base.

---

## 4. Veredicto Técnico
**VALORACIÓN: INFRAESTRUCTURA DE ALTA FIDELIDAD**
Este software tiene una estructura comparable a los sistemas de **Prop Firms** o **Hedge Funds** pequeños. La modularidad garantiza que el software sea mantenible a largo plazo, y el uso de **Stable Baselines 3 (RL)** lo pone a la vanguardia tecnológica.

**Veredicto de Auditor**: "Un activo robusto donde el riesgo está controlado por 4 capas de software antes de llegar al mercado."
