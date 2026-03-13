"""
Scopes skeleton: thinking as a user, not a library author.

Three scenarios where scoped dependencies emerge naturally in non-web apps:
  1. Data processing pipeline (primary example, fully fleshed out)
     1-E. Same pipeline on Ray — tests the serialization boundary
  2. Multi-tenant batch processor (brief sketch)
  3. Plugin-based CLI tool (brief sketch)

Key design thesis demonstrated here:
  - Container nesting IS the scope mechanism. No separate scope= declaration needed.
  - Where you bind determines the scope. Bind to app → app-lived. Bind to job → job-lived.
  - `async with DIBox(parent=...)` is both scope entry AND lifecycle boundary.
  - The missing connector (resolver / contextvar) is what makes @inject work across scopes.

This file is a user-perspective wishlist. Comments mark what exists today vs. what's proposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from dibox import DIBox, Injected, inject


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO 1: Geospatial data processing pipeline
#
# Real-world context: a system that ingests satellite imagery, runs it through
# multiple processing stages (tile, enhance, classify, merge), and writes
# results to object storage. Each stage may allocate GPU memory, temp files,
# or open network connections that must be cleaned up before the next stage.
#
# Natural scope hierarchy:
#   app          → config, storage client, model registry (live forever)
#   pipeline run → run ID, metrics collector, artifact manifest (per execution)
#   stage        → GPU context, temp directory, stage-specific buffer (per stage)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ── Domain types ─────────────────────────────────────────────────────────────

@dataclass
class AppConfig:
    storage_url: str
    model_registry_url: str
    tile_size: int = 512


class StorageClient:
    """Expensive: opens connection pool. App-scoped."""
    def __init__(self, config: AppConfig):
        self.url = config.storage_url

    async def upload(self, key: str, data: bytes) -> None: ...
    async def download(self, key: str) -> bytes: ...
    async def close(self) -> None: ...          # called by DIBox on exit


class ModelRegistry:
    """Loads ML model metadata. App-scoped."""
    def __init__(self, config: AppConfig):
        self.url = config.model_registry_url

    async def get_model(self, name: str) -> object: ...
    async def close(self) -> None: ...


@dataclass
class PipelineRun:
    """One per pipeline execution. Tracks metrics and artifacts."""
    run_id: str
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)

    def record(self, name: str, value: float) -> None:
        self.metrics[name] = value


@dataclass
class StageContext:
    """One per stage. Owns temp resources."""
    stage_name: str
    temp_dir: Path

    async def close(self) -> None:
        # cleanup temp files — called automatically by DIBox
        ...


class GPUContext:
    """Allocates/frees GPU memory. Stage-scoped so we don't leak across stages."""
    def __init__(self, config: AppConfig) -> None:
        self.tile_size = config.tile_size

    async def close(self) -> None:
        # release GPU memory
        ...


# ── Services with cross-scope dependencies ───────────────────────────────────

class TileLoader:
    """Needs app-level storage + run-level tracking."""
    def __init__(self, storage: StorageClient, run: PipelineRun) -> None:
        self.storage = storage
        self.run = run

    async def load_tiles(self, source_key: str) -> list[bytes]:
        raw = await self.storage.download(source_key)
        self.run.record("tiles_loaded", 1)
        return [raw]  # simplified


class Enhancer:
    """Stage-level: needs GPU + temp dir + app config."""
    def __init__(self, gpu: GPUContext, stage_ctx: StageContext, config: AppConfig) -> None:
        self.gpu = gpu
        self.stage_ctx = stage_ctx
        self.config = config

    async def enhance(self, tiles: list[bytes]) -> list[bytes]:
        # writes intermediates to stage_ctx.temp_dir, uses GPU
        return tiles


class Classifier:
    """Stage-level: needs GPU + model registry + run tracking."""
    def __init__(self, gpu: GPUContext, registry: ModelRegistry, run: PipelineRun) -> None:
        self.gpu = gpu
        self.registry = registry
        self.run = run

    async def classify(self, tiles: list[bytes]) -> list[dict[str, float]]:
        self.run.record("tiles_classified", len(tiles))
        return [{"urban": 0.8, "forest": 0.2}]


class ResultMerger:
    """Run-level: merges stage outputs, writes to storage."""
    def __init__(self, storage: StorageClient, run: PipelineRun) -> None:
        self.storage = storage
        self.run = run

    async def merge_and_upload(self, classifications: list[dict[str, float]]) -> str:
        key = f"results/{self.run.run_id}/output.json"
        await self.storage.upload(key, b"{}")
        self.run.artifacts.append(key)
        return key


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APPROACH A: Explicit container plumbing (works TODAY with container nesting)
#
# This is what you'd write once DIBox(parent=...) is implemented.
# Clean, explicit, debuggable. The "cost" is manual provide() calls.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def approach_a_explicit():
    # ── App scope ────────────────────────────────────────────────────────
    app = DIBox()
    app.bind(AppConfig, instance=AppConfig(
        storage_url="s3://geo-bucket",
        model_registry_url="http://models.internal",
    ))
    app.bind(StorageClient)     # auto-wired from AppConfig
    app.bind(ModelRegistry)     # auto-wired from AppConfig

    async with app:
        await process_imagery(app, source="s3://geo-bucket/scene-001.tif")
        await process_imagery(app, source="s3://geo-bucket/scene-002.tif")
        # StorageClient.close(), ModelRegistry.close() called here


async def process_imagery(app: DIBox, source: str):
    # ── Run scope ────────────────────────────────────────────────────────
    async with DIBox(parent=app) as run:
        run.bind(PipelineRun, instance=PipelineRun(run_id="run-001"))
        run.bind(TileLoader)        # depends on StorageClient(app) + PipelineRun(run)
        run.bind(ResultMerger)      # depends on StorageClient(app) + PipelineRun(run)

        loader = await run.provide(TileLoader)
        tiles = await loader.load_tiles(source)

        # ── Stage: enhance ───────────────────────────────────────────────
        async with DIBox(parent=run) as stage:
            stage.bind(StageContext, instance=StageContext("enhance", Path("/tmp/enhance")))
            stage.bind(GPUContext)       # depends on AppConfig(app)
            stage.bind(Enhancer)         # depends on GPUContext(stage) + StageContext(stage) + AppConfig(app)

            enhancer = await stage.provide(Enhancer)
            tiles = await enhancer.enhance(tiles)
        # GPUContext.close() + StageContext.close() called — GPU memory freed, temp files gone

        # ── Stage: classify ──────────────────────────────────────────────
        async with DIBox(parent=run) as stage:
            stage.bind(StageContext, instance=StageContext("classify", Path("/tmp/classify")))
            stage.bind(GPUContext)       # fresh GPU allocation for this stage
            stage.bind(Classifier)       # depends on GPUContext(stage) + ModelRegistry(app) + PipelineRun(run)

            classifier = await stage.provide(Classifier)
            classifications = await classifier.classify(tiles)
        # GPU freed again. Clean separation between stages.

        merger = await run.provide(ResultMerger)
        key = await merger.merge_and_upload(classifications)

        pipeline_run = await run.provide(PipelineRun)
        print(f"Done: {pipeline_run.run_id}, artifacts: {pipeline_run.artifacts}")
    # PipelineRun, TileLoader, ResultMerger gone. App-level resources untouched.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APPROACH B: @inject + contextvar-based container (PROPOSED)
#
# Pain point in Approach A: every function manually calls provide().
# In a real pipeline with 15 stages and helper functions, this gets tedious.
#
# Idea: when you enter `async with DIBox(parent=...) as box`, the container
# pushes itself onto a contextvar stack. @inject resolves from the top of
# that stack. Exiting the `async with` pops it.
#
# This is the contextvar evolution of global_box.py and connects to the
# "resolver" concept in injection_modes.md.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Stage functions become plain functions with declared dependencies.
# No container reference, no provide() calls. Just types.

@inject  # resolves from "current container" via contextvar
async def enhance_tiles(
    tiles: list[bytes],               # regular argument, passed by caller
    enhancer: Injected[Enhancer],     # injected from current container scope
) -> list[bytes]:
    return await enhancer.enhance(tiles)

@inject
async def classify_tiles(
    tiles: list[bytes],
    classifier: Injected[Classifier],
) -> list[dict[str, float]]:
    return await classifier.classify(tiles)

@inject
async def merge_results(
    classifications: list[dict[str, float]],
    merger: Injected[ResultMerger],
) -> str:
    return await merger.merge_and_upload(classifications)


async def approach_b_contextvar():
    app = DIBox()
    app.bind(AppConfig, instance=AppConfig(
        storage_url="s3://geo-bucket",
        model_registry_url="http://models.internal",
    ))
    app.bind(StorageClient)
    app.bind(ModelRegistry)

    async with app:  # app becomes "current container"
        await process_imagery_b(app, source="s3://geo-bucket/scene-001.tif")


async def process_imagery_b(app: DIBox, source: str):
    async with DIBox(parent=app) as run:  # run becomes "current container"
        run.bind(PipelineRun, instance=PipelineRun(run_id="run-002"))
        run.bind(TileLoader)
        run.bind(ResultMerger)

        # TileLoader resolved from run (which inherits StorageClient from app)
        loader = await run.provide(TileLoader)
        tiles = await loader.load_tiles(source)

        # ── Stage: enhance ───────────────────────────────────────────────
        async with DIBox(parent=run) as stage:  # stage becomes "current container"
            stage.bind(StageContext, instance=StageContext("enhance", Path("/tmp/enhance")))
            stage.bind(GPUContext)
            stage.bind(Enhancer)

            # enhance_tiles is @inject'd — Enhancer resolved from `stage` automatically
            tiles = await enhance_tiles(tiles)
        # stage exits, container pops back to run

        # ── Stage: classify ──────────────────────────────────────────────
        async with DIBox(parent=run) as stage:
            stage.bind(StageContext, instance=StageContext("classify", Path("/tmp/classify")))
            stage.bind(GPUContext)
            stage.bind(Classifier)

            classifications = await classify_tiles(tiles)

        key = await merge_results(classifications)
        # ↑ merger resolved from run (current container after stage exited)
        print(f"Output: {key}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APPROACH C: container.call() — greedy resolution, no markers needed
#
# For pipeline orchestration code that shouldn't need Injected[] markers.
# The container already knows what it can provide. Just fill what you can.
#
# This is the container.call() idea from injection_modes.md.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# No @inject, no Injected[]. Just plain functions with type hints.

async def enhance_tiles_plain(tiles: list[bytes], enhancer: Enhancer) -> list[bytes]:
    return await enhancer.enhance(tiles)

async def classify_tiles_plain(tiles: list[bytes], classifier: Classifier) -> list[dict[str, float]]:
    return await classifier.classify(tiles)


async def approach_c_container_call():
    app = DIBox()
    app.bind(AppConfig, instance=AppConfig(
        storage_url="s3://geo-bucket",
        model_registry_url="http://models.internal",
    ))
    app.bind(StorageClient)
    app.bind(ModelRegistry)

    async with app:
        async with DIBox(parent=app) as run:
            run.bind(PipelineRun, instance=PipelineRun(run_id="run-003"))
            run.bind(TileLoader)
            run.bind(ResultMerger)

            loader = await run.provide(TileLoader)
            tiles = await loader.load_tiles("s3://input")

            async with DIBox(parent=run) as stage:
                stage.bind(StageContext, instance=StageContext("enhance", Path("/tmp/enhance")))
                stage.bind(GPUContext)
                stage.bind(Enhancer)

                # container.call: "I'll fill in whatever I can, you pass the rest"
                tiles = await stage.call(enhance_tiles_plain, tiles=tiles)

            async with DIBox(parent=run) as stage:
                stage.bind(StageContext, instance=StageContext("classify", Path("/tmp/classify")))
                stage.bind(GPUContext)
                stage.bind(Classifier)

                classifications = await stage.call(classify_tiles_plain, tiles=tiles)

            key = await run.call(merge_results, classifications=classifications)
            # ^ merge_results still has @inject but container.call also works with plain funcs
            print(f"Output: {key}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APPROACH D: Binding modules — reusable scope recipes (PROPOSED)
#
# In real pipelines you repeat the same bindings across stages. Binding
# modules package a related set of bindings together.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# A module is just a function that configures a container.
# No special base class needed. The simplest thing that works.

def gpu_stage_module(box: DIBox, stage_name: str, temp_dir: Path) -> None:
    """Reusable bindings for any GPU-accelerated pipeline stage."""
    box.bind(StageContext, instance=StageContext(stage_name, temp_dir))
    box.bind(GPUContext)


def enhance_module(box: DIBox) -> None:
    gpu_stage_module(box, "enhance", Path("/tmp/enhance"))
    box.bind(Enhancer)


def classify_module(box: DIBox) -> None:
    gpu_stage_module(box, "classify", Path("/tmp/classify"))
    box.bind(Classifier)


async def approach_d_modules():
    app = DIBox()
    app.bind(AppConfig, instance=AppConfig(
        storage_url="s3://geo-bucket",
        model_registry_url="http://models.internal",
    ))
    app.bind(StorageClient)
    app.bind(ModelRegistry)

    async with app:
        async with DIBox(parent=app) as run:
            run.bind(PipelineRun, instance=PipelineRun(run_id="run-004"))
            run.bind(TileLoader)
            run.bind(ResultMerger)

            loader = await run.provide(TileLoader)
            tiles = await loader.load_tiles("s3://input")

            async with DIBox(parent=run) as stage:
                enhance_module(stage)  # one line sets up the whole stage
                tiles = await stage.call(enhance_tiles_plain, tiles=tiles)

            async with DIBox(parent=run) as stage:
                classify_module(stage)
                classifications = await stage.call(classify_tiles_plain, tiles=tiles)

            merger = await run.provide(ResultMerger)
            key = await merger.merge_and_upload(classifications)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO 1-E: Same pipeline, but stages run on Ray workers
#
# Ray breaks the single-process assumption. You can't pass a DIBox, a
# StorageClient, or a GPUContext across the serialization boundary.
# What CAN cross: dataclasses, plain dicts, bytes — i.e. config and data.
# What CANNOT cross: connections, handles, managed resources.
#
# This forces a clean separation:
#   orchestrator (driver)  → owns app container, coordinates pipeline
#   worker (Ray task/actor) → creates its OWN container from config, owns its resources
#
# Key insight: binding modules become the contract between driver and worker.
# The driver says "run this stage with this config"; the worker uses the
# module to set up its own container, does the work, tears it down.
#
# Does container nesting still work? Yes, but the parent-child relationship
# is LOCAL to each process. The driver has app→run nesting; each worker
# has its own local_app→stage nesting. Config is the bridge.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import ray  # type: ignore


# ── Ray-compatible stage functions ───────────────────────────────────────────
# These run in a separate process. They receive serializable config,
# build their own container, do the work, tear it down, return data.

@ray.remote(num_gpus=1)
class StageWorker:
    """
    A Ray actor that owns a local DIBox for its lifetime.
    The actor IS the scope boundary — __init__ enters, __del__/shutdown exits.

    Why an actor instead of a stateless task?
    - GPU allocation is expensive; we want to reuse it across tiles in a stage.
    - The actor lifecycle naturally maps to DIBox's async-with lifecycle.
    - Stateless @ray.remote tasks would create+destroy a container per call,
      which is fine for CPU work but wasteful for GPU-heavy stages.
    """

    def __init__(self, config: AppConfig, stage_name: str) -> None:
        # Each actor builds its own container from serializable config.
        # No parent container crosses the process boundary — config does.
        self.box = DIBox()
        self.box.bind(AppConfig, instance=config)
        self.box.bind(StorageClient)     # actor's own connection
        self.box.bind(ModelRegistry)     # actor's own connection
        self.box.bind(StageContext, instance=StageContext(stage_name, Path(f"/tmp/{stage_name}")))
        self.box.bind(GPUContext)
        self.box.bind(Enhancer)
        self.box.bind(Classifier)
        # Note: we can't use `async with` in Ray actor __init__.
        # Options: (a) explicit start/shutdown methods,
        # (b) DIBox supports non-context-manager lifecycle (start()/close())
        # For now, assume (a):

    async def start(self) -> None:
        """Called once after actor creation. Enters the container scope."""
        await self.box.__aenter__()

    async def shutdown(self) -> None:
        """Explicit teardown — releases GPU, closes connections."""
        await self.box.__aexit__(None, None, None)

    async def enhance(self, tiles: list[bytes]) -> list[bytes]:
        enhancer = await self.box.provide(Enhancer)
        return await enhancer.enhance(tiles)

    async def classify(self, tiles: list[bytes]) -> list[dict[str, float]]:
        classifier = await self.box.provide(Classifier)
        return await classifier.classify(tiles)


# ── Alternative: stateless tasks with per-call containers ────────────────────
# Simpler, no actor lifecycle to manage. Good for CPU-bound or cheap stages.
# Each task creates, uses, and destroys its own container.

@ray.remote
def enhance_remote(config: AppConfig, tiles: list[bytes]) -> list[bytes]:
    """
    Stateless Ray task. Container lives for exactly one function call.
    Fine when setup is cheap (no GPU, no connection pool worth reusing).
    """
    import asyncio

    async def _run() -> list[bytes]:
        box = DIBox()
        box.bind(AppConfig, instance=config)
        box.bind(StageContext, instance=StageContext("enhance", Path("/tmp/enhance")))
        box.bind(GPUContext)
        box.bind(Enhancer)

        async with box:
            enhancer = await box.provide(Enhancer)
            return await enhancer.enhance(tiles)

    return asyncio.run(_run())

# With binding modules, the boilerplate shrinks:

@ray.remote
def enhance_remote_v2(config: AppConfig, tiles: list[bytes]) -> list[bytes]:
    import asyncio

    async def _run() -> list[bytes]:
        box = DIBox()
        box.bind(AppConfig, instance=config)
        enhance_module(box)  # <-- reuse the same module from Approach D

        async with box:
            return await box.call(enhance_tiles_plain, tiles=tiles)

    return asyncio.run(_run())


# ── Driver: orchestrates from the main process ──────────────────────────────

async def approach_e_ray_actors():
    """Actor-based: long-lived workers, amortize setup cost."""
    app = DIBox()
    config = AppConfig(
        storage_url="s3://geo-bucket",
        model_registry_url="http://models.internal",
    )
    app.bind(AppConfig, instance=config)
    app.bind(StorageClient)
    app.bind(ModelRegistry)

    async with app:
        async with DIBox(parent=app) as run:
            run.bind(PipelineRun, instance=PipelineRun(run_id="run-005"))
            run.bind(TileLoader)
            run.bind(ResultMerger)

            loader = await run.provide(TileLoader)
            tiles = await loader.load_tiles("s3://input")

            # Spin up GPU workers — each creates its own container internally
            enhance_worker = StageWorker.remote(config, "enhance")  # type: ignore[attr-defined]
            classify_worker = StageWorker.remote(config, "classify")  # type: ignore[attr-defined]
            await enhance_worker.start.remote()  # type: ignore[attr-defined]
            await classify_worker.start.remote()  # type: ignore[attr-defined]

            try:
                # Data crosses the boundary (bytes). Dependencies don't.
                tiles = await enhance_worker.enhance.remote(tiles)  # type: ignore[attr-defined]
                classifications = await classify_worker.classify.remote(tiles)  # type: ignore[attr-defined]
            finally:
                # Explicit teardown — each worker closes its own container
                await enhance_worker.shutdown.remote()  # type: ignore[attr-defined]
                await classify_worker.shutdown.remote()  # type: ignore[attr-defined]

            merger = await run.provide(ResultMerger)
            key = await merger.merge_and_upload(classifications)
            print(f"Output: {key}")


async def approach_e_ray_tasks():
    """Task-based: stateless, simpler, container per call."""
    config = AppConfig(
        storage_url="s3://geo-bucket",
        model_registry_url="http://models.internal",
    )
    app = DIBox()
    app.bind(AppConfig, instance=config)
    app.bind(StorageClient)
    app.bind(ModelRegistry)

    async with app:
        async with DIBox(parent=app) as run:
            run.bind(PipelineRun, instance=PipelineRun(run_id="run-006"))
            run.bind(TileLoader)
            run.bind(ResultMerger)

            loader = await run.provide(TileLoader)
            tiles = await loader.load_tiles("s3://input")

            # Fire-and-forget tasks. Each builds its own container from config.
            tiles = await enhance_remote_v2.remote(config, tiles)  # type: ignore[attr-defined]
            # Could fan out: [enhance_remote_v2.remote(config, chunk) for chunk in chunks]

            # classify_remote would be analogous (omitted for brevity)
            # classifications = await classify_remote.remote(config, tiles)

            merger = await run.provide(ResultMerger)
            # key = await merger.merge_and_upload(classifications)


# ── Observations ─────────────────────────────────────────────────────────────
#
# 1. CONTAINER NESTING STILL WORKS — just not across the process boundary.
#    The driver has its own app→run nesting. Each worker has its own flat or
#    nested container. The contract between them is config (serializable data).
#
# 2. BINDING MODULES ARE THE KILLER FEATURE HERE.
#    Without modules, every Ray task repeats the same bind() boilerplate.
#    With modules, the worker says `enhance_module(box)` and gets a correctly
#    configured container in one line. The module IS the portable scope recipe.
#
# 3. THE ACTOR LIFECYCLE MISMATCH IS REAL.
#    Ray actors don't support `async with` in __init__. DIBox needs either:
#    (a) explicit start()/close() (already supported via InstanceBox hooks), or
#    (b) a helper like `await DIBox.create()` that returns an entered container.
#    This isn't specific to Ray — any framework with managed object lifecycles
#    (gRPC servicers, Thrift handlers) has the same pattern.
#
# 4. CONTEXTVAR @inject IS USELESS ACROSS PROCESSES.
#    Inside a single worker, it works fine. But the driver can't inject
#    dependencies into remote functions — they run in a different process
#    with a different contextvar stack. This is expected and correct:
#    DI helps you wire dependencies, not serialize them.
#
# 5. container.call() SHINES IN WORKERS.
#    `box.call(enhance_tiles_plain, tiles=tiles)` inside a Ray task is the
#    cleanest spelling. The function stays framework-agnostic; the container
#    fills in the dependencies; Ray only sees data in and data out.
#
# 6. WHAT DIBOX SHOULD NOT DO:
#    - Don't try to be Ray-aware. Don't add remote= or distributed= flags.
#    - Don't try to serialize containers or manage cross-process state.
#    - DO make it trivial to set up a fresh container from config + modules.
#      That's the right abstraction boundary.
#


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO 2 (mini): Multi-tenant batch job processor
#
# App: shared infra (queue, notification service)
# Tenant: tenant DB connection, tenant config (loaded per-tenant)
# Job: job context, results accumulator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class TenantConfig:
    tenant_id: str
    db_url: str

class TenantDB:
    def __init__(self, config: TenantConfig) -> None:
        self.db_url = config.db_url
    async def close(self) -> None: ...

class JobResult:
    def __init__(self) -> None:
        self.rows_processed: int = 0

class BatchProcessor:
    def __init__(self, db: TenantDB, result: JobResult) -> None:
        self.db = db
        self.result = result
    async def process(self) -> None: ...

class QueueClient:
    async def close(self) -> None: ...

class NotificationService:
    def __init__(self, config: AppConfig) -> None: ...
    async def notify(self, tenant_id: str, message: str) -> None: ...


async def scenario_2_multi_tenant():
    app = DIBox()
    app.bind(AppConfig, instance=AppConfig(storage_url="", model_registry_url=""))
    app.bind(QueueClient)
    app.bind(NotificationService)

    tenants = [
        TenantConfig("acme", "postgres://acme-db/main"),
        TenantConfig("globex", "postgres://globex-db/main"),
    ]

    async with app:
        for tenant_cfg in tenants:
            # ── Tenant scope ─────────────────────────────────────────────
            async with DIBox(parent=app) as tenant_box:
                tenant_box.bind(TenantConfig, instance=tenant_cfg)
                tenant_box.bind(TenantDB)  # auto-wired from TenantConfig

                for job_id in range(3):
                    # ── Job scope ────────────────────────────────────────
                    async with DIBox(parent=tenant_box) as job_box:
                        job_box.bind(JobResult)
                        job_box.bind(BatchProcessor)

                        processor = await job_box.provide(BatchProcessor)
                        await processor.process()

                        result = await job_box.provide(JobResult)
                        print(f"Tenant {tenant_cfg.tenant_id} job {job_id}: "
                              f"{result.rows_processed} rows")
                    # JobResult, BatchProcessor gone

                # Notify after all jobs for this tenant
                notifier = await tenant_box.provide(NotificationService)
                # ^ resolves NotificationService from app, but that's fine — it's app-scoped
                await notifier.notify(tenant_cfg.tenant_id, "All jobs complete")
            # TenantDB.close() called — connection returned


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCENARIO 3 (mini): Plugin-based CLI tool
#
# App: global config, output formatter
# Command: command-specific resources (file handles, network clients)
#
# Here the "scope" is just command execution lifetime.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class CLIConfig:
    verbose: bool = False
    output_format: str = "json"

class OutputFormatter:
    def __init__(self, config: CLIConfig) -> None:
        self.format = config.output_format
    def format_output(self, data: dict[str, object]) -> str: ...

class ReportGenerator:
    def __init__(self, formatter: OutputFormatter, db: TenantDB) -> None:
        self.formatter = formatter
        self.db = db
    async def generate(self) -> str: ...


async def scenario_3_cli():
    app = DIBox()
    app.bind(CLIConfig, instance=CLIConfig(verbose=True))
    app.bind(OutputFormatter)

    async with app:
        # Each CLI command runs in its own scope
        async with DIBox(parent=app) as cmd:
            cmd.bind(TenantConfig, instance=TenantConfig("local", "sqlite:///local.db"))
            cmd.bind(TenantDB)
            cmd.bind(ReportGenerator)

            gen = await cmd.provide(ReportGenerator)
            print(await gen.generate())
        # TenantDB connection closed, OutputFormatter still alive for next command


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WHAT I (the user) WANT FROM DIBOX — ranked by importance
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# 1. DIBox(parent=...) container nesting              — THE foundation
#    Without this, nothing else works. This gives me scope boundaries
#    and instance isolation with zero new concepts.
#
# 2. container.call(func, **explicit_args)            — eliminate provide() chains
#    Greedy resolution: the container fills what it can, I pass the rest.
#    This is the killer feature for pipeline code where I don't want @inject
#    on internal helpers.
#
# 3. Contextvar-based @inject resolution              — for entry points
#    Plain @inject resolves from "current container" (the innermost active
#    `async with DIBox(...)`). This makes framework integration seamless
#    and replaces the global_dibox singleton with something scope-aware.
#
# 4. Binding modules (plain functions)                — reusable scope setup
#    No base class, just `def setup(box): box.bind(...)`.
#    Package common binding groups for reuse.
#
# 5. container.validate() / container.visualize()     — debugging
#    "Show me the dependency graph" and "tell me what's missing" are
#    enormously valuable when nesting gets deep.
#
# ──────────────────────────────────────────────────────────────────────────────
# WHAT I DON'T WANT (yet)
# ──────────────────────────────────────────────────────────────────────────────
#
# - scope= parameter on bind(). It's redundant with container nesting.
#   Where I bind IS the scope. Adding a parallel scope concept creates
#   two ways to express the same thing and raises questions nobody has
#   good answers to (who manages scope lifecycle? how do named scopes
#   nest?). Container nesting already answers these questions structurally.
#
# - Named/enumerated scopes (RequestScope, SessionScope, etc.)
#   These are framework-specific vocabulary. A generic DI library should
#   provide the primitive (nesting + lifecycle), not the vocabulary.
#   If someone needs named scopes, they can name their binding modules.
#
# - Resolver stack / middleware chain on Injector
#   Cool idea but premature. Single resolver (or contextvar default)
#   covers 95% of cases. Stack adds debugging complexity.
#   Save it for when there's a concrete multi-resolver use case.
