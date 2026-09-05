from dataclasses import dataclass


@dataclass
class PunchError(Exception):
    code: str
    detail: str
    status_code: int = 400
    kiosk: object = None
    distance: float | None = None

    def __str__(self):
        return self.detail
