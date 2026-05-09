__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from src.server.api.main import app

        return app
    raise AttributeError(name)
