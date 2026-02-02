"""Delete orphan Firecracker VM using mikrom-py FirecrackerClient."""

import asyncio
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import mikrom
sys.path.insert(0, str(Path(__file__).parent.parent))

from mikrom.clients.firecracker import FirecrackerClient, FirecrackerError
from mikrom.utils.logger import get_logger

logger = get_logger(__name__)

VM_ID = "srv-c1c695b0"
HOST = "firecracker-01"
HOST_IP = "192.168.123.215"


async def check_vm_process(vm_id: str, host_ip: str) -> bool:
    """Check if VM process is running on remote host."""
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=5",
                f"root@{host_ip}",
                f"ps aux | grep '/firecracker ' | grep '{vm_id}' | grep -v grep",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and vm_id in result.stdout
    except Exception as e:
        logger.error(f"Error checking VM process: {e}")
        return False


async def main():
    """Delete orphan VM."""
    print("=" * 70)
    print("ELIMINACIÓN DE VM HUÉRFANA DE FIRECRACKER")
    print("=" * 70)

    print("\n📋 Información de la VM:")
    print(f"   ID: {VM_ID}")
    print(f"   Host: {HOST} ({HOST_IP})")

    # Check if VM is running
    print("\n🔍 Verificando si la VM está corriendo...")
    is_running = await check_vm_process(VM_ID, HOST_IP)

    if is_running:
        print("   ✓ VM encontrada corriendo en el host")
    else:
        print("   ⚠️  VM no encontrada corriendo (puede estar ya detenida)")
        response = input("\n¿Continuar con la limpieza de recursos? (s/n): ")
        if response.lower() != "s":
            print("Operación cancelada")
            return

    # Initialize FirecrackerClient
    print("\n🔧 Inicializando FirecrackerClient...")
    try:
        client = FirecrackerClient()
        print("   ✓ Cliente inicializado")
        print(f"   ✓ Deploy path: {client.deploy_path}")
    except FirecrackerError as e:
        print(f"   ✗ Error: {e}")
        return

    # Delete VM
    print("\n🗑️  Ejecutando cleanup de VM...")
    print("   Esto incluirá:")
    print("   - Detener proceso de Firecracker")
    print("   - Eliminar directorio jail")
    print("   - Eliminar dispositivo TAP")
    print("   - Liberar IP del pool (si existe)")
    print("   - Eliminar logs")

    try:
        result = await client.cleanup_vm(vm_id=VM_ID, limit=HOST)

        print("\n✅ Cleanup completado exitosamente!")
        print(f"   Status: {result['status']}")
        print(f"   Return code: {result['rc']}")
        print(f"   Stats: {result['stats']}")

    except FirecrackerError as e:
        print("\n❌ Error durante el cleanup:")
        print(f"   {e}")
        return

    # Verify VM is stopped
    print("\n🔍 Verificando que la VM fue detenida...")
    is_still_running = await check_vm_process(VM_ID, HOST_IP)

    if is_still_running:
        print("   ⚠️  La VM aún parece estar corriendo")
        print("   Puede ser necesario forzar la terminación del proceso")
    else:
        print("   ✓ VM detenida correctamente")

    # Summary
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"  VM ID: {VM_ID}")
    print(f"  Host: {HOST}")
    print(
        f"  Estado: {'ELIMINADA' if not is_still_running else 'ERROR - AÚN CORRIENDO'}"
    )
    print("\n✅ La VM huérfana ha sido limpiada del sistema")


if __name__ == "__main__":
    asyncio.run(main())
