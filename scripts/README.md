# Mikrom Scripts

Este directorio contiene scripts de utilidad para probar y gestionar el proyecto mikrom-py.

## Scripts Disponibles

### `test-vm-lifecycle.sh` - Prueba del Ciclo de Vida de VMs

Script bash completo para probar el ciclo de vida de una VM en mikrom-py, desde su creación hasta su eliminación.

#### ¿Qué hace este script?

El script ejecuta un test end-to-end que cubre:

1. ✅ **Validación inicial** - Verifica dependencias (curl, jq) y acceso a la API
2. ✅ **Autenticación** - Login con JWT y verificación del token
3. ✅ **Creación de VM** - Crea una nueva VM con recursos configurables
4. ✅ **Monitoreo de provisioning** - Espera hasta que la VM esté en estado "running"
5. ✅ **Verificación** - Valida que la VM aparece en la lista y tiene los datos correctos
6. ✅ **Actualización** - Modifica el nombre y descripción de la VM
7. ✅ **Eliminación** - Elimina la VM y confirma el cleanup
8. ✅ **Resumen** - Muestra estadísticas del test y duración total

#### Prerequisitos

Antes de ejecutar el script, asegúrate de tener:

1. **Dependencias instaladas:**
   ```bash
   # En Debian/Ubuntu
   sudo apt-get install curl jq
   
   # En macOS
   brew install curl jq
   ```

2. **Servicios corriendo:**
   ```bash
   # Desde el directorio mikrom-py/
   
   # Opción 1: Con Docker Compose (recomendado)
   docker compose up -d
   
   # Opción 2: Localmente
   docker compose up -d db redis  # Base de datos y Redis
   make worker                     # Worker en una terminal
   make run                        # API en otra terminal
   ```

3. **Usuario creado:**
   ```bash
   # Crear un superuser
   make superuser
   
   # Credenciales por defecto:
   # Username: admin
   # Password: admin123
   # Email: admin@example.com
   ```

4. **Servicios de infraestructura (para prueba completa):**
   - **ippool** corriendo en http://localhost:8080
   - **firecracker-deploy** configurado
   - **Servidor KVM** con SSH accesible

   > **Nota:** Si estos servicios no están disponibles, la VM se quedará en estado "provisioning" o "pending", pero el script probará correctamente las operaciones de API.

#### Uso Básico

```bash
# Hacer el script ejecutable (solo la primera vez)
chmod +x scripts/test-vm-lifecycle.sh

# Ejecutar con configuración por defecto
./scripts/test-vm-lifecycle.sh
```

#### Configuración

Puedes configurar el script mediante variables de entorno:

```bash
# Configuración de API
export API_URL="http://localhost:8000"
export API_API_USERNAME="admin"
export API_API_PASSWORD="admin123"

# Configuración de VM
export VM_NAME="my-test-vm"
export VM_VCPU_COUNT="2"
export VM_MEMORY_MB="512"
export VM_DESCRIPTION="Mi VM de prueba"

# Configuración de timeouts
export MAX_WAIT_TIME="180"      # Segundos para esperar estado 'running'
export POLL_INTERVAL="5"        # Segundos entre verificaciones de estado
export DELETE_WAIT_TIME="90"    # Segundos para esperar eliminación

# Modo verbose (muestra requests/responses completos)
export VERBOSE="true"

# Ejecutar script con configuración personalizada
./scripts/test-vm-lifecycle.sh
```

#### Ejemplos

**Ejemplo 1: Prueba básica con defaults**
```bash
./scripts/test-vm-lifecycle.sh
```

**Ejemplo 2: Prueba con VM más grande y modo verbose**
```bash
VM_VCPU_COUNT=4 VM_MEMORY_MB=1024 VERBOSE=true ./scripts/test-vm-lifecycle.sh
```

**Ejemplo 3: Prueba contra API remota**
```bash
API_URL="http://192.168.1.100:8000" \
API_USERNAME="testuser" \
API_PASSWORD="testpass123" \
./scripts/test-vm-lifecycle.sh
```

**Ejemplo 4: Prueba rápida (sin esperar VM real)**
```bash
# Útil para probar solo las operaciones de API
# La VM no llegará a 'running' sin infraestructura real
MAX_WAIT_TIME=10 ./scripts/test-vm-lifecycle.sh
```

#### Output del Script

El script genera output con colores para mejor legibilidad:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║               MIKROM VM LIFECYCLE TEST                         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

[INIT] Verificando prerequisitos...
  ✓ curl instalado
  ✓ jq instalado
  ✓ API accesible en http://localhost:8000
  → Configuración del test:
  → API: http://localhost:8000
  → Usuario: admin
  → VM: test-vm-1707123456
  → Recursos: 1 vCPU, 256 MB RAM
  → Timeout: 120s (polling cada 3s)

[AUTH] Autenticando usuario...
  ✓ Login exitoso
  ✓ Token obtenido
  ✓ Usuario autenticado: admin (admin@example.com)

[CREATE] Creando VM...
  ✓ VM creada: srv-a1b2c3d4
  → Estado inicial: pending
  → ID en BD: 1
  → Recursos: 1 vCPU, 256 MB RAM

[PROVISION] Esperando provisioning...
  ⏳ Estado: provisioning ... (0s)
  ⏳ Estado: provisioning ... (3s)
  ✓ VM en estado 'running' (8s)
  → IP asignada: 172.16.0.2

[VERIFY] Verificando VM...
  ✓ VM aparece en la lista
  ✓ Detalles de VM correctos
  → Nombre: test-vm-1707123456
  → Estado: running
  → Recursos: 1 vCPU, 256 MB
  → IP: 172.16.0.2

[UPDATE] Actualizando metadata de VM...
  ✓ Nombre actualizado: test-vm-1707123456-updated
  ✓ Descripción actualizada

[DELETE] Eliminando VM...
  ✓ Eliminación solicitada
  → Estado: deleting
  ⏳ Esperando eliminación completa...
  ✓ VM eliminada completamente (5s)

╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║                    ✓ TEST EXITOSO                              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

  → Duración total: 18s
  → VM ID: srv-a1b2c3d4
  → Estados: pending → provisioning → running → deleting → deleted
  
  → Estadísticas de tests:
  → Total: 12
  → Exitosos: 12
  → Tasa de éxito: 100%
```

#### Códigos de Salida

- **0** - Test exitoso (todas las verificaciones pasaron)
- **1** - Test fallido (una o más verificaciones fallaron)

#### Cleanup Automático

El script incluye cleanup automático mediante `trap EXIT`:
- Si el script se interrumpe (Ctrl+C) o falla, intentará eliminar la VM creada
- Si la eliminación normal completa exitosamente, no se realiza cleanup adicional

#### Troubleshooting

**Problema: "curl no está instalado"**
```bash
# Debian/Ubuntu
sudo apt-get install curl

# macOS
brew install curl
```

**Problema: "jq no está instalado"**
```bash
# Debian/Ubuntu
sudo apt-get install jq

# macOS
brew install jq
```

**Problema: "La API no está accesible"**
```bash
# Verificar que la API esté corriendo
curl http://localhost:8000/api/v1/health

# Si no responde, iniciar la API
cd mikrom-py
docker compose up -d
# O localmente:
make run
```

**Problema: "Login falló. Verifica las credenciales."**
```bash
# Crear un usuario si no existe
make superuser

# O especificar credenciales correctas
API_USERNAME="tu_usuario" API_PASSWORD="tu_password" ./scripts/test-vm-lifecycle.sh
```

**Problema: "Timeout esperando que la VM esté running"**

Esto es normal si no tienes la infraestructura completa (ippool, firecracker-deploy, KVM). El script igualmente probará las operaciones de API:

```bash
# Reducir el timeout para probar más rápido
MAX_WAIT_TIME=10 ./scripts/test-vm-lifecycle.sh
```

O configurar la infraestructura completa:
```bash
# 1. Iniciar ippool
cd ../ippool
cargo run

# 2. Verificar firecracker-deploy
cd ../firecracker-deploy
make network-setup
make template-create

# 3. Ejecutar el script nuevamente
cd ../mikrom-py
./scripts/test-vm-lifecycle.sh
```

**Problema: "VM se queda en estado 'provisioning'"**

Verifica los logs del worker:
```bash
# Con Docker
docker compose logs -f worker

# Localmente
# Ver la terminal donde corre 'make worker'
```

#### Integración con Make

Puedes agregar este script al Makefile del proyecto:

```makefile
# En mikrom-py/Makefile

test-vm-lifecycle: ## Probar ciclo de vida de VM
	@echo "$(GREEN)Ejecutando test de ciclo de vida de VM...$(NC)"
	./scripts/test-vm-lifecycle.sh

test-vm-quick: ## Prueba rápida de VM (sin esperar running)
	@echo "$(GREEN)Ejecutando prueba rápida de VM...$(NC)"
	MAX_WAIT_TIME=10 ./scripts/test-vm-lifecycle.sh
```

Luego puedes ejecutar:
```bash
make test-vm-lifecycle
make test-vm-quick
```

#### Uso en CI/CD

El script es ideal para integración continua:

```yaml
# En .gitlab-ci.yml
test:vm-lifecycle:
  stage: test
  services:
    - postgres:16
    - redis:7
  script:
    - apt-get update && apt-get install -y curl jq
    - docker compose up -d
    - sleep 5  # Esperar a que la API esté lista
    - make superuser  # Crear usuario de prueba
    - ./scripts/test-vm-lifecycle.sh
  only:
    - main
    - merge_requests
```

#### Variables de Entorno (Referencia Completa)

| Variable | Descripción | Default | Ejemplo |
|----------|-------------|---------|---------|
| `API_URL` | URL de la API mikrom-py | `http://localhost:8000` | `http://192.168.1.100:8000` |
| `API_USERNAME` | Usuario para autenticación | `admin` | `testuser` |
| `API_PASSWORD` | Contraseña del usuario | `admin123` | `myp@ssw0rd` |
| `VM_NAME_PREFIX` | Prefijo para el nombre de VM | `test-vm` | `ci-vm` |
| `VM_NAME` | Nombre completo de VM | `test-vm-{timestamp}` | `my-custom-vm` |
| `VM_VCPU_COUNT` | Número de vCPUs | `1` | `2` |
| `VM_MEMORY_MB` | Memoria RAM en MB | `256` | `512` |
| `VM_DESCRIPTION` | Descripción de la VM | `Test VM created...` | `My test VM` |
| `MAX_WAIT_TIME` | Timeout para estado 'running' (segundos) | `120` | `180` |
| `POLL_INTERVAL` | Intervalo entre verificaciones (segundos) | `3` | `5` |
| `DELETE_WAIT_TIME` | Timeout para eliminación (segundos) | `60` | `90` |
| `VERBOSE` | Mostrar requests/responses completos | `false` | `true` |

#### Desarrollo y Contribuciones

Para modificar o extender el script:

1. **Agregar nuevas validaciones:**
   ```bash
   # Buscar la función phase_verify_vm() y agregar más checks
   ```

2. **Agregar nuevas fases:**
   ```bash
   # Crear una nueva función phase_mi_nueva_fase()
   # Llamarla desde main()
   ```

3. **Probar cambios:**
   ```bash
   # Usar modo verbose para debugging
   VERBOSE=true ./scripts/test-vm-lifecycle.sh
   ```

4. **Verificar sintaxis:**
   ```bash
   bash -n scripts/test-vm-lifecycle.sh
   shellcheck scripts/test-vm-lifecycle.sh  # Si tienes shellcheck instalado
   ```

#### Licencia

Este script es parte del proyecto mikrom-py. Consulta el archivo LICENSE en la raíz del proyecto.

#### Soporte

Si encuentras problemas:
1. Verifica los prerequisitos arriba
2. Ejecuta con `VERBOSE=true` para más detalles
3. Revisa los logs del worker y la API
4. Abre un issue en el repositorio del proyecto

---

**Última actualización:** Febrero 2025  
**Mantenedor:** Mikrom Platform Team
