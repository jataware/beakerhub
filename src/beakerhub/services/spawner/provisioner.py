import sys

from beaker_notebook.services.kernel.provisioner import BeakerLocalProvisioner

class BeakerhubLocalProvisioner(BeakerLocalProvisioner):
    """
    Forward launched kernel logs to the parent process output streams.
    """
    async def launch_kernel(self, cmd, **kwargs):
        kwargs.setdefault("stdout", sys.stdout)
        kwargs.setdefault("stderr", sys.stderr)

        return await super().launch_kernel(cmd, **kwargs)
