"""
Utility functions for MultiAgent system.
"""
import logging
from pathlib import Path, PurePath
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Agent display styling for Streamlit
AGENT_STYLES = """
<style>
.agent-item {
    display: flex;
    align-items: center;
    padding: 8px;
    border-radius: 5px;
    margin-bottom: 5px;
    position: relative;
    cursor: pointer;
    background-color: rgba(255, 255, 255, 0.1);
}
.agent-emoji {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 10px;
    font-size: 18px;
}
.agent-name {
    flex-grow: 1;
    font-size: 14px;
}
.agent-status {
    font-size: 10px;
    color: #4CAF50;
    margin-left: 5px;
}
.agent-tooltip {
    display: none;
    position: absolute;
    background-color: #333;
    color: white;
    padding: 10px;
    border-radius: 5px;
    width: 200px;
    top: 100%;
    left: 0;
    z-index: 1000;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}
.agent-item:hover .agent-tooltip {
    display: block;
}
</style>
"""

# Agent definitions with their details
AGENTS = {
    "QuestionAnswerer": {
        "emoji": "🔍",
        "color": "#4285F4",
        "description": "Searches for information and provides detailed answers to your questions"
    },
    "AnswerChecker": {
        "emoji": "✅",
        "color": "#34A853",
        "description": "Verifies the accuracy of information provided by other agents"
    },
    "LinkChecker": {
        "emoji": "🔗",
        "color": "#FBBC05",
        "description": "Validates links to ensure all references are working correctly"
    },
    "Manager": {
        "emoji": "📊",
        "color": "#EA4335",
        "description": "Coordinates the workflow between all agents and approves final responses"
    }
}

def load_env_variables():
    """Load environment variables from .env file."""
    current_dir = Path(__file__).parent.parent
    env_path = PurePath(current_dir).joinpath(".env")
    load_dotenv(dotenv_path=env_path)
    logger.info("Environment variables loaded")

def get_agent_avatar(agent_name):
    """
    Get an appropriate emoji avatar based on agent name.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        str: Emoji representing the agent
    """
    # Default to a robot emoji if no match is found
    default_avatar = "🤖"
    
    # Map agent names to emojis
    avatar_map = {
        "QuestionAnswererAgent": "🔍",
        "AnswerCheckerAgent": "✅",
        "LinkCheckerAgent": "🔗",
        "ManagerAgent": "📊"
    }
    
    # Try to match the full name first
    if agent_name in avatar_map:
        return avatar_map[agent_name]
    
    # Try to match partial names    
    for key in avatar_map:
        if key.lower() in agent_name.lower():
            return avatar_map[key]
            
    return default_avatar

def render_agents_online():
    """
    Generate HTML for displaying agents online in the Streamlit sidebar.
    
    Returns:
        str: HTML for agent display and CSS styling
    """
    # Start with the CSS styling
    html = AGENT_STYLES
    
    # Add the heading
    html += "<h4 style='margin-bottom: 0px;'>Agents Online:</h4>"
    
    # Add each agent
    for agent_name, details in AGENTS.items():
        html += f"""<div class="agent-item">
                <div class="agent-emoji" style="background-color: {details['color']};">
                    {details['emoji']}
                </div>
                <div class="agent-name">
                    {agent_name} Agent
                </div>
                <div class="agent-status">
                    ● Online
                </div>
                <div class="agent-tooltip">
                    {details['description']}
                </div>
            </div>"""
    
    # Add a separator
    html += "<hr/>"
    
    return html

class SearchFunctionFilter:
    pass