import sys

from beaker_notebook.services.kernel.provisioner import BeakerLocalProvisioner

class KubernetesLocalProvisioner(BeakerLocalProvisioner):
    """
    Custom Provisioner that is ensures that launched kernel logs are forwarded to the main stdout/stderr for proper logging in kubernetes
    """
    async def launch_kernel(self, cmd, **kwargs):
        kwargs.setdefault("stdout", sys.stdout)
        kwargs.setdefault("stderr", sys.stderr)

        return await super().launch_kernel(cmd, **kwargs)
