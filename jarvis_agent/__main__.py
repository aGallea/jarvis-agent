import uvicorn

from jarvis_agent.app import create_app
from jarvis_agent.settings import Settings
from jarvis_agent.utils.logger import init_logger


def main():
    settings = Settings()
    init_logger(settings)
    app = create_app(settings=settings)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
