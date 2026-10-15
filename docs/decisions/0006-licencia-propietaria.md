# 0006 — Licencia propietaria

- **Estado**: Aceptada
- **Fecha**: 2026-10-15

## Contexto

El `LICENSE` era CC BY-NC 4.0, mientras que `core/pyproject.toml` había llegado a declarar EUPL-1.2: dos licencias contradictorias. Las licencias Creative Commons no están pensadas para software (no tratan patentes ni distinguen código fuente de binario). Además, el propietario quiere monetizar el proyecto más adelante y conservar todas las opciones.

## Decisión

El repositorio pasa a ser **propietario, con todos los derechos reservados**. Sigue siendo público en GitHub solo para su consulta. El texto está en `LICENSE`; los `pyproject.toml` declaran `license = "LicenseRef-Proprietary"` y el clasificador `Private :: Do Not Upload`, que evita publicarlos en PyPI por error.

## Alternativas consideradas

- **Mantener CC BY-NC 4.0**: no está pensada para software, y la cláusula "no comercial" es ambigua.
- **AGPL-3.0**: protege frente a quien la use como servicio sin publicar sus cambios, pero permite el uso comercial por terceros, así que limita las opciones de monetizar.
- **Hacer el repositorio privado**: se puede hacer más adelante sin cambiar nada de esta decisión. Por ahora lo público sirve de escaparate.

## Consecuencias

- Nadie puede reutilizar el código sin permiso. Las contribuciones externas, si llegan, necesitarán un acuerdo de cesión (CLA).
- Las versiones publicadas antes de este cambio siguen bajo CC BY-NC 4.0 para quien las obtuviera: una licencia ya concedida no se puede retirar.
- Las dependencias (revisadas el 2026-10-15) permiten usarlas en software propietario. Casi todas son permisivas (BSD, MIT, Apache). La excepción es `certifi` (MPL-2.0, copyleft débil), que vale porque se usa sin modificar. Antes de añadir una dependencia nueva, comprueba que no sea copyleft fuerte (GPL o AGPL).
- Las atribuciones de datos de terceros (MITECO, OpenStreetMap) siguen siendo obligatorias en la interfaz.
