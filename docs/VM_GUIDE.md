# 🚀 Gestión de VMs en mikrom-py - COMPLETADO

## ✅ Implementación Completada

La integración de gestión de microVMs Firecracker en mikrom-py ha sido completada exitosamente!

### Componentes Implementados

#### 1. **Base de Datos** ✅
- Modelo `VM` con todos los campos necesarios
- Relación `User ↔ VMs` (one-to-many)
- Migración de Alembic aplicada

#### 2. **Schemas Pydantic** ✅
- `VMCreate` - Validación de creación
- `VMUpdate` - Validación de actualización
- `VMResponse` - Respuesta de API
- `VMListResponse` - Lista paginada

#### 3. **Clientes Externos** ✅
- `IPPoolClient` - Gestión de IPs
- `FirecrackerClient` - Ejecución de Ansible

#### 4. **Background Tasks** ✅
- `create_vm_task` - Crear y arrancar VM
- `delete_vm_task` - Eliminar VM
- Worker de arq configurado

#### 5. **Servicio de Negocio** ✅
- `VMService` - Lógica de VMs
- Integración con Redis/arq
- Generación de IDs únicos

#### 6. **API REST** ✅
- `POST /api/v1/vms/` - Crear VM
- `GET /api/v1/vms/` - Listar VMs
- `GET /api/v1/vms/{id}` - Obtener VM
- `PATCH /api/v1/vms/{id}` - Actualizar VM
- `DELETE /api/v1/vms/{id}` - Eliminar VM

#### 7. **Docker** ✅
- Redis agregado a docker-compose
- Worker agregado a docker-compose
- Variables de entorno configuradas

---

## 🏃 Cómo Usar

### Prerrequisitos

Antes de crear VMs, asegúrate de tener:

1. **PostgreSQL corriendo** ✅ (ya está con docker-compose)
2. **Redis corriendo** ✅ (ya está con docker-compose)
3. **ippool corriendo** en puerto 8080
4. **firecracker-deploy** configurado
5. **Servidor con KVM** accesible vía SSH

### Paso 1: Levantar Servicios

```bash
cd mikrom-py

# Levantar DB + Redis
docker compose up -d db redis

# O todo junto (incluye worker)
docker compose up -d
```

### Paso 2: Iniciar el Worker (desarrollo local)

Terminal separada:

```bash
cd mikrom-py
make worker
```

### Paso 3: Iniciar la API (desarrollo local)

Otra terminal:

```bash
cd mikrom-py
make run
```

La API estará en http://localhost:8000

### Paso 4: Crear un Usuario

```bash
cd mikrom-py
make superuser

# Ingresar:
# Email: admin@example.com
# Username: admin
# Password: admin123
# Full Name: Administrator
```

### Paso 5: Probar la API

#### 5.1 Login

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | jq -r .access_token)

echo "Token: $TOKEN"
```

#### 5.2 Crear una VM

```bash
curl -X POST "http://localhost:8000/api/v1/vms/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-dev-vm",
    "description": "Mi primera VM de desarrollo",
    "vcpu_count": 1,
    "memory_mb": 256
  }' | jq
```

**Respuesta esperada:**
```json
{
  "id": 1,
  "vm_id": "srv-a1b2c3d4",
  "name": "my-dev-vm",
  "description": "Mi primera VM de desarrollo",
  "vcpu_count": 1,
  "memory_mb": 256,
  "ip_address": null,
  "status": "creating",
  "error_message": null,
  "host": null,
  "user_id": 1,
  "created_at": "2024-02-01T10:00:00Z",
  "updated_at": "2024-02-01T10:00:00Z"
}
```

#### 5.3 Ver el Estado de la VM

Espera 2-3 segundos para que el worker procese la tarea:

```bash
curl -X GET "http://localhost:8000/api/v1/vms/1" \
  -H "Authorization: Bearer $TOKEN" | jq
```

**Cuando esté lista:**
```json
{
  "id": 1,
  "vm_id": "srv-a1b2c3d4",
  "name": "my-dev-vm",
  "ip_address": "172.16.0.2",
  "status": "running",
  ...
}
```

#### 5.4 Listar VMs

```bash
curl -X GET "http://localhost:8000/api/v1/vms/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### 5.5 Conectar a la VM

```bash
ssh debian@172.16.0.2
# Password: debian
```

#### 5.6 Eliminar la VM

```bash
curl -X DELETE "http://localhost:8000/api/v1/vms/1" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## 📊 Verificar el Worker

```bash
# Ver logs del worker
docker compose logs -f worker

# O si ejecutas localmente:
# Ver la terminal donde corre `make worker`
```

---

## 🐛 Troubleshooting

### VM se queda en "creating"

**Causa:** Worker no está corriendo o falló

**Solución:**
```bash
# Ver logs del worker
docker compose logs worker

# Verificar que Redis está corriendo
docker compose ps redis

# Verificar que ippool está corriendo
curl http://localhost:8080/api/v1/health
```

### Error: "Firecracker deploy path does not exist"

**Causa:** La ruta en `.env` no es correcta

**Solución:**
```bash
# Editar .env
FIRECRACKER_DEPLOY_PATH=/ruta/correcta/a/firecracker-deploy

# Reiniciar worker
docker compose restart worker
```

### VM en estado "error"

**Causa:** Fallo en Ansible o ippool

**Solución:**
```bash
# Ver el mensaje de error
curl -X GET "http://localhost:8000/api/v1/vms/1" \
  -H "Authorization: Bearer $TOKEN" | jq .error_message

# Ver logs del worker para detalles
docker compose logs worker
```

---

## 🎯 Próximos Pasos Opcionales

1. **Tests** - Crear tests unitarios y de integración
2. **Operaciones adicionales** - Start/Stop de VMs
3. **Snapshots** - Guardar y restaurar estados de VMs
4. **Monitoreo** - Métricas de CPU, memoria, red
5. **Cuotas** - Límites por usuario
6. **UI Web** - Dashboard para gestión visual

---

## 📚 Documentación API

Accede a la documentación interactiva:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 🔧 Configuración Avanzada

### Variables de Entorno (.env)

```bash
# VM Management
IPPOOL_API_URL=http://localhost:8080
FIRECRACKER_DEPLOY_PATH=/path/to/firecracker-deploy
FIRECRACKER_DEFAULT_HOST=  # Opcional: limitar a un host

# Redis
REDIS_URL=redis://localhost:6379
ARQ_QUEUE_NAME=mikrom:queue
```

### Docker Compose

```bash
# Levantar todo
docker compose up -d

# Ver estado
docker compose ps

# Ver logs
docker compose logs -f

# Detener todo
docker compose down
```

---

## ✅ Checklist de Deployment

- [x] PostgreSQL corriendo
- [x] Redis corriendo
- [ ] ippool corriendo en puerto 8080
- [ ] firecracker-deploy configurado
- [ ] SSH a hosts de VMs funciona
- [ ] Network bridge configurado (make network-setup)
- [ ] Rootfs template creado (make template-create)
- [x] Migraciones aplicadas
- [x] Usuario creado
- [ ] Worker corriendo
- [ ] API corriendo

---

¡La implementación está completa y lista para usar! 🎉
