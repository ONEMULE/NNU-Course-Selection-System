from fastapi import FastAPI

from routers import login_router

app = FastAPI()

app.include_router(login_router.router, prefix='/login')

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
