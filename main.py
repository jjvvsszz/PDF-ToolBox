import uvicorn
from app.config import HOST, PORT, LOG_LEVEL, WORKERS

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level=LOG_LEVEL, workers=WORKERS)
