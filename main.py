import os
from fastapi import FastAPI
from ga_report import popular_report
import uvicorn


app = FastAPI(
    title="Mirror TV Ga Report Service",
    description="API to generate Mirror TV Ga Report based on Google Analytics data.",
    version="1.0.0",
)

@app.get("/")
async def root():
    return {
        "service": "Mirror TV Ga Report Service",
        "status": "ok"}

@app.get("/generate_popular_report")
async def generate_popular_report():
    ga_id = os.environ.get('GA_RESOURCE_ID', "311149968")
    result = await popular_report(ga_id)
    return {"status": result}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
