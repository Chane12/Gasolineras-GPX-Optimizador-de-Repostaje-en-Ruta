# Registro de decisiones de arquitectura (ADRs)

Cada archivo explica **una** decisión: el contexto, qué se decidió y sus consecuencias. Sirve para que nadie (persona o IA) deshaga una decisión sin saber por qué se tomó.

| Nº | Decisión | Estado |
|---|---|---|
| [0001](0001-stack-fastapi-nextjs.md) | Stack de la web: FastAPI + Next.js | Aceptada |
| [0002](0002-hosting-gratuito.md) | Alojamiento a 0 € hasta monetizar | Aceptada |
| [0003](0003-monorepo-uv-workspace.md) | Monorepo con workspace uv y `core` sin UI | Aceptada |
| [0004](0004-convencion-idioma.md) | Inglés en el código, español en interfaz y docs | Aceptada |
| [0005](0005-servicios-externos.md) | Uso responsable de MITECO, OSRM y Nominatim | Aceptada (implementada en la Fase 1; OSRM propio pendiente) |
| [0006](0006-licencia-propietaria.md) | Licencia propietaria (todos los derechos reservados) | Aceptada |
| [0007](0007-tls-miteco.md) | Cifrado TLS heredado solo para el MITECO | Aceptada |

## Cuándo escribir un ADR

Cuando una decisión sea difícil de revertir, afecte a varias carpetas, o alguien futuro pueda preguntarse "¿por qué está hecho así?". No para detalles de implementación.

## Plantilla

Copia esto en `NNNN-titulo-corto.md` (número siguiente) y añádelo a la tabla:

```markdown
# NNNN — Título

- **Estado**: Propuesta | Aceptada | Sustituida por NNNN
- **Fecha**: AAAA-MM-DD

## Contexto
Qué problema o situación obliga a decidir.

## Decisión
Qué se decide, en una o dos frases claras.

## Alternativas consideradas
Qué más se valoró y por qué se descartó.

## Consecuencias
Qué implica (bueno y malo) y qué habrá que vigilar.
```

Un ADR aceptado no se edita para cambiar la decisión: se escribe uno nuevo que lo sustituye.
