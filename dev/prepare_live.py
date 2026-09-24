"""Copy only the configured OpenAI key to the disposable dev instance, without output.

Run on the host. Never copies login credentials or prints the key.
"""
import subprocess

key = subprocess.check_output([
    "docker", "exec", "-w", "/a0", "agent-zero-v2", "/opt/venv-a0/bin/python", "-c",
    "import models; print(models.get_api_key('openai'), end='')",
])
assert key and key.strip() not in (b"None", b""), "No configured OpenAI key"
subprocess.run([
    "docker", "exec", "-i", "-w", "/a0", "a0-rtv-dev", "/opt/venv-a0/bin/python", "-c",
    "import sys; from helpers.dotenv import save_dotenv_value; save_dotenv_value('API_KEY_OPENAI', sys.stdin.read())",
], input=key, check=True, stdout=subprocess.DEVNULL)
print("Configured the disposable instance's OpenAI key (value not displayed).")
