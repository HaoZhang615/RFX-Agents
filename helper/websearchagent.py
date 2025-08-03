# Import necessary libraries and modules
import os
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import BingGroundingTool, BingCustomSearchTool

# Load environment variables from .env file
load_dotenv()

# Retrieve required environment variables
project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
agent_id = os.environ.get("AZURE_AGENT_ID")
BING_CUSTOM_CONNECTION = os.environ.get("BING_CUSTOM_CONNECTION_NAME")
configuration_name = os.environ["BING_CUSTOM_INSTANCE_NAME"]

# Initialize the Azure AI Project client
project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(),
)
# Get the Bing connection ID
bing_custom_connection = project_client.connections.get(name=BING_CUSTOM_CONNECTION)
conn_id = bing_custom_connection.id

# Create agent with the bing custom search tool and process assistant run
with project_client:
    agents_client = project_client.agents
    agent = agents_client.get_agent(agent_id=agent_id)

    # Create thread for communication
    thread = agents_client.threads.create()
    print(f"Created thread, ID: {thread.id}")

    # Create message to thread
    message = agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content="what skus are available for the Fabric capacity?",
    )
    print(f"Created message, ID: {message.id}")

    # Create and process Agent run in thread with tools
    run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
    print(f"Run finished with status: {run.status}")

    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    # Uncomment these lines to delete the Agent when done
    #agents_client.delete_agent(agent.id)
    #print("Deleted agent")

    # Fetch and log all messages
    messages = agents_client.messages.list(thread_id=thread.id)
    for msg in messages:
        if msg.text_messages:
            for text_message in msg.text_messages:
                if msg.role == "assistant":
                    print(f"Agent response: {text_message.text.value}")
                elif msg.role == "user":
                    print(f"User message: {text_message.text.value}")
                else:
                    print(f"{msg.role}: {text_message.text.value}")
            
            # Only show citations for agent responses
            if msg.role == "assistant":
                for annotation in msg.url_citation_annotations:
                    print(f"URL Citation: [{annotation.url_citation.title}]({annotation.url_citation.url})")