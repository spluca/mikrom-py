"""Client for Firecracker VM management via Ansible."""

import ansible_runner
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Optional, Dict, Any
from mikrom.config import settings
from mikrom.utils.logger import get_logger, log_timer
from mikrom.utils.telemetry import get_tracer, add_span_attributes, add_span_event

logger = get_logger(__name__)
tracer = get_tracer()


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
        Run an Ansible playbook in a thread pool with timeout enforcement.

        Args:
            playbook: Playbook filename
            extravars: Extra variables to pass
            limit: Limit to specific host

        Returns:
            ansible_runner.Runner instance

        Raises:
            FirecrackerError: If playbook execution fails or times out
        """
        with tracer.start_as_current_span(f"ansible.{playbook}") as span:
            # Add span attributes
            add_span_attributes(
                **{
                    "ansible.playbook": playbook,
                    "ansible.limit": limit or "all",
                    "ansible.timeout": settings.ANSIBLE_PLAYBOOK_TIMEOUT,
                }
            )

            # Add variables as attributes (sanitize sensitive data)
            for key, value in extravars.items():
                add_span_attributes(**{f"ansible.var.{key}": str(value)})

            logger.info(
                "Starting Ansible playbook execution",
                extra={
                    "playbook": playbook,
                    "variables": extravars,
                    "limit": limit,
                    "timeout": settings.ANSIBLE_PLAYBOOK_TIMEOUT,
                },
            )

            # Use /tmp for artifacts since deploy_path may be read-only
            artifact_dir = Path(tempfile.mkdtemp(prefix="ansible-"))

            def _execute_playbook():
                """Execute ansible-runner in separate thread."""
                return ansible_runner.run(
                    playbook=playbook,
                    private_data_dir=str(self.deploy_path),
                    artifact_dir=str(artifact_dir),
                    extravars=extravars,
                    limit=limit,
                    quiet=False,
                    verbosity=0,
                )

            try:
                with log_timer(f"playbook_{playbook}", logger):
                    # Execute in thread pool with timeout
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(_execute_playbook)
                        try:
                            runner = future.result(
                                timeout=settings.ANSIBLE_PLAYBOOK_TIMEOUT
                            )
                        except FuturesTimeoutError:
                            # Cancel the future and raise timeout error
                            future.cancel()
                            error_msg = (
                                f"Playbook {playbook} execution timed out after "
                                f"{settings.ANSIBLE_PLAYBOOK_TIMEOUT} seconds"
                            )
                            logger.error(
                                "Playbook execution timeout",
                                extra={
                                    "playbook": playbook,
                                    "timeout": settings.ANSIBLE_PLAYBOOK_TIMEOUT,
                                },
                            )
                            span.record_exception(TimeoutError(error_msg))
                            raise FirecrackerError(error_msg)

                if runner.status != "successful":
                    # Extract stats before they're cleaned up
                    try:
                        failed_stats = runner.stats
                    except Exception:
                        failed_stats = {}

                    error_msg = (
                        f"Playbook {playbook} failed with status: {runner.status}"
                    )
                    if runner.rc != 0:
                        error_msg += f", return code: {runner.rc}"

                    logger.error(
                        "Playbook execution failed",
                        extra={
                            "playbook": playbook,
                            "status": runner.status,
                            "return_code": runner.rc,
                            "stats": failed_stats,
                        },
                    )

                    # Try to get error details from events
                    try:
                        for event in runner.events:
                            if event.get("event") == "runner_on_failed":
                                event_data = event.get("event_data", {})
                                task = event_data.get("task", "Unknown task")
                                res = event_data.get("res", {})
                                msg = res.get(
                                    "msg", res.get("stderr", "No error details")
                                )

                                logger.error(
                                    "Ansible task failed",
                                    extra={
                                        "playbook": playbook,
                                        "task": task,
                                        "error_message": msg,
                                    },
                                )

                                add_span_event(
                                    "task_failed", {"task": task, "error": msg}
                                )
                    except Exception as e:
                        logger.warning(
                            "Could not extract event details",
                            extra={"error": str(e)},
                        )

                    span.record_exception(Exception(error_msg))
                    raise FirecrackerError(error_msg)

                # Extract stats and events while temp directory still exists
                try:
                    playbook_stats = runner.stats
                    # Store stats as attribute for later access
                    runner._extracted_stats = playbook_stats
                except Exception as e:
                    logger.warning(
                        "Could not extract playbook stats",
                        extra={"error": str(e)},
                    )
                    runner._extracted_stats = {}

                logger.info(
                    "Playbook completed successfully",
                    extra={
                        "playbook": playbook,
                        "stats": playbook_stats,
                    },
                )

                add_span_event("playbook_completed", {"status": runner.status})
                return runner

            except Exception as e:
                if isinstance(e, FirecrackerError):
                    raise

                error_msg = f"Failed to run playbook {playbook}: {str(e)}"
                logger.error(
                    "Playbook execution error",
                    extra={
                        "playbook": playbook,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                span.record_exception(e)
                raise FirecrackerError(error_msg) from e
            finally:
                # Clean up temporary artifact directory
                try:
                    if artifact_dir.exists():
                        shutil.rmtree(artifact_dir)
                        logger.debug(
                            "Cleaned up artifact directory",
                            extra={"artifact_dir": str(artifact_dir)},
                        )
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to clean up artifact directory",
                        extra={
                            "artifact_dir": str(artifact_dir),
                            "error": str(cleanup_error),
                        },
                    )

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
            "fc_ippool_server_url": settings.IPPOOL_EXTERNAL_API_URL
            or settings.IPPOOL_API_URL,
        }

        if kernel_path:
            extravars["fc_kernel_path"] = kernel_path

        runner = self._run_playbook("start-vm.yml", extravars, limit)

        return {
            "status": runner.status,
            "rc": runner.rc,
            "stats": getattr(runner, "_extracted_stats", {}),
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
            "stats": getattr(runner, "_extracted_stats", {}),
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
        extravars = {
            "fc_vm_id": vm_id,
            "fc_ippool_server_url": settings.IPPOOL_API_URL,
        }
        runner = self._run_playbook("cleanup-vm.yml", extravars, limit)

        return {
            "status": runner.status,
            "rc": runner.rc,
            "stats": getattr(runner, "_extracted_stats", {}),
        }
