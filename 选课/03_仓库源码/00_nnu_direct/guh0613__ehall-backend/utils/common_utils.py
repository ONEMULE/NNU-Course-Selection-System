from configs import config


def get_cas_url() -> str:
    """return the CAS URL for the specified school."""
    return config.CAS_SERVER_URL


def get_ehall_url() -> str:
    """return the eHall URL for the specified school."""
    return config.EHALL_SERVER_URL


def get_ehallapp_url() -> str:
    """return the eHallApp URL for the specified school."""
    return config.EHALLAPP_SERVER_URL
