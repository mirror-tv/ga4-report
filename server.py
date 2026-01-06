from flask import Flask
from ga_report import popular_report
import os

app = Flask(__name__)

@app.route("/generate_popular_report")
def generate_popular_report():
	if 'GA_RESOURCE_ID' in os.environ:
		ga_id = os.environ['GA_RESOURCE_ID']
	else:
		ga_id = "311149968"
	popular_report(ga_id)
	return "ok"

if __name__ == "__main__":
    app.run()
