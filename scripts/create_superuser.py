#!/usr/bin/env python3
"""Script para crear un superusuario en mikrom-py."""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar mikrom
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from getpass import getpass
from sqlmodel import Session, select
from mikrom.database import sync_engine
from mikrom.models import User
from mikrom.core.security import get_password_hash


def create_superuser():
    """Crear un nuevo superusuario de forma interactiva."""
    print("\n" + "=" * 60)
    print("  CREAR SUPERUSUARIO - mikrom-py")
    print("=" * 60 + "\n")

    # Solicitar datos
    try:
        email = input("Email: ").strip()
        username = input("Username: ").strip()
        password = getpass("Password: ")  # Oculta el password
        password_confirm = getpass("Confirmar Password: ")
        full_name = input("Full Name (opcional): ").strip() or None
    except EOFError:
        print("\n❌ Error: No se pudo leer la entrada")
        sys.exit(1)

    print()  # Línea en blanco

    # Validaciones básicas
    if not email or not username or not password:
        print("❌ Error: Email, username y password son requeridos")
        sys.exit(1)

    if password != password_confirm:
        print("❌ Error: Las contraseñas no coinciden")
        sys.exit(1)

    if len(password) < 6:
        print("❌ Error: La contraseña debe tener al menos 6 caracteres")
        sys.exit(1)

    if "@" not in email:
        print("❌ Error: El email debe tener un formato válido")
        sys.exit(1)

    # Crear usuario
    try:
        with Session(sync_engine) as session:
            # Verificar si ya existe
            statement = select(User).where(
                (User.email == email) | (User.username == username)
            )
            existing = session.exec(statement).first()

            if existing:
                if existing.email == email:
                    print(f"❌ Error: Ya existe un usuario con el email '{email}'")
                else:
                    print(
                        f"❌ Error: Ya existe un usuario con el username '{username}'"
                    )
                sys.exit(1)

            # Crear superusuario
            user = User(
                email=email,
                username=username,
                hashed_password=get_password_hash(password),
                full_name=full_name,
                is_active=True,
                is_superuser=True,
            )

            session.add(user)
            session.commit()
            session.refresh(user)

            print("=" * 60)
            print("✅ Superusuario creado exitosamente")
            print("=" * 60)
            print(f"  ID:          {user.id}")
            print(f"  Username:    {user.username}")
            print(f"  Email:       {user.email}")
            print(f"  Full Name:   {user.full_name or 'N/A'}")
            print(f"  Superuser:   ✓ True")
            print(f"  Active:      ✓ True")
            print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error al crear el usuario: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        create_superuser()
    except KeyboardInterrupt:
        print("\n\n❌ Operación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
