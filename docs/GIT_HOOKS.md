# Git Hooks

Este proyecto utiliza Git hooks para mantener la calidad del código.

## Pre-commit Hook

El pre-commit hook ejecuta automáticamente el linter antes de cada commit para asegurar que el código cumple con los estándares de estilo.

### ¿Qué hace?

Antes de cada commit, el hook ejecuta:
```bash
make lint
```

Si el linting falla, el commit será rechazado y verás un mensaje con los errores que necesitas corregir.

### Instalación

El hook ya está instalado en `.git/hooks/pre-commit` y es ejecutable.

### Cómo arreglar errores de linting

Si el commit es rechazado por errores de linting:

1. **Auto-arreglar errores** (recomendado):
   ```bash
   make format  # Formatea el código automáticamente
   uv run ruff check --fix mikrom tests  # Arregla imports no usados, etc.
   ```

2. **Ver los errores**:
   ```bash
   make lint
   ```

3. **Arreglar manualmente** los errores que no se pueden auto-arreglar

4. **Intentar el commit nuevamente**:
   ```bash
   git add .
   git commit -m "Tu mensaje"
   ```

### Bypass del hook (NO recomendado)

En casos excepcionales, puedes saltar el hook con:
```bash
git commit --no-verify -m "mensaje"
```

⚠️ **No se recomienda** usar `--no-verify` ya que puede introducir código que no cumple con los estándares del proyecto.

### Errores comunes

#### Imports no usados
```python
# ❌ Error
from foo import bar  # 'bar' is imported but unused

# ✅ Solución
# Remover el import o usar la variable
```

#### Variables no usadas
```python
# ❌ Error
with tracer.start_as_current_span("operation") as span:
    # span no se usa en el código

# ✅ Solución
with tracer.start_as_current_span("operation") as _span:
    # _span indica que intencionalmente no se usa
```

#### Líneas muy largas
```bash
# Auto-arreglar con:
make format
```

## Otros hooks

Puedes agregar más hooks en `.git/hooks/` según las necesidades del proyecto:
- `pre-push`: Ejecutar tests antes de hacer push
- `commit-msg`: Validar formato de mensajes de commit
- `post-commit`: Acciones después de un commit exitoso

## Referencias

- [Git Hooks Documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
