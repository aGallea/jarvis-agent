# import socket
import uvicorn
# from zeroconf import ServiceInfo, Zeroconf

from jarvis_agent.app import create_app
from jarvis_agent.settings import Settings
from jarvis_agent.utils.logger import init_logger


def main():
    settings = Settings()
    init_logger(settings)
    app = create_app(settings=settings)
    # hostname = socket.gethostname()
    # ip = socket.gethostbyname(hostname)
    # desc = {'info': 'Termux server'}

    # info = ServiceInfo(
    #     "_http._tcp.local.",
    #     "TermuxServer._http._tcp.local.",
    #     addresses=[socket.inet_aton(ip)],
    #     port=settings.port,
    #     properties=desc,
    # )

    # zeroconf = Zeroconf()
    # zeroconf.register_service(info)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
