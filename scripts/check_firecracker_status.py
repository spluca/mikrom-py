"""Check for VMs in mikrom-py database and running Firecracker processes."""

import asyncio
import subprocess
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from mikrom.config import settings
from mikrom.models import VM


async def main():
    """Check VMs and processes."""
    # Create engine and session
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, echo=False)
    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    print("=" * 70)
    print("VERIFICACIÓN DE VMs Y PROCESOS DE FIRECRACKER")
    print("=" * 70)

    # Check database
    async with SessionLocal() as session:
        result = await session.execute(select(VM))
        vms = result.scalars().all()

        print(f"\n📊 VMs en base de datos: {len(vms)}")

        if vms:
            print(f"\n{'ID':<15} {'Nombre':<30} {'Estado':<12} {'IP':<15} {'Host'}")
            print("-" * 70)
            for vm in vms:
                status = (
                    vm.status.value if hasattr(vm.status, "value") else str(vm.status)
                )
                print(
                    f"{vm.vm_id:<15} {vm.name:<30} {status:<12} {vm.ip_address or 'N/A':<15} {vm.host or 'N/A'}"
                )

    await engine.dispose()

    # Check for Firecracker processes
    print("\n🔍 Buscando procesos de Firecracker...")
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        firecracker_processes = [
            line
            for line in result.stdout.split("\n")
            if "firecracker" in line.lower()
            and "grep" not in line
            and "qemu" not in line
        ]

        if firecracker_processes:
            print(
                f"\n⚠️  Procesos de Firecracker encontrados: {len(firecracker_processes)}"
            )
            for proc in firecracker_processes:
                print(f"   {proc}")
        else:
            print("\n✅ No hay procesos de Firecracker corriendo")

    except Exception as e:
        print(f"\n❌ Error al buscar procesos: {e}")

    # Check firecracker-deploy directory
    print("\n📁 Verificando directorio firecracker-deploy...")
    try:
        result = subprocess.run(
            ["ls", "-la", "/home/apardo/Work/mikrom/new/firecracker-deploy/vms/"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            lines = result.stdout.split("\n")
            vm_dirs = [
                line
                for line in lines
                if line.startswith("d") and not line.endswith((".", ".."))
            ]
            if vm_dirs:
                print(f"   Directorios de VMs encontrados: {len(vm_dirs)}")
                for vm_dir in vm_dirs:
                    print(f"      {vm_dir.split()[-1]}")
            else:
                print("   No hay directorios de VMs")
        else:
            print("   Directorio no existe o no es accesible")
    except Exception as e:
        print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
