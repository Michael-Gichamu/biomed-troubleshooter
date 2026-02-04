"""
LangSmith Observability Integration

Provides tracing, monitoring, and debugging for the LangGraph agent.
Supports free LangSmith tier with offline/local development.
"""

import os
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class LangSmithConfig:
    """Configuration for LangSmith."""
    api_key: Optional[str] = None
    project_name: str = "biomed-troubleshooter"
    endpoint: str = "https://api.smith.langchain.com"
    enabled: bool = True
    trace_children: bool = True
    debug: bool = False


class LangSmithClient:
    """
    Client for LangSmith observability.

    Design:
    - Lazy initialization
    - Graceful fallback if LangSmith unavailable
    - Minimal overhead in production
    """

    def __init__(self, config: Optional[LangSmithConfig] = None):
        self.config = config or LangSmithConfig()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize LangSmith client."""
        if self._initialized:
            return

        # Check for API key from environment
        api_key = self.config.api_key or os.environ.get("LANGCHAIN_API_KEY")

        if not api_key:
            print("[LangSmith] API key not found - tracing disabled")
            self.config.enabled = False
            return

        try:
            from langsmith import Client
            self._client = Client(
                api_url=self.config.endpoint,
                api_key=api_key
            )
            self._initialized = True
            print(f"[LangSmith] Initialized project: {self.config.project_name}")
        except ImportError:
            print("[LangSmith] langsmith package not installed - tracing disabled")
            self.config.enabled = False
        except Exception as e:
            print(f"[LangSmith] Initialization failed: {e}")
            self.config.enabled = False

    def is_enabled(self) -> bool:
        """Check if LangSmith is enabled."""
        return self.config.enabled and self._initialized

    def create_run(
        self,
        name: str,
        run_type: str,
        inputs: dict,
        extra: Optional[dict] = None
    ) -> Optional[str]:
        """
        Create a trace run.

        Returns:
            run_id if successful, None otherwise
        """
        if not self.is_enabled():
            return None

        try:
            run_id = self._client.create_run(
                name=name,
                run_type=run_type,
                inputs=inputs,
                extra=extra or {},
                project_name=self.config.project_name
            )
            return run_id
        except Exception as e:
            print(f"[LangSmith] Create run failed: {e}")
            return None

    def end_run(
        self,
        run_id: str,
        outputs: dict,
        error: Optional[str] = None
    ) -> None:
        """End a trace run."""
        if not self.is_enabled():
            return

        try:
            self._client.end_run(
                run_id=run_id,
                outputs=outputs,
                error=error
            )
        except Exception as e:
            print(f"[LangSmith] End run failed: {e}")

    def patch_langchain(self) -> None:
        """
        Patch LangChain to automatically trace calls.

        This enables automatic tracing for LLM calls, embeddings, etc.
        """
        if not self.is_enabled():
            return

        try:
            from langchain.callbacks import LangChainTracer
            tracer = LangChainTracer(
                project_name=self.config.project_name
            )
            # Tracer is ready to be added to LLM/Chain callbacks
            self._tracer = tracer
        except ImportError:
            print("[LangSmith] Tracer not available")


# Global client instance
_langsmith_client: Optional[LangSmithClient] = None


def get_langsmith_client() -> LangSmithClient:
    """Get or create the global LangSmith client."""
    global _langsmith_client
    if _langsmith_client is None:
        _langsmith_client = LangSmithClient()
    return _langsmith_client


def configure_langsmith(
    api_key: Optional[str] = None,
    project_name: str = "biomed-troubleshooter",
    enabled: bool = True
) -> LangSmithClient:
    """
    Configure LangSmith observability.

    Usage:
        from src.infrastructure.langsmith_client import configure_langsmith

        # Initialize with environment variable or explicit key
        configure_langsmith(
            api_key="your-api-key",
            project_name="biomed-troubleshooter"
        )
    """
    from src.infrastructure.config import LangSmithConfig

    config = LangSmithConfig(
        api_key=api_key,
        project_name=project_name,
        enabled=enabled
    )
    client = LangSmithClient(config)
    client.initialize()

    global _langsmith_client
    _langsmith_client = client

    return client


def initialize_observability(
    api_key: str = None,
    project_name: str = "biomed-troubleshooter",
    enabled: bool = True
) -> None:
    """
    Initialize LangSmith observability.

    Environment variables:
        LANGCHAIN_API_KEY: LangSmith API key
        LANGCHAIN_PROJECT: Project name (default: biomed-troubleshooter)
        LANGCHAIN_TRACING: Enable tracing (default: true)
    """
    configure_langsmith(
        api_key=api_key,
        project_name=project_name,
        enabled=enabled
    )


class TracingDecorator:
    """
    Decorator for tracing function calls.
    """

    def __init__(self, name: str, run_type: str = "function"):
        self.name = name
        self.run_type = run_type

    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            client = get_langsmith_client()

            if not client.is_enabled():
                return func(*args, **kwargs)

            # Create run
            run_id = client.create_run(
                name=self.name,
                run_type=self.run_type,
                inputs={"args": str(args), "kwargs": str(kwargs)}
            )

            try:
                result = func(*args, **kwargs)
                client.end_run(run_id, outputs={"result": str(result)})
                return result
            except Exception as e:
                client.end_run(run_id, outputs={}, error=str(e))
                raise

        return wrapper


def trace_agent_node(node_name: str) -> Callable:
    """
    Decorator to trace LangGraph node execution.

    Usage:
        @trace_agent_node("validate_input")
        def validate_input(state: AgentState) -> AgentState:
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(state, *args, **kwargs):
            client = get_langsmith_client()

            if not client.is_enabled():
                return func(state, *args, **kwargs)

            # Create run
            run_id = client.create_run(
                name=f"node.{node_name}",
                run_type="node",
                inputs={"state_keys": list(state.__dict__.keys())}
            )

            try:
                result = func(state, *args, **kwargs)
                client.end_run(
                    run_id,
                    outputs={"node_history": result.node_history}
                )
                return result
            except Exception as e:
                client.end_run(run_id, outputs={}, error=str(e))
                raise

        return wrapper
    return decorator
