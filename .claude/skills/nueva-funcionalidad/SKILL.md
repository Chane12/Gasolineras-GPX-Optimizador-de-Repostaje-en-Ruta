---
name: nueva-funcionalidad
description: Flujo completo para implementar una tarea (funcionalidad, corrección o refactor) en este repo — rama, plan, tests, implementación, verificación, roadmap, PR y fusión. Úsala cuando el usuario pida construir, añadir, cambiar o arreglar algo, o "sigue con la siguiente tarea del roadmap".
---

# Nueva funcionalidad / tarea

## 1. Situarse

- Lee `docs/ROADMAP.md`. Si el usuario no ha dicho qué hacer, coge la siguiente tarea sin marcar de la fase actual y empieza. Pide confirmación solo si implica una decisión de producto o de coste.
- Lee el `CLAUDE.md` de las carpetas que vas a tocar y los ADRs relacionados en `docs/decisions/`.
- Comprueba que no estás en `main`: `git status -sb`.

## 2. Rama

```bash
git checkout main && git pull --ff-only
git checkout -b <tipo>/<descripcion-corta>   # tipo: feat | fix | refactor | chore | docs | test
```

## 3. Plan breve (antes de escribir código)

Escribe al usuario, en 3–6 líneas: qué vas a cambiar, en qué archivos, cómo lo vas a probar y qué queda fuera. Si hay una decisión que es suya (producto, coste, servicios externos), pregúntala ahora. Si la tarea es grande, divídela en PRs pequeños.

## 4. Test primero cuando sea posible

- Bug: escribe el test que lo reproduce y comprueba que falla.
- Lógica nueva en `core/`: test unitario sin red (mockea `requests.get` con `monkeypatch`; ver `core/tests/test_miteco.py`).
- Respeta los invariantes del `CLAUDE.md` raíz (CRS, `core` sin UI, servicios externos con timeout y degradación elegante).

## 5. Implementar

- Cambios mínimos y enfocados; no refactorices de paso lo que no hace falta (anótalo como deuda en el ROADMAP).
- Idioma: identificadores en inglés, textos de interfaz en español (ADR 0004).
- El hook formatea solo; tú preocúpate de que el código sea correcto y legible.

## 6. Verificar

Usa la skill `/verificar`. No sigas hasta que esté en verde.

## 7. Documentar

- Marca la tarea en `docs/ROADMAP.md` y añade la deuda detectada.
- Decisión de arquitectura → ADR nuevo con la plantilla de `docs/decisions/README.md`.
- Si cambian comandos o la estructura → actualiza `CLAUDE.md` / `README.md`.

## 8. Commit y PR

```bash
git add -A
git commit -m "<tipo>: <qué y por qué, en inglés>"
git push -u origin HEAD
gh pr create --fill
```

En la descripción del PR: qué cambia, cómo se verificó, qué no se pudo verificar y cualquier acción manual necesaria (p. ej. en Streamlit Cloud o Vercel).

## 9. Fusionar (lo hace el agente)

El propietario delega la fusión: **fusiona tú** cuando se cumpla todo esto:
- El CI del PR está en verde: `gh pr checks <n> --watch`.
- Si el PR toca `core/`, `legacy/` o las dependencias, has pasado `./scripts/verify.sh --smoke`, porque `main` despliega a producción.
- El PR no incluye ninguna decisión de producto que el propietario no haya aprobado.

```bash
gh pr merge <n> --merge --delete-branch
git checkout main && git pull --ff-only
```

Si el PR llega a producción (toca `core/`, `legacy/` o las dependencias), espera a que Streamlit Cloud se redespliegue y comprueba: `uvx --from playwright python scripts/check_prod.py`. Si el PR tocó el core, la app se reinstala y reinicia, lo que lleva unos minutos; debe acabar mostrando "Precios MITECO actualizados ahora mismo" o pocos minutos. Si muestra "El MITECO no responde", investiga: es el síntoma de que la app no obtiene precios. Si falla, arréglalo de inmediato con un PR `fix/...`, o revierte con `gh pr create` sobre un `git revert`.

`main` está protegida (PR obligatorio, CI en verde, rama al día con `main`). Si GitHub pide actualizar la rama: `gh pr update-branch <n>` y espera de nuevo al CI. Nunca desactives la protección para fusionar.
