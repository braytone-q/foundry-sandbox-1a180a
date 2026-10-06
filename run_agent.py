from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = "https://veloking45-8432-resource.services.ai.azure.com/api/projects/regen-agentic-ai"

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

my_agent = "regen"
my_version = "9"

openai_client = project_client.get_openai_client()

activity = input("Enter environmental activity: ")

response = openai_client.responses.create(
    input=[
        {
            "role": "user",
            "content": activity
        }
    ],
    extra_body={
        "agent_reference": {
            "name": my_agent,
            "version": my_version,
            "type": "agent_reference"
        }
    },
)

print("\nRe-gen Analysis:\n")
print(response.output_text)