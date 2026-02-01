"""Client for Firecracker VM management via Ansible."""

import ansible_runner
from pathlib import Path
from typing import Optional, Dict, Any
from mikrom.config import settings
from mikrom.utils.logger import logger


class FirecrackerError(Exception):
    """Firecracker management error."""

    pass


class FirecrackerClient:
    """Client for managing Firecracker VMs via Ansible Runner."""

    def __init__(self, deploy_path: Optional[Path] = None):
        """
        Initialize client.

        Args:
            deploy_path: Path to firecracker-deploy directory
        """
        self.deploy_path = deploy_path or Path(settings.FIRECRACKER_DEPLOY_PATH)

        if not self.deploy_path.exists():
            raise FirecrackerError(
                f"Firecracker deploy path does not exist: {self.deploy_path}"
            )

        # Validate required playbooks exist
        required_playbooks = ["start-vm.yml", "stop-vm.yml", "cleanup-vm.yml"]
        for playbook in required_playbooks:
            playbook_path = self.deploy_path / playbook
            if not playbook_path.exists():
                raise FirecrackerError(f"Required playbook not found: {playbook_path}")

    def _run_playbook(
        self, playbook: str, extravars: Dict[str, Any], limit: Optional[str] = None
    ) -> ansible_runner.Runner:
        """
        Run an Ansible playbook.

        Args:
            playbook: Playbook filename
            extravars: Extra variables to pass
            limit: Limit to specific host

        Returns:
            ansible_runner.Runner instance

        Raises:
            FirecrackerError: If playbook execution fails
        """
        logger.info(f"Running playbook {playbook} with vars: {extravars}")

        try:
            runner = ansible_runner.run(
                playbook=playbook,
                private_data_dir=str(self.deploy_path),
                extravars=extravars,
                limit=limit,
                quiet=False,
                verbosity=0,
            )

            if runner.status != "successful":
                error_msg = f"Playbook {playbook} failed with status: {runner.status}"
                if runner.rc != 0:
                    error_msg += f", return code: {runner.rc}"
                logger.error(error_msg)

                # Try to get error details from events
                for event in runner.events:
                    if event.get("event") == "runner_on_failed":
                        event_data = event.get("event_data", {})
                        task = event_data.get("task", "Unknown task")
                        res = event_data.get("res", {})
                        msg = res.get("msg", res.get("stderr", "No error details"))
                        logger.error(f"Task '{task}' failed: {msg}")

                raise FirecrackerError(error_msg)

            logger.info(f"Playbook {playbook} completed successfully")
            return runner

        except Exception as e:
            if isinstance(e, FirecrackerError):
                raise
            error_msg = f"Failed to run playbook {playbook}: {str(e)}"
            logger.error(error_msg)
            raise FirecrackerError(error_msg) from e

    async def start_vm(
        self,
        vm_id: str,
        vcpu_count: int = 1,
        memory_mb: int = 256,
        kernel_path: Optional[str] = None,
        limit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a Firecracker VM.

        Args:
            vm_id: Unique VM identifier
            vcpu_count: Number of vCPUs
            memory_mb: Memory size in MB
            kernel_path: Optional custom kernel path
            limit: Limit to specific host

        Returns:
            dict with execution results

        Raises:
            FirecrackerError: If VM start fails
        """
        extravars = {
            "fc_vm_id": vm_id,
            "fc_vcpu_count": vcpu_count,
            "fc_mem_size_mib": memory_mb,
        }

        if kernel_path:
            extravars["fc_kernel_path"] = kernel_path

        runner = self._run_playbook("start-vm.yml", extravars, limit)

        return {
            "status": runner.status,
            "rc": runner.rc,
            "stats": runner.stats,
        }

    async def stop_vm(self, vm_id: str, limit: Optional[str] = None) -> Dict[str, Any]:
        """
        Stop a Firecracker VM.

        Args:
            vm_id: Unique VM identifier
            limit: Limit to specific host

        Returns:
            dict with execution results

        Raises:
            FirecrackerError: If VM stop fails
        """
        extravars = {"fc_vm_id": vm_id}
        runner = self._run_playbook("stop-vm.yml", extravars, limit)

        return {
            "status": runner.status,
            "rc": runner.rc,
            "stats": runner.stats,
        }

    async def cleanup_vm(
        self, vm_id: str, limit: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cleanup (delete) a Firecracker VM.

        Args:
            vm_id: Unique VM identifier
            limit: Limit to specific host

        Returns:
            dict with execution results

        Raises:
            FirecrackerError: If VM cleanup fails
        """
        extravars = {"fc_vm_id": vm_id}
        runner = self._run_playbook("cleanup-vm.yml", extravars, limit)

        return {
            "status": runner.status,
            "rc": runner.rc,
            "stats": runner.stats,
        }
