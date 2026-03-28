from flask import Flask
import subprocess

app = Flask(__name__)

@app.route("/")
def run_bot():
    try:
        result = subprocess.run(["python", "monitor.py"], capture_output=True, text=True, timeout=60)
        return f"SUCCESS\n{result.stdout}"
    except Exception as e:
        return f"ERROR\n{str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
