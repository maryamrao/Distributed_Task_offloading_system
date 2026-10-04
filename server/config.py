HOST = "0.0.0.0"
PORT = 5000

BASE_DIR = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]
JOBS_DIR = "jobs"
SOCKET_TIMEOUT = 30
CHUNK_SIZE = 1024 * 1024
