import sys
import subprocess

issue = sys.argv[1]
command = ["gh", "api", "--jq", ".labels.[].name", issue]
result = subprocess.run(command, stdout=subprocess.PIPE)
labels = result.stdout.decode("utf-8").splitlines()

for lb in labels:
    table = lb.split("Register")[1].strip() if "Register" in lb else None
    if table:
        break
print(f"{table}")
