---
name: nueva-funcionalidad
description: Flujo completo para implementar una tarea (funcionalidad, corrección o refactor) en este repo — rama, plan, tests, implementación, verificación, roadmap y PR. Úsala cuando el usuario pida construir, añadir, cambiar o arreglar algo, o "sigue con la siguiente tarea del roadmap".
---

# Nueva funcionalidad / tarea

## 1. Situarse

- Lee `docs/ROADMAP.md`. Si el usuario no ha dicho qué hacer, propón la siguiente tarea sin marcar de la fase actual y confírmala.
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

En la descripción del PR: qué cambia, cómo se verificó, qué no se pudo verificar y cualquier acción manual necesaria (p. ej. en Streamlit Cloud o Vercel). **No fusiones tú el PR** salvo que el usuario lo pida expresamente: `main` despliega a producción.
