"""Run N concurrent GpuContention processes as one pressure source."""

from edgemedic.gpu_pressure import GpuContention, injector_config as gpu_injector_config, injector_hash as gpu_injector_hash


class MultiGpuContention:
    def __init__(self, replicas=2, **kwargs):
        self.replicas = max(1, int(replicas))
        self.kwargs = dict(kwargs)
        self.workers = [GpuContention(**kwargs) for _ in range(self.replicas)]

    def config(self):
        cfg = gpu_injector_config(**self.kwargs)
        cfg["replicas"] = self.replicas
        cfg["kind"] = f"multi_{cfg.get('kind')}"
        return cfg

    def hash(self):
        return gpu_injector_hash(self.config())

    def start(self):
        started = []
        for worker in self.workers:
            started.append(worker.start())
        return {"replicas": self.replicas, "workers": started, "config": self.config(), "hash": self.hash()}

    def alive(self):
        return all(worker.alive() for worker in self.workers)

    def stop(self):
        for worker in self.workers:
            worker.stop()
