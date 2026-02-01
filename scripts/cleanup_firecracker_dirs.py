"""Clean up leftover Firecracker VM directories."""

import os
import shutil
import subprocess


def main():
    """Clean up Firecracker artifacts."""
    artifacts_dir = "/home/apardo/Work/mikrom/new/firecracker-deploy/artifacts"

    print("=" * 70)
    print("LIMPIEZA DE DIRECTORIOS DE FIRECRACKER")
    print("=" * 70)

    if not os.path.exists(artifacts_dir):
        print(f"\n✅ El directorio {artifacts_dir} no existe")
        return

    # List all VM directories
    vm_dirs = [
        d
        for d in os.listdir(artifacts_dir)
        if os.path.isdir(os.path.join(artifacts_dir, d))
    ]

    if not vm_dirs:
        print(f"\n✅ No hay directorios de VMs en {artifacts_dir}")
        return

    print(f"\n📁 Directorios encontrados: {len(vm_dirs)}")

    # Confirm deletion
    print(f"\n⚠️  Se eliminarán {len(vm_dirs)} directorios de VMs")
    print(f"   Ubicación: {artifacts_dir}")

    deleted_count = 0
    error_count = 0

    for vm_dir in vm_dirs:
        vm_path = os.path.join(artifacts_dir, vm_dir)
        try:
            # Check if there's a socket file (means VM might be running)
            socket_path = os.path.join(vm_path, "firecracker.socket")
            if os.path.exists(socket_path):
                print(f"\n⚠️  VM {vm_dir} tiene socket, intentando limpiar...")

            # Remove directory
            shutil.rmtree(vm_path)
            deleted_count += 1

            if deleted_count % 10 == 0:
                print(f"   Eliminados: {deleted_count}/{len(vm_dirs)}...")

        except Exception as e:
            error_count += 1
            print(f"   ✗ Error eliminando {vm_dir}: {e}")

    print(f"\n" + "=" * 70)
    print("RESUMEN DE LIMPIEZA")
    print("=" * 70)
    print(f"  Directorios procesados: {len(vm_dirs)}")
    print(f"  ✓ Eliminados exitosamente: {deleted_count}")
    if error_count > 0:
        print(f"  ✗ Errores: {error_count}")

    # Verify cleanup
    remaining = [
        d
        for d in os.listdir(artifacts_dir)
        if os.path.isdir(os.path.join(artifacts_dir, d))
    ]

    if remaining:
        print(f"\n⚠️  Aún quedan {len(remaining)} directorios")
    else:
        print(f"\n✅ Todos los directorios han sido eliminados")


if __name__ == "__main__":
    main()
