import re

with open('workflow_map.mmd', 'r') as f:
    mermaid_code = f.read()

mermaid_block = "```mermaid\n" + mermaid_code + "\n```"

with open('README.md', 'r') as f:
    readme = f.read()

# Replace the image tag with the mermaid block
readme = readme.replace('![Data Processing Workflow](docs/workflow_map.png)', mermaid_block)

with open('README.md', 'w') as f:
    f.write(readme)
