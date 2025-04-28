"""
Multi-Agent helper Helper Streamlit Application
"""
import os
import asyncio
import uuid
import streamlit as st
# Import from refactored modules
from helper.utils import load_env_variables, get_agent_avatar, render_agents_online, logger
from helper.agents import MultiAgent

# Load environment variables
load_env_variables()

# Set Streamlit page configuration
st.set_page_config(page_title="Multi-Agent RFX Helper", page_icon="🤖", layout="wide")
st.title("Multi-Agent RFX Helper")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_inner_monologue" not in st.session_state:
    st.session_state.show_inner_monologue = True
if "agent_instance" not in st.session_state:
    st.session_state.agent_instance = MultiAgent()

# Sidebar configuration
with st.sidebar:
    st.header("Agent Configuration")
    
    # Display agents online using the utility function
    st.markdown(render_agents_online(), unsafe_allow_html=True)
    
    # Toggle for showing/hiding inner monologue
    st.session_state.show_inner_monologue = st.checkbox(
        "Show Agents' Inner Monologue", 
        value=False
    )
    # Context select dropdown
    st.subheader("Research Context")
    
    # Initialize selected_context in session state if it doesn't exist
    if "selected_contexts" not in st.session_state:
        st.session_state.selected_contexts = ["Azure AI"]
    
    # Context mapping for agent prompts
    context_mapping = {
        "Azure AI": "Microsoft Azure AI",
        "Fabric": "Microsoft Fabric",
        "Copilot Studio": "Microsoft Copilot Studio",
        "M365 Copilot": "Microsoft 365 Copilot"
    }
    
    # Create the multiselect with our context options
    selected_contexts = st.multiselect(
        "Select research contexts:",
        options=list(context_mapping.keys()),
        default=st.session_state.selected_contexts,
        key="context_multiselect"
    )
    
    # If nothing is selected, default to "Azure AI"
    if not selected_contexts:
        selected_contexts = ["Azure AI"]
    
    # Update session state with the selection and update agent context
    if selected_contexts != st.session_state.selected_contexts:
        st.session_state.selected_contexts = selected_contexts
        
        # Create a combined context string for the agent
        if len(selected_contexts) > 1:
            # Join multiple contexts with commas and "and"
            context_names = [context_mapping[ctx] for ctx in selected_contexts]
            if len(context_names) == 2:
                context_str = f"{context_names[0]} and {context_names[1]}"
            else:
                context_str = ", ".join(context_names[:-1]) + f", and {context_names[-1]}"
        else:
            # Single selection
            context_str = context_mapping[selected_contexts[0]]
            
        # Update the agent's context based on the multiselect
        st.session_state.agent_instance.update_prompts(context=context_str)
        st.success(f"Context updated to: {context_str}")
    
    if st.button("Restart Conversation 🔄"):
        st.session_state.messages = []
        st.rerun()
    RESOURCES_FOLDER = os.path.join(os.path.dirname(__file__), 'resources')
    st.image(os.path.join(RESOURCES_FOLDER, "flowchart.png"), use_container_width=True, caption="Flowchart of the Multi-Agent System")

# Display chat history
for msg in st.session_state.messages:
    # Check if the message has inner monologue data
    if "role" in msg and msg["role"] == "assistant" and "inner_monologue" in msg and st.session_state.show_inner_monologue:
        # Display the inner monologue in an expander
        with st.expander("💭 Agents' Inner Monologue", expanded=True):
            # Display structured inner monologue
            if isinstance(msg["inner_monologue"], list):
                for dialogue in msg["inner_monologue"]:
                    agent = dialogue.get("agent", "Assistant")
                    content = dialogue.get("content", "")
                    st.markdown(f"{get_agent_avatar(agent)} **{agent}**: {content}")
        
        # Display just the final response (if available)
        if "final_answer" in msg:
            with st.chat_message("assistant"):
                st.markdown(msg["final_answer"])
    else:
        # Display normal messages
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Handle user input
if prompt := st.chat_input("Ask a question about Microsoft Technology..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Process the message with the agent system
    with st.spinner("Agents are collaborating on your question..."):
        # Create a placeholder for live updates
        live_update_container = st.empty()
        
        # Modify the MultiAgent ask_question method to accept a callback for UI updates
        async def update_ui_callback(agent_name, response_text):
            with live_update_container.container():
                st.write(f"💭 {get_agent_avatar(agent_name)} **{agent_name}** is thinking...")
                st.markdown(f"{response_text}")
                
        # Process the message with UI updates
        response = asyncio.run(st.session_state.agent_instance.ask_question(
            prompt, 
            ui_callback=update_ui_callback
        ))
        
        # Store the full structured response
        if isinstance(response, dict):
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["final_answer"],  # For compatibility
                "inner_monologue": response["inner_monologue"],
                "final_answer": response["final_answer"]
            })
        else:
            # Handle error case
            st.session_state.messages.append({
                "role": "assistant",
                "content": str(response)
            })
        
        # Clear the live update container
        live_update_container.empty()
    
    # Force a rerun to update the UI
    st.rerun()